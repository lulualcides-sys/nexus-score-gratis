import copy
import unittest
from datetime import datetime, timezone, timedelta
from pregame_audit import update_row, prediction, odds_snapshot, resolve
from web_export import public_baseline


class PregameAuditTests(unittest.TestCase):
    def make_row(self):
        now = datetime(2026,10,17,20,0,tzinfo=timezone.utc)
        start = int((now + timedelta(minutes=25)).timestamp())
        games = lambda gf,ga:[{'ts':start-86400*(i+1),'gf':gf,'ga':ga}
                               for i in range(8)]
        return now, {'fixture':{'id':'fotmob-123','home':'Equipe A','away':'Equipe B',
                               'phase':'scheduled','start_timestamp':start},
                     'team_form':{'home':{'games':games(2,1)},
                                  'away':{'games':games(1,2)}}}

    def test_frozen_before_start_and_settled_after_without_changing_forecast(self):
        now,row=self.make_row()
        self.assertTrue(update_row(row,now))
        saved=copy.deepcopy(row['pregame_baseline'])
        self.assertEqual(len(saved['indications']),4)
        self.assertIsNone(saved['odds'])
        later=now+timedelta(minutes=26)
        row['fixture'].update(phase='live',minute=1,score='0-0')
        row['team_form']={'home':{'games':[]},'away':{'games':[]}}
        self.assertFalse(update_row(row,later))
        self.assertEqual(row['pregame_baseline'],saved)
        row['fixture'].update(phase='finished',score='2-1')
        self.assertTrue(update_row(row,later))
        settled=row['pregame_baseline']['settlement']
        self.assertEqual(settled['count'],4)
        self.assertEqual(settled['status'],'sports_only_no_bet')
        self.assertEqual(row['pregame_baseline']['forecast'],saved['forecast'])
        self.assertFalse(update_row(row,later))

    def test_never_create_retroactive_prediction(self):
        now,row=self.make_row()
        row['fixture']['phase']='finished'
        self.assertFalse(update_row(row,now+timedelta(hours=3)))
        self.assertNotIn('pregame_baseline',row)

    def test_no_future_form_or_partial_results(self):
        now,row=self.make_row()
        start=row['fixture']['start_timestamp']
        row['team_form']['away']['games']=[{'ts':start+10,'gf':8,'ga':0}]*9
        self.assertIsNone(prediction(row,start))
        self.assertFalse(update_row(row,now))

    def test_odd_requires_same_provider_bet_at_same_instant(self):
        now,row=self.make_row()
        current=now.isoformat()
        row['odds_quotes']=[
            {'market':'1x2','selection':k,'odds':v,'source':'ESPN',
             'bookmaker':'Casa A','captured_at':current}
            for k,v in (('home',1.9),('draw',3.1),('away',4.0))]
        self.assertTrue(update_row(row,now))
        baseline=row['pregame_baseline']
        self.assertEqual(baseline['odds']['prices']['home'],1.9)
        self.assertIsNotNone(public_baseline(row,row['fixture'])['model_ev'])
        row2=copy.deepcopy(row)
        row2['odds_quotes'][1]['bookmaker']='Casa diferente'
        self.assertIsNone(odds_snapshot(row2,now.timestamp(),row2['fixture']['start_timestamp']))
        row2['pregame_baseline']=None
        self.assertTrue(update_row(row2,now))
        self.assertIsNone(row2['pregame_baseline']['odds'])

    def test_market_resolution_and_no_simulated_stake(self):
        self.assertTrue(resolve({'market':'double_chance','selection':'1X'},0,0))
        self.assertFalse(resolve({'market':'double_chance','selection':'12'},0,0))
        self.assertTrue(resolve({'market':'btts','selection':'yes'},2,1))
        self.assertTrue(resolve({'market':'over_under_25','selection':'under'},0,0))
        now,row=self.make_row()
        self.assertTrue(update_row(row,now))
        out=public_baseline(row,row['fixture'])
        self.assertNotIn('stake',str(out))
        self.assertNotIn('net_pl',str(out))
        self.assertNotIn('account',str(out))


if __name__=='__main__':
    unittest.main()
