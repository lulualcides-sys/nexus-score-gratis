import unittest
from datetime import datetime, timezone, timedelta
from web_export import public_odds_comparison

class BestPriceTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc)
        self.t=self.now.timestamp()
        self.at=lambda dt:dt.isoformat()
    def quote(self,book,odds,when,market='btts',sel='yes',source='OddsPapi'):
        return {'market':market,'selection':sel,'odds':odds,'source':source,
                'bookmaker':book,'captured_at':self.at(when)}
    def test_best_price_identifies_bookmaker_and_observed_at(self):
        f={'phase':'scheduled','start_timestamp':int(self.t+3600)}
        offers=[
            self.quote('Betano BR',1.9,self.now-timedelta(minutes=5)),
            self.quote('Pinnacle',2.15,self.now-timedelta(minutes=4)),
            self.quote('Betano BR',2.0,self.now-timedelta(minutes=2)),
            self.quote('Outdated',3.0,self.now-timedelta(hours=26)),
        ]
        data=public_odds_comparison(offers,f,'pregame',self.t)
        self.assertEqual(len(data),1)
        self.assertEqual(data[0]['best']['bookmaker'],'Pinnacle')
        self.assertEqual(data[0]['best']['odds'],2.15)
        self.assertEqual(data[0]['books_compared'],2)
        self.assertEqual(data[0]['alternatives'][0]['bookmaker'],'Betano BR')
        self.assertIn('at',data[0]['best'])
    def test_no_live_from_pre_match_or_expired(self):
        f={'phase':'live','start_timestamp':int(self.t-600)}
        q=[
            self.quote('Betano',2.3,self.now-timedelta(minutes=3),
                       market='1x2',sel='home'),
            self.quote('Pinnacle',3.4,self.now-timedelta(hours=1),
                       market='1x2',sel='home'),
            self.quote('Other',4.0,self.now-timedelta(minutes=18),
                       market='1x2',sel='home'),
        ]
        data=public_odds_comparison(q,f,'live',self.t)
        self.assertEqual(len(data),1)
        self.assertEqual(data[0]['best']['odds'],2.3)
        self.assertEqual(data[0]['books_compared'],1)
        self.assertEqual(public_odds_comparison(q,f,'pregame',self.t),[])
    def test_finished_games_never_present_pregame_as_current(self):
        f={'phase':'finished','start_timestamp':int(self.t-3600)}
        data=public_odds_comparison([
           self.quote('Pinnacle',5,self.now-timedelta(hours=2),
                      market='over_under_25',sel='under')],f,'pregame',self.t)
        self.assertEqual(data,[])


    def test_new_goal_lines_are_kept_separate(self):
        f={'phase':'scheduled','start_timestamp':int(self.t+3600)}
        offers=[self.quote('Pinnacle',1.5,self.now-timedelta(minutes=2),
                          market='over_under_15',sel='over'),
                self.quote('Betano BR',2.4,self.now-timedelta(minutes=2),
                          market='over_under_35',sel='over')]
        compared=public_odds_comparison(offers,f,'pregame',self.t)
        self.assertEqual({x['market'] for x in compared},
                         {'over_under_15','over_under_35'})
        self.assertEqual(len(compared),2)
    def test_asian_lines_not_crossed_between_markets(self):
        f={'phase':'scheduled','start_timestamp':int(self.t+1800)}
        q=[self.quote('Pinnacle',1.92,self.now-timedelta(minutes=1),
                      market='ah_m05',sel='home'),
           self.quote('Pinnacle',2.15,self.now-timedelta(minutes=1),
                      market='ah_p05',sel='home')]
        result=public_odds_comparison(q,f,'pregame',self.t)
        self.assertEqual({x['market'] for x in result},{'ah_m05','ah_p05'})
        self.assertEqual(len(result),2)

if __name__=='__main__':unittest.main()
