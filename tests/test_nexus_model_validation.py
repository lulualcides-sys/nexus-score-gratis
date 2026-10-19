import unittest
from datetime import datetime,timezone
from model_validation import validation_report
T=datetime(2026,10,19,12,tzinfo=timezone.utc).timestamp()
def sample():
 return {'phase':'finished','score':'2-1','start_timestamp':T,'league':'Serie A',
         'variants':[{'pregame_baseline':{'model_status':'experimental_uncalibrated',
            'captured_at':datetime.fromtimestamp(T-600,timezone.utc).isoformat(),
            'forecast':{'one_x_two':{'home':60,'draw':25,'away':15}}}}]}
class ValidationTests(unittest.TestCase):
 def test_brier_and_no_ev_without_robust_sample(self):
  r=validation_report([sample()])
  self.assertEqual(r['eligible'],1)
  self.assertEqual(r['overall']['top_pick_accuracy_pct'],100)
  self.assertFalse(r['validated'])
  self.assertFalse(r['sample_sufficient_for_review'])
 def test_conflict_or_no_result_fails_closed(self):
  a=sample()
  self.assertEqual(validation_report([{**a,'result_conflict':True}])['eligible'],0)
  self.assertEqual(validation_report([{**a,'score':''}])['eligible'],0)
  self.assertEqual(validation_report([{**a,'start_timestamp':T-700}])['eligible'],0)
if __name__=='__main__':unittest.main()
