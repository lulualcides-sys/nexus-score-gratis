import unittest
from nexus_original_529_rules import board,KEYS
from signal_registry import active_signals

class Original529RulesTests(unittest.TestCase):
    def points(self,value,start=26,end=35):
        return [{'minute':m,'value':value} for m in range(start,end+1)]

    def test_matches_original_twelve_indicator_states_and_team(self):
        stats={'home':{'shots_on':0,'big_chances':0,'corners':2},
               'away':{'shots_on':4,'big_chances':1,'corners':6,'dangerous_attacks':26}}
        actual=board(self.points(-70),35,stats)
        self.assertEqual([i['emoji'] for i in actual['board']],list(KEYS))
        active={a['emoji']:a for a in actual['active']}
        for icon in ('🧨','🔥','🚩','⚡','⚔️','🚨'):
            self.assertIn(icon,active)
        self.assertEqual(active['🔥']['team'],'AWAY')
        self.assertEqual(active['💣']['state'] if '💣' in active else 'inactive','inactive')
        self.assertEqual(actual['pressure10']['score'],88)
        self.assertEqual(actual['pressure5']['score'],88)
        self.assertEqual(next(a for a in actual['board'] if a['emoji']=='🧠')['state'],'unavailable')

    def test_stale_graph_does_not_trigger_temporal_alert(self):
        fixture={'id':'fotmob-1','home':'A','away':'B','phase':'live','minute':70,'score':'0-0'}
        row={'thermometer':{'points':self.points(-70)},'stats':{}}
        self.assertFalse([a for a in active_signals(fixture,row,'now')
                          if a['basis']=='pressure_window'])

    def test_original_timeline_requires_ten_minutes_for_graph_markers(self):
        fixture={'id':'fotmob-1','home':'A','away':'B','phase':'live','minute':1,'score':'0-0'}
        row={'thermometer':{'points':[{'minute':1,'value':0}]},'stats':{}}
        self.assertFalse(active_signals(fixture,row,'now'))

    def test_critical_and_tension_late_are_side_specific(self):
        b=board(self.points(75,71,80),80,{'home':{'shots_on':5,'big_chances':1}},[])
        active={x['emoji']:x for x in b['active']}
        self.assertEqual(active['⏱️']['team'],'HOME')
        self.assertIn('🚨',active)
        self.assertNotIn('🥶',active)

    def test_cold_and_red_with_no_momentum_do_not_look_like_goal_forecast(self):
        b=board([],53,{'away':{'red_cards':1}},[])
        states={x['emoji']:x for x in b['board']}
        self.assertEqual(states['🟥']['state'],'active')
        self.assertEqual(states['🟥']['team'],'AWAY')
        self.assertEqual(states['🔥']['state'],'unavailable')
        self.assertEqual(states['🧠']['state'],'unavailable')
        self.assertEqual(states['🚨']['state'],'unavailable')

if __name__=='__main__':unittest.main()
