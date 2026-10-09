import unittest
from sofascore_odds import normalized,fixture_match,three_way_market,link_fixtures,decimal

class SofaOddsTests(unittest.TestCase):
    def test_exact_name_and_kickoff_required(self):
        fixture={'home':'Fluminense FC','away':'Coritiba','start_timestamp':1800000000}
        event={'id':111,'homeTeam':{'name':'Fluminense'},'awayTeam':{'name':'Coritiba FC'},
            'startTimestamp':1800000200}
        self.assertTrue(fixture_match(fixture,event))
        self.assertFalse(fixture_match(fixture,{**event,'startTimestamp':1800000700}))
        self.assertFalse(fixture_match(fixture,{**event,'homeTeam':{'name':'Flamengo'}}))

    def test_odds_1x2_decimals_from_fractional(self):
        m={'markets':[{'marketId':1,'marketName':'Full time','isLive':False,
            'suspended':False,'choices':[
            {'name':'1','fractionalValue':'6/5'},
            {'name':'X','fractionalValue':'12/5'},
            {'name':'2','fractionalValue':'9/4'}]}]}
        prices,provider=three_way_market(m)
        self.assertEqual(prices,{'home':2.2,'draw':3.4,'away':3.25})
        self.assertEqual(provider,'Bookmaker não identificado')
        self.assertEqual(decimal({'fractionalValue':'0/0'}),None)

    def test_live_and_suspended_odds_rejected(self):
        market={'marketId':1,'marketName':'Full time','isLive':True,
          'choices':[{'name':a,'decimalValue':2.0} for a in ('1','X','2')]}
        self.assertIsNone(three_way_market({'markets':[market]}))
        self.assertIsNone(three_way_market({'markets':[{**market,'isLive':False,'suspended':True}]}))

    def test_match_ambiguity_rejected(self):
        f={'home':'Fluminense','away':'Coritiba','start_timestamp':1800000000}
        ev={'id':10,'homeTeam':{'name':'Fluminense'},'awayTeam':{'name':'Coritiba'},
          'startTimestamp':1800000000}
        selected=link_fixtures([('2026-10-09','fotmob-1',500,f)],[ev,{**ev,'id':11}])
        self.assertEqual(selected,[])
        self.assertEqual(len(link_fixtures([('2026-10-09','fotmob-1',500,f)],[ev])),1)

if __name__=='__main__':unittest.main()
