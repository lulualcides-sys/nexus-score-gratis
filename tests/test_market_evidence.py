import unittest
from market_evidence import audit_markets


def row(ident='A',closed=False,price=True,prob=55):
    b={'model_status':'experimental_uncalibrated',
       'indications':[
          {'market':'1x2','selection':'home','probability':prob},
          {'market':'double_chance','selection':'1X','probability':80},
          {'market':'over_under_25','selection':'over','probability':57},
          {'market':'btts','selection':'yes','probability':53}],
       'odds':{'recent_at_check':True,'prices':{'home':2.15,'draw':3.2,'away':3.5}} if price else None,
       'settlement':({'status':'finished','score':'2-1','checks':[
          {'market':'1x2','selection':'home','result':'hit'},
          {'market':'double_chance','selection':'1X','result':'hit'},
          {'market':'over_under_25','selection':'over','result':'hit'},
          {'market':'btts','selection':'yes','result':'miss'}]} if closed else None)}
    return {'id':ident,'pregame_baseline':b}

class MarketEvidenceTests(unittest.TestCase):
 def test_no_credited_bets_even_when_sport_forecast_correct(self):
    x=audit_markets([row('A',True)])
    self.assertEqual(x['fixtures_with_frozen_forecast'],1)
    self.assertEqual(x['fixtures_with_verified_pregame_1x2'],1)
    self.assertEqual(x['fixtures_with_result'],1)
    self.assertEqual(len(x['markets']),4)
    by={m['market']:m for m in x['markets']}
    self.assertEqual(by['1x2']['forecasts'],1)
    self.assertEqual(by['1x2']['with_price'],1)
    self.assertEqual(by['1x2']['theoretical_positive'],1)
    self.assertEqual(by['1x2']['hits'],1)
    self.assertEqual(by['btts']['misses'],1)
    self.assertEqual(by['double_chance']['with_price'],0)
    self.assertEqual(by['over_under_25']['with_price'],0)
    self.assertNotIn('paper_pl',str(x))
    self.assertNotIn('stake',str(x))
    self.assertNotIn('profit',str(x))

 def test_missing_odds_and_result_stay_pending(self):
    x=audit_markets([row('A',False,False)])
    self.assertEqual(x['fixtures_with_result'],0)
    self.assertEqual(x['fixtures_with_verified_pregame_1x2'],0)
    for m in x['markets']:
        self.assertEqual(m['pending'],1)
        self.assertEqual(m['settled'],0)
        self.assertIsNone(m['observed_hit_pct'])
        self.assertEqual(m['theoretical_positive'],0)

 def test_duplicate_fixture_and_untrusted_market_ignored(self):
    duplicate=row('A',True)
    another=row('B',True)
    another['pregame_baseline']['model_status']='retrospective'
    x=audit_markets([duplicate,duplicate,another,{'id':'C','pregame_baseline':{}}])
    self.assertEqual(x['fixtures_with_frozen_forecast'],1)
    self.assertEqual(sum(m['settled'] for m in x['markets']),4)

 def test_partial_trio_does_not_create_ev(self):
    x=row('Z',True)
    x['pregame_baseline']['odds']['prices'].pop('draw')
    y=audit_markets([x])
    self.assertEqual(y['fixtures_with_verified_pregame_1x2'],0)
    self.assertEqual(y['markets'][0]['theoretical_positive'],0)
    self.assertEqual(y['markets'][0]['settled'],1)

if __name__=='__main__':unittest.main()
