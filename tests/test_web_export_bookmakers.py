"""NEXUS: public odds may include several books, but never mix 1/X/2 quotes."""
import unittest
from web_export import public_row

class PublicMultiBookmakerOddsTests(unittest.TestCase):
    def row(self):
        from datetime import datetime,timezone
        start=int(datetime(2026,10,20,19,tzinfo=timezone.utc).timestamp())
        return {'fixture':{'id':'match-1','home':'Equipe A','away':'Equipe B',
                'league':'bra.1','source':'ESPN','phase':'scheduled',
                'start_timestamp':start},'odds_quotes':[]}
    def add(self,row,book,when,prices,source='OddsPapi'):
        for side,price in prices.items():
            row['odds_quotes'].append({'market':'1x2','selection':side,'odds':price,
                'bookmaker':book,'source':source,'captured_at':when})
    def test_complete_trios_from_three_books_are_public(self):
        row=self.row()
        self.add(row,'Betano BR','2026-10-19T12:00:00+00:00',
                 {'home':2.15,'draw':3.40,'away':3.50})
        self.add(row,'Pinnacle','2026-10-19T12:05:00+00:00',
                 {'home':2.11,'draw':3.50,'away':3.61})
        self.add(row,'Bet365','2026-10-19T12:10:00+00:00',
                 {'home':2.08,'draw':3.55,'away':3.64})
        offers=public_row(row,'2026-10-19')['odds']
        self.assertEqual(len(offers),9)
        self.assertEqual({o['bookmaker'] for o in offers},
                         {'Betano BR','Pinnacle','Bet365'})
        for book in ('Betano BR','Pinnacle','Bet365'):
            selected=[o for o in offers if o['bookmaker']==book]
            self.assertEqual({o['sel'] for o in selected},{'home','draw','away'})
            self.assertEqual(len({o['at'] for o in selected}),1)
    def test_partial_update_does_not_replace_complete_bookmaker_snapshot(self):
        row=self.row()
        self.add(row,'Pinnacle','2026-10-19T12:00:00+00:00',
                 {'home':2.10,'draw':3.20,'away':3.90})
        self.add(row,'Pinnacle','2026-10-19T12:15:00+00:00',{'home':1.01})
        offers=public_row(row,'2026-10-19')['odds']
        self.assertEqual(len(offers),3)
        self.assertEqual({o['at'] for o in offers},{'2026-10-19T12:00:00+00:00'})
    def test_incomplete_and_unattributed_offers_never_display(self):
        row=self.row()
        self.add(row,'Other Book','2026-10-19T12:00:00+00:00',{'home':2.1,'draw':3.2})
        self.add(row,'','2026-10-19T12:02:00+00:00',
                 {'home':2.1,'draw':3.2,'away':3.8})
        self.assertEqual(public_row(row,'2026-10-19')['odds'],[])

if __name__=='__main__':unittest.main()
