import unittest
from datetime import datetime,timezone
from urllib.parse import parse_qs,urlsplit
from oddspapi_odds import collect_odds,extract_1x2,match_fixture
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
    def test_no_key_no_call_and_free_slots(self):
        docs={'2026-10-19':{'matches':{'f1':fixture()}}}
        choices=[('2026-10-19','f1',2100)]
        calls=[]
        def f(url):calls.append(url);return []
        self.assertEqual(collect_odds(docs,choices,NOW,key='',fetcher=f)['status'],'not_configured')
        self.assertEqual(collect_odds(docs,choices,NOW+3600,key='free',fetcher=f)['status'],'waiting_free_slot')
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
if __name__=='__main__':unittest.main()
