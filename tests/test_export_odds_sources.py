import unittest
from web_export import public_row

class ExportOddsTests(unittest.TestCase):
    def test_does_not_combine_1x2_from_different_bookmakers(self):
        row={'fixture':{'id':'fotmob-1','home':'Casa','away':'Fora','phase':'scheduled'},
          'odds_quotes':[
           {'market':'1x2','selection':'home','odds':2.11,'source':'ESPN',
             'bookmaker':'A','captured_at':'2026-10-09T19:00:00Z'},
           {'market':'1x2','selection':'draw','odds':3.40,'source':'SofaScore',
             'bookmaker':'B','captured_at':'2026-10-09T19:01:00Z'},
           {'market':'1x2','selection':'away','odds':3.80,'source':'The Odds API',
             'bookmaker':'C','captured_at':'2026-10-09T19:02:00Z'}]}
        result=public_row(row,'2026-10-09')
        self.assertEqual(len(result['odds']),1)
    def test_prefers_full_same_bookmaker_trio_over_newer_single_price(self):
        offers=[
          {'market':'1x2','selection':side,'odds':price,'source':'ESPN',
           'bookmaker':'Casa A','captured_at':'2026-10-09T18:00:00Z'}
          for side,price in [('home',2.1),('draw',3.1),('away',3.6)]]
        offers.append({'market':'1x2','selection':'home','odds':1.95,
             'source':'SofaScore','bookmaker':'Casa B','captured_at':'2026-10-09T19:00:00Z'})
        row={'fixture':{'id':'fotmob-2','home':'Casa','away':'Fora','phase':'scheduled'},
             'odds_quotes':offers}
        result=public_row(row,'2026-10-09')
        self.assertEqual(len(result['odds']),3)
        self.assertEqual({x['bookmaker'] for x in result['odds']},{'Casa A'})

if __name__=="__main__":unittest.main()
