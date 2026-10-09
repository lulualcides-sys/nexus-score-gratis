import unittest
from signal_registry import active_signals,resolve,update,diagnostics

class SignalRegistryTests(unittest.TestCase):
    def game(self,minute=35,score='0-0',phase='live'):
        return {'id':'fotmob-55','home':'Casa','away':'Fora',
                'minute':minute,'score':score,'phase':phase,'source':'FotMob'}
    def data(self,stat=None,events=None,readings=None):
        if readings is None:readings=[-70]*10
        return {'thermometer':{'points':[{'minute':m,'value':v}
            for m,v in zip(range(26,36),readings)]},
            'stats':stat if stat is not None else {'away':{'shots_on':4,'big_chances':2}},
            'events':events or []}
    def test_three_existing_pressure_rules_run_with_away_team(self):
        signals=active_signals(self.game(),self.data(),'2026-10-09T10:30:00Z')
        self.assertEqual([s['rule'] for s in signals],
            ['pressao_forte_10min','pressao_total_5_10min','alerta_cruzado_gol'])
        self.assertTrue(all(s['team']=='away' and s['ev_pct'] is None for s in signals))
    def test_cumulative_indicators_work_without_pressure_but_without_fake_minute(self):
        row={'stats':{'home':{'shots_on':6,'corners':7,'big_chances':3,
                     'dangerous_attacks':26},'away':{'shots_on':1}}}
        found=active_signals(self.game(50),row,'2026-10-09T18:00:00Z')
        self.assertEqual([e['icon'] for e in found],['🎯','🚩','💣','⚔️'])
        self.assertTrue(all(e['basis']=='cumulative_stat_snapshot' for e in found))
        self.assertTrue(all(e['team']=='home' and e['minute']==50 for e in found))
        self.assertTrue(all(e['odds'] is None and e['ev_pct'] is None for e in found))
        initial=update({'2026-10-09':{'matches':{'fixture-50':{
          'fixture':self.game(50),**row}}}}, {}, '2026-10-09T18:00:00Z')
        later=update({'2026-10-09':{'matches':{'fixture-50':{
          'fixture':self.game(70),**row}}}}, initial, '2026-10-09T18:20:00Z')
        self.assertEqual(len(initial['items']),4)
        self.assertEqual(len(later['items']),4)

    def test_missing_stale_and_insufficient_data_do_not_trigger(self):
        self.assertEqual(active_signals(self.game(48),self.data(),'t'),[])
        self.assertEqual(active_signals(self.game(),self.data(readings=[-70]*3),'t'),[])
        self.assertEqual(active_signals(self.game(35,phase='finished'),self.data(),'t'),[])
        self.assertFalse(any(e['icon']=='🚨' for e in active_signals(
            self.game(),self.data(stat={'away':{'shots_on':3}}),'t')))
    def test_diagnostic_distinguishes_missing_pressure_from_zero_signals(self):
        live={'fixture':self.game(),**self.data()}
        frozen={'fixture':{**self.game(80),'id':'fotmob-56'},**self.data()}
        d=diagnostics({'2026-10-09':{'matches':{'with':live,'stale':frozen}}})
        self.assertEqual(d['matches_live'],2)
        self.assertEqual(d['with_pressure'],2)
        self.assertEqual(d['fresh_pressure'],1)
        self.assertEqual(d['valid_10min'],1)
        self.assertEqual(d['matches_with_signals'],1)
    def test_duplicate_snapshot_is_not_new_alert(self):
        row=self.data()
        match={'fixture':self.game(),**row}
        docs={'2026-10-09':{'matches':{'fotmob-55':match}}}
        first=update(docs,{},'2026-10-09T11:00:00Z')
        second=update(docs,first,'2026-10-09T11:10:00Z')
        self.assertEqual(len(first['items']),3)
        self.assertEqual(len(second['items']),3)
    def test_goal_is_confirmed_only_with_correct_time(self):
        item=active_signals(self.game(),self.data(),'t')[0]
        row=self.data(events=[{'type':'goal','minute':39,'side':'away'}])
        resolve(item,self.game(40,'0-1'),row)
        self.assertEqual(item['outcomes']['5'],'gol_confirmado')
        self.assertEqual(item['outcomes']['10'],'gol_confirmado')
        resolve(item,self.game(55,'0-1'),row)
        self.assertEqual(item['outcomes']['15'],'gol_confirmado')
    def test_changed_score_without_goal_minute_is_unknown(self):
        item=active_signals(self.game(),self.data(),'t')[0]
        resolve(item,self.game(55,'0-1'),self.data())
        self.assertTrue(all(s=='indeterminado' for s in item['outcomes'].values()))
    def test_same_score_after_horizon_is_no_goal(self):
        item=active_signals(self.game(),self.data(),'t')[0]
        resolve(item,self.game(55,'0-0'),self.data())
        self.assertTrue(all(s=='sem_gol_confirmado' for s in item['outcomes'].values()))
    def test_window_not_completed_after_full_time(self):
        row={'thermometer':{'points':[{'minute':m,'value':65}
            for m in range(79,89)]},'stats':{'home':{}}}
        item=active_signals(self.game(88),row,'t')[0]
        resolve(item,self.game(0,'0-0','finished'),self.data())
        self.assertTrue(all(s=='janela_incompleta' for s in item['outcomes'].values()))

if __name__=='__main__':unittest.main()
