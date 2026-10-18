import copy
import unittest
from datetime import datetime,timezone,timedelta
from pregame_archive_merge import consolidate

START=int(datetime(2026,10,17,22,tzinfo=timezone.utc).timestamp())

def forecast(home=37,source='FotMob'):
 return {
  'captured_at':'2026-10-17T20:39:00+00:00','model':'Poisson experimental',
  'forecast':{'one_x_two':{'home':home,'draw':25,'away':75-home}},
  'indications':[
   {'market':'1x2','selection':'home','probability':home},
   {'market':'over_under_25','selection':'under','probability':55},
   {'market':'btts','selection':'no','probability':52}],
  'odds':None,'settlement':None}

def record(mid,home,away,minute=0,phase='scheduled',score='0-0',base=None,source='FotMob',start=START):
 return {'fixture':{'id':mid,'home':home,'away':away,'source':source,
          'start_timestamp':start+minute*60,'phase':phase,'score':score,
          'league':'Série A' if source=='FotMob' else 'bra.1'},
         'day':'2026-10-17','pregame_baseline':base}

class ArchiveConsolidationTests(unittest.TestCase):
 def test_same_fixture_preserves_both_distinct_forecasts(self):
  first=record('espn-bra.1-101','São Paulo','Vasco da Gama',
               base=forecast(37),source='ESPN')
  second=record('fotmob-301','São Paulo','Vasco da Gama',
                base=forecast(46),minute=2)
  saved=copy.deepcopy([first,second])
  groups=consolidate([first,second])
  self.assertEqual(len(groups),1)
  self.assertEqual(groups[0]['variant_count'],2)
  self.assertTrue(groups[0]['forecast_divergence'])
  self.assertEqual({v['pregame_baseline']['forecast']['one_x_two']['home']
                    for v in groups[0]['variants']},{37,46})
  self.assertEqual([first,second],saved,'O histórico fonte permanece intocado')
  self.assertEqual(groups[0]['day'],'2026-10-17')

 def test_finished_record_without_baseline_verifies_both_existing_versions(self):
  rows=[
   record('espn-bra.1-101','São Paulo','Vasco da Gama',
          base=forecast(37),source='ESPN'),
   record('fotmob-301','São Paulo','Vasco da Gama',base=forecast(46)),
   record('score-feed','São Paulo','Vasco da Gama',
          minute=2,phase='finished',score='2-0',base=None)]
  results=consolidate(rows)
  self.assertEqual(len(results),1)
  self.assertEqual(results[0]['score'],'2-0')
  self.assertEqual(results[0]['phase'],'finished')
  for version in results[0]['variants']:
   self.assertEqual(version['pregame_baseline']['settlement']['score'],'2-0')
   self.assertEqual(version['pregame_baseline']['settlement']['count'],3)
   self.assertEqual(version['pregame_baseline']['settlement']['hits'],3)
   self.assertIsNone(rows[0]['pregame_baseline']['settlement'])
   self.assertNotIn('stake',str(version))

 def test_conflicting_final_scores_suspend_both_reports(self):
  rows=[record('es-1','Independiente Medellín','Once Caldas',
               base=forecast(45)),
        record('es-2','Independiente Medellín','Once Caldas',
               minute=1,phase='finished',score='2-0'),
        record('es-3','Independiente Medellín','Once Caldas',
               minute=2,phase='finished',score='1-1')]
  g=consolidate(rows)[0]
  self.assertTrue(g['result_conflict'])
  self.assertEqual(g['score'],'')
  self.assertIsNone(g['variants'][0]['pregame_baseline']['settlement'])

 def test_other_match_same_clubs_different_kickoff_is_not_merged(self):
  rows=[record('a','Casa','Fora',base=forecast()),
        record('b','Casa','Fora',start=START+7200,base=forecast())]
  self.assertEqual(len(consolidate(rows)),2)

 def test_wrong_team_and_unverified_score_never_settles(self):
  rows=[record('a','Casa','Fora',base=forecast()),
        record('b','Casa','Outra',phase='finished',score='5-0'),
        record('c','Casa','Fora',phase='live',score='2-0')]
  g=next(x for x in consolidate(rows) if x['home']=='Casa' and x['away']=='Fora')
  self.assertIsNone(g['pregame_baseline']['settlement'])

 def test_duplicate_id_same_capture_is_kept_once(self):
  row=record('fm-10','Casa','Fora',base=forecast())
  self.assertEqual(consolidate([row,row]) [0]['variant_count'],1)

if __name__=='__main__':
 unittest.main()
