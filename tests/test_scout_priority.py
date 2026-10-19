import unittest
from coletar import scout_priority, choose_scout_games
class ScoutPriorityTests(unittest.TestCase):
 def game(self):return {'id':'fotmob-1','minute':55}
 def old(self):
    return {'observations':[{'at':'2026-10-19T12:30:00+00:00'}]}
 def test_missing_scout_source_is_lower_than_measured_source(self):
    missing={**self.old(),'momentum_diagnostic':{'state':'not_provided'}}
    measured={**missing,'stats':{'home':{'shots_on':2},'away':{'shots_on':1}}}
    self.assertLess(scout_priority(self.game(),measured),scout_priority(self.game(),missing))
 def test_new_game_receives_first_observation(self):
    missing={**self.old(),'momentum_diagnostic':{'state':'not_provided'}}
    self.assertLess(scout_priority(self.game(),{}),scout_priority(self.game(),missing))
 def test_stale_observed_pressure_first(self):
    old={**self.old(),'thermometer':{'points':[{'minute':40,'value':17}]}}
    self.assertEqual(scout_priority(self.game(),old)[0],0)
 def test_no_fake_data_or_source_mutation(self):
    old={**self.old(),'momentum_diagnostic':{'state':'not_provided'}}
    before=repr(old)
    self.assertEqual(scout_priority(self.game(),old)[0],4)
    self.assertEqual(repr(old),before)

 def test_rechecks_missing_momentum_without_starving_verified_scouts(self):
    fixtures={}
    matches=[]
    for n in range(30):
       ident='fotmob-'+str(n)
       matches.append({'id':ident,'minute':60})
       fixtures[ident]={**self.old(),
         'stats':({'home':{'shots_on':3}} if n<13 else {}),
         'momentum_diagnostic':{'state':'observed' if n<13 else 'not_provided'}}
    chosen=choose_scout_games(matches,fixtures,12)
    self.assertEqual(len(chosen),12)
    self.assertEqual(len({x['id'] for x in chosen}),12)
    self.assertEqual(sum(int(x['id'][7:])>=13 for x in chosen),2)
 def test_maintains_first_look_priority(self):
    fixtures={}
    matches=[]
    for n in range(19):
       ident='fotmob-'+str(n)
       matches.append({'id':ident,'minute':54})
       fixtures[ident]={**self.old(),
         'momentum_diagnostic':{'state':'not_provided'}}
    matches.append({'id':'fotmob-new','minute':40})
    chosen=choose_scout_games(matches,fixtures,12)
    self.assertIn('fotmob-new',{g['id'] for g in chosen})
 def test_empty_and_no_mutation(self):
    games=[{'id':'fotmob-a','minute':53}]
    self.assertEqual(choose_scout_games(games,{},0),[])
    self.assertEqual(choose_scout_games(games,{},12),games)
if __name__=='__main__':unittest.main()
