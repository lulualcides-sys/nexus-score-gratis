import unittest
from datetime import datetime, timezone
from experiments.openfootball_cc0_probe import score_crosscheck, summary

TS=int(datetime(2026,10,9,19,0,tzinfo=timezone.utc).timestamp())
F={'id':'test-1','home':'Arsenal','away':'Chelsea','league_code':'eng.1',
   'start_timestamp':TS,'phase':'finished','score':'2-1'}
ROWS=[
 {'date':'2026-10-09','team1':'Arsenal FC','team2':'Chelsea FC','score':{'ft':[2,1]}},
 {'date':'2026-10-09','team1':'Arsenal FC','team2':'Tottenham Hotspur FC','score':{'ft':[4,0]}},
 {'date':'2026-10-10','team1':'Arsenal FC','team2':'Chelsea FC','score':{'ft':[7,3]}},
 {'date':'2026-10-09','team1':'Arsenal FC','team2':'Chelsea FC','score':[0,0]}
]
class CC0CrosscheckTests(unittest.TestCase):
 def test_correct_result_with_strict_identity_and_day(self):
  self.assertEqual(score_crosscheck(F,ROWS)['status'],'cross_verified')
 def test_mismatch_is_a_conflict_not_verification(self):
  self.assertEqual(score_crosscheck({**F,'score':'1-0'},ROWS)['status'],'conflict')
 def test_pending_and_missing_score_never_verified(self):
  self.assertEqual(score_crosscheck({**F,'phase':'live'},ROWS)['status'],'unsettled')
  self.assertEqual(score_crosscheck({**F,'score':'—'},ROWS)['status'],'unavailable')
 def test_two_explicit_same_fixture_rows_are_ambiguous(self):
  duplicated=[ROWS[0],ROWS[0].copy()]
  self.assertEqual(score_crosscheck(F,duplicated)['status'],'ambiguous')
 def test_other_fixture_not_associated_by_similar_team_name(self):
  self.assertEqual(score_crosscheck({**F,'home':'Arsenal Tula'},ROWS)['status'],'unmatched')
 def test_summary_does_not_invent_coverage(self):
  batch=summary([F,{**F,'id':'test-2','score':'1-0'}],{'eng.1':ROWS})
  self.assertEqual(batch['checked'],2)
  self.assertEqual(batch['cross_verified'],1)
  self.assertEqual(batch['conflict'],1)
  self.assertEqual(batch['source'],'OpenFootball CC0')

if __name__=='__main__':unittest.main()
