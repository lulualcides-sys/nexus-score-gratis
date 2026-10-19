import unittest
from datetime import datetime,timezone
from pregame_refresh_quotes import append_trio,append_market_group
class QuoteReconfirmation(unittest.TestCase):
    def setUp(self):
        self.t=int(datetime(2026,10,19,20,tzinfo=timezone.utc).timestamp())
        self.price={'home':1.98,'draw':3.4,'away':4.5}
    def test_pregame_same_quote_new_timestamp_only_after_interval(self):
        row={'fixture':{'phase':'scheduled','start_timestamp':self.t+7200}}
        self.assertEqual(append_trio(row,self.price,'Pinnacle','OddsPapi',self.t),3)
        self.assertEqual(append_trio(row,self.price,'Pinnacle','OddsPapi',self.t+60),0)
        self.assertEqual(append_trio(row,self.price,'Pinnacle','OddsPapi',self.t+1900),3)
        self.assertEqual(len(row['odds_quotes']),6)
        self.assertNotEqual(row['odds_quotes'][0]['captured_at'],row['odds_quotes'][3]['captured_at'])
    def test_live_same_price_reconfirmed_without_historical_contamination(self):
        row={'fixture':{'phase':'live','start_timestamp':self.t-300}}
        pair={'yes':1.85,'no':1.95}
        self.assertEqual(append_market_group(row,'btts',pair,'Bet365','OddsPapi',self.t,'live'),2)
        self.assertEqual(append_market_group(row,'btts',pair,'Bet365','OddsPapi',self.t+60,'live'),0)
        self.assertEqual(append_market_group(row,'btts',pair,'Bet365','OddsPapi',self.t+360,'live'),2)
        self.assertEqual(len(row['live_odds_quotes']),4)
        self.assertNotIn('market_quotes',row)
    def test_no_prices_after_kickoff(self):
        row={'fixture':{'phase':'scheduled','start_timestamp':self.t+100}}
        self.assertEqual(append_trio(row,self.price,'Betano','OddsPapi',self.t+110),0)
        self.assertEqual(append_market_group(row,'btts',{'yes':1.8,'no':1.9},'Bet365','OddsPapi',self.t+110),0)
if __name__=='__main__':unittest.main()
