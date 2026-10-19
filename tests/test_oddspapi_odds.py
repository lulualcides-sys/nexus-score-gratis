import unittest
import json
import tempfile
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import parse_qs,urlsplit
from oddspapi_odds import collect_odds,extract_1x2,match_fixture,available_extra_markets,priority_score
NOW=int(datetime(2026,10,19,21,3,tzinfo=timezone.utc).timestamp())
def date(ts):
    return datetime.fromtimestamp(ts,timezone.utc).isoformat()
def fixture():
    return {'fixture':{'id':'f1','home':'Flamengo','away':'Palmeiras',
       'start_timestamp':NOW+2100,'league':'Brasileirão Série A','phase':'scheduled'}}
def event():
    return {'fixtureId':'odds123','hasOdds':True,'startTime':date(NOW+2100),
      'participant1Name':'Flamengo','participant2Name':'Palmeiras'}
def pricepacket():
    return {**event(),'bookmakerOdds':{'betano.bet.br':{
       'bookmakerIsActive':True,'suspended':False,
       'markets':{'101':{'marketActive':True,'outcomes':{
          '101':{'players':{'0':{'active':True,'price':1.93,'changedAt':date(NOW-200)}}},
          '102':{'players':{'0':{'active':True,'price':3.3,'changedAt':date(NOW-200)}}},
          '103':{'players':{'0':{'active':True,'price':4.2,'changedAt':date(NOW-200)}}},
       }}}}}}
class OddsPapiFreeTests(unittest.TestCase):
    def test_exact_match_and_ambiguity(self):
        self.assertEqual(match_fixture(fixture()['fixture'],[event()])['fixtureId'],'odds123')
        self.assertIsNone(match_fixture(fixture()['fixture'],[event(),event()]))
        wrong={**event(),'participant2Name':'Botafogo'}
        self.assertIsNone(match_fixture(fixture()['fixture'],[wrong]))
    def test_1x2_and_stale_guard(self):
        self.assertEqual(extract_1x2(pricepacket(),NOW)[0],{'home':1.93,'draw':3.3,'away':4.2})
        bad=pricepacket()
        del bad['bookmakerOdds']['betano.bet.br']['markets']['101']['outcomes']['102']
        self.assertIsNone(extract_1x2(bad,NOW))
        old=pricepacket()
        old['bookmakerOdds']['betano.bet.br']['markets']['101']['outcomes']['101']['players']['0']['changedAt']=date(NOW-90000)
        self.assertIsNone(extract_1x2(old,NOW))
    def test_no_prices_never_claims_bookmaker_data(self):
        from oddspapi_odds import available_1x2
        self.assertEqual(available_1x2({'hasOdds':False},NOW),[])
        self.assertIsNone(extract_1x2({'hasOdds':False},NOW))
        docs={'2026-10-19':{'matches':{'f1':fixture()}}}
        no_prices={**event(),'hasOdds':False}
        def fetch(url):
            return [event()] if '/fixtures?' in url else no_prices
        result=collect_odds(docs,[('2026-10-19','f1',2100)],NOW,
                            key='free-test',fetcher=fetch)
        self.assertEqual(result['status'],'checked')
        self.assertEqual(result['quotes_added'],0)
        self.assertEqual(result['errors'],[])
        self.assertFalse(docs['2026-10-19']['matches']['f1'].get('odds_quotes'))
    def test_multiple_bookmakers_one_free_api_request(self):
        docs={'2026-10-19':{'matches':{'f1':fixture()}}}
        many=pricepacket()
        # Outro bookmaker fornece os seus próprios três preços; nunca misturar casas.
        another=json.loads(json.dumps(many['bookmakerOdds']['betano.bet.br']))
        another['markets']['101']['outcomes']['101']['players']['0']['price']=2.13
        many['bookmakerOdds']['pinnacle']=another
        calls=[]
        def fetch(url):
            calls.append(url)
            return [event()] if '/fixtures?' in url else many
        result=collect_odds(docs,[('2026-10-19','f1',2100)],NOW,key='test-free',fetcher=fetch)
        self.assertEqual(result['requests'],2)
        self.assertEqual(result['quotes_added'],6)
        self.assertEqual(len(calls),2)
        qs=docs['2026-10-19']['matches']['f1']['odds_quotes']
        self.assertEqual({x['bookmaker'] for x in qs},{'Betano BR','Pinnacle'})
    def test_no_key_no_call_and_free_slots(self):
        docs={'2026-10-19':{'matches':{'f1':fixture()}}}
        choices=[('2026-10-19','f1',2100)]
        calls=[]
        def f(url):calls.append(url);return []
        self.assertEqual(collect_odds(docs,choices,NOW,key='',fetcher=f)['status'],'not_configured')
        self.assertEqual(collect_odds(docs,choices,NOW+7200,key='free',fetcher=f)['status'],'waiting_free_slot')
        self.assertEqual(calls,[])
    def test_fetched_betano_quote_preserves_real_observation(self):
        docs={'2026-10-19':{'matches':{'f1':fixture()}}}
        calls=[]
        def fetch(url):
            calls.append(url)
            args=parse_qs(urlsplit(url).query)
            self.assertEqual(args['apiKey'],['free-test-key'])
            if '/fixtures?' in url:return [event()]
            return pricepacket()
        out=collect_odds(docs,[('2026-10-19','f1',2100)],NOW,key='free-test-key',fetcher=fetch)
        self.assertEqual(out['status'],'checked')
        self.assertEqual(out['quotes_added'],3)
        self.assertEqual(out['requests'],2)
        offers=docs['2026-10-19']['matches']['f1']['odds_quotes']
        self.assertEqual({o['bookmaker'] for o in offers},{'Betano BR'})
        self.assertEqual({o['source'] for o in offers},{'OddsPapi'})
        self.assertEqual(len(offers),3)

    def test_delayed_runner_uses_once_per_window(self):
        later=NOW+27*60 # 21h30 UTC: runner chegou atrasado
        docs={'2026-10-19':{'matches':{'f1':fixture()}}}
        calls=[]
        def fetch(url):
            calls.append(url)
            return [event()] if '/fixtures?' in url else pricepacket()
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Path(tmp)/'usage.json'
            first=collect_odds(docs,[('2026-10-19','f1',480)],later,
                               key='mock',fetcher=fetch,ledger_path=ledger)
            self.assertEqual(first['status'],'checked')
            self.assertEqual(first['requests'],2)
            second=collect_odds(docs,[('2026-10-19','f1',480)],later+10*60,
                                key='mock',fetcher=fetch,ledger_path=ledger)
            self.assertEqual(second['status'],'already_checked')
            self.assertEqual(len(calls),2)
            usage=json.loads(ledger.read_text())
            self.assertEqual(usage['requests'],2)
            self.assertEqual(usage['slots']['2026-10-19T21']['requests'],2)
    def test_usage_budget_rejects_new_paid_requests(self):
        docs={'2026-10-19':{'matches':{'f1':fixture()}}}
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Path(tmp)/'usage.json'
            ledger.write_text(json.dumps({'month':'2026-10',
                                          'requests':186,'slots':{}}))
            calls=[]
            def fetch(url):calls.append(url);return []
            out=collect_odds(docs,[('2026-10-19','f1',2100)],NOW,
                             key='mock',fetcher=fetch,ledger_path=ledger)
            self.assertEqual(out['status'],'free_budget_exhausted')
            self.assertEqual(calls,[])
    def test_error_consumes_reserved_request_only_once(self):
        docs={'2026-10-19':{'matches':{'f1':fixture()}}}
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Path(tmp)/'usage.json'
            calls=[]
            def fetch(url):
                calls.append(url)
                raise RuntimeError('simulated provider outage')
            first=collect_odds(docs,[('2026-10-19','f1',2100)],NOW,
                               key='mock',fetcher=fetch,ledger_path=ledger)
            self.assertEqual(first['status'],'unavailable')
            self.assertEqual(first['requests'],1)
            again=collect_odds(docs,[('2026-10-19','f1',2100)],NOW,
                               key='mock',fetcher=fetch,ledger_path=ledger)
            self.assertEqual(again['status'],'already_checked')
            self.assertEqual(len(calls),1)
            self.assertEqual(json.loads(ledger.read_text())['requests'],1)

    def test_accepted_odds_calls_are_paced_to_avoid_429(self):
        docs={'2026-10-19':{'matches':{
            'f1':fixture(),
            'f2':{'fixture':{**fixture()['fixture'],'id':'f2',
                'away':'Botafogo','start_timestamp':NOW+2700}}}}}
        other={**event(),'fixtureId':'odds456',
               'participant2Name':'Botafogo','startTime':date(NOW+2700)}
        durations=[]
        calls=[]
        def fetch(url):
            calls.append(url)
            if '/fixtures?' in url:return [event(),other]
            if 'odds456' in url:return {**pricepacket(),'fixtureId':'odds456',
                                        'startTime':date(NOW+2700)}
            return pricepacket()
        result=collect_odds(docs,[('2026-10-19','f1',2100),
                                  ('2026-10-19','f2',2700)],NOW,
                            key='mock',fetcher=fetch,
                            sleep_fn=durations.append)
        self.assertEqual(result['status'],'checked')
        self.assertEqual(result['requests'],3)
        self.assertEqual(len(calls),3)
        self.assertEqual(durations,[1.2])

    def test_new_markets_only_when_complete_and_active(self):
        p=pricepacket()
        bookmaker=p['bookmakerOdds']['betano.bet.br']
        base=lambda price:{'players':{'0':{'active':True,'price':price,'changedAt':date(NOW-100)}}}
        bookmaker['markets']['104']={'marketActive':True,'outcomes':{
            '104':base(1.85),'105':base(1.98)}}
        bookmaker['markets']['1010']={'marketActive':True,'outcomes':{
            '1010':base(2.05),'1011':base(1.82)}}
        bookmaker['markets']['1072']={'marketActive':True,'outcomes':{
            '1072':{'players':{'0':{'active':True,'price':1.6,
                               'bookmakerOutcomeId':'opaque-4','changedAt':date(NOW-90)}}},
            '1073':{'players':{'0':{'active':True,'price':2.3,
                               'bookmakerOutcomeId':'opaque-7','changedAt':date(NOW-90)}}}}}
        found={name:values for name,values,book in available_extra_markets(p,NOW)}
        self.assertEqual(found['btts'],{'yes':1.85,'no':1.98})
        self.assertEqual(found['over_under_25'],{'over':2.05,'under':1.82})
        self.assertEqual(found['ah_0'],{'home':1.6,'away':2.3})
        bookmaker['markets']['104']['outcomes']['105']['players']['0']['active']=False
        self.assertNotIn('btts',{n for n,_,_ in available_extra_markets(p,NOW)})
    def test_priority_high_coverage_and_near_kickoff(self):
        premier={'league':'Premier League'}
        minor={'league':'Unlisted minor division'}
        self.assertLess(priority_score(premier,1800),priority_score(minor,1800))
        self.assertLess(priority_score(premier,1800),priority_score(premier,7200))
    def test_single_paid_request_returns_three_real_markets(self):
        docs={'2026-10-19':{'matches':{'f1':fixture()}}}
        data=pricepacket()
        d=lambda price:{'players':{'0':{'active':True,'price':price,'changedAt':date(NOW-60)}}}
        data['bookmakerOdds']['betano.bet.br']['markets']['1010']={
            'marketActive':True,'outcomes':{'1010':d(1.8),'1011':d(2.1)}}
        data['bookmakerOdds']['betano.bet.br']['markets']['104']={
            'marketActive':True,'outcomes':{'104':d(1.7),'105':d(2.2)}}
        def fetch(url):return [event()] if '/fixtures?' in url else data
        out=collect_odds(docs,[('2026-10-19','f1',2100)],NOW,
                         key='fake',fetcher=fetch)
        self.assertEqual(out['requests'],2)
        self.assertEqual(out['quotes_added'],3)
        self.assertEqual(out['markets_added'],4)
        self.assertEqual({i['market'] for i in docs['2026-10-19']['matches']['f1']['market_quotes']},
                         {'btts','over_under_25'})
    def test_live_market_keeps_strict_separate_phase(self):
        data=pricepacket()
        data['statusId']=1
        fixture_live={**fixture()['fixture'],'phase':'live',
                       'start_timestamp':NOW-600}
        listed={**event(),'statusId':1,'startTime':date(NOW-600)}
        data.update({'startTime':date(NOW-600),'statusId':1})
        # Atualizar o horario de preco; precos antigos nao sao LIVE.
        for m in data['bookmakerOdds']['betano.bet.br']['markets'].values():
            for out in m['outcomes'].values():
                for offer in out['players'].values():
                    offer['changedAt']=date(NOW-55)
        docs={'2026-10-19':{'matches':{'f1':{'fixture':fixture_live}}}}
        def fetch(url):return [listed] if '/fixtures?' in url else data
        got=collect_odds(docs,[('2026-10-19','f1',-600)],NOW,key='mock',fetcher=fetch)
        self.assertEqual(got['live_quotes_added'],3)
        self.assertEqual(got['quotes_added'],0)
        self.assertFalse(docs['2026-10-19']['matches']['f1'].get('odds_quotes'))
        self.assertEqual({q['phase'] for q in docs['2026-10-19']['matches']['f1']['live_odds_quotes']},{'live'})

    def test_ah0_rejects_incomplete_and_wrong_outcome_ids(self):
        data=pricepacket()
        m=data['bookmakerOdds']['betano.bet.br']['markets']
        base=lambda p:{'players':{'0':{'active':True,'price':p,
                                     'changedAt':date(NOW-30)}}}
        m['1072']={'marketActive':True,'outcomes':{'1072':base(1.85),
                                                   'bogus':base(2.0)}}
        self.assertNotIn('ah_0',{slug for slug,_,_ in available_extra_markets(data,NOW)})
        m['1072']['outcomes']['1073']=base(2.1)
        self.assertIn('ah_0',{slug for slug,_,_ in available_extra_markets(data,NOW)})
        m['1072']['outcomes']['1073']['players']['0']['active']=False
        self.assertNotIn('ah_0',{slug for slug,_,_ in available_extra_markets(data,NOW)})
if __name__=='__main__':unittest.main()
