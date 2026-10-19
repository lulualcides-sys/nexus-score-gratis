import unittest
from model_validation import validation_report

class ModelCalibrationSafetyTests(unittest.TestCase):
    def test_missing_sample_does_not_invent_calibration(self):
        report=validation_report([])
        self.assertFalse(report['validated'])
        self.assertIsNone(report['calibration_error_pct'])
        self.assertIsNone(report['overall']['skill_vs_uniform'])
    def test_valid_frozen_predictions_have_audit_metrics_but_no_ev_release(self):
        rows=[]
        for n in range(8):
            rows.append({'id':str(n),'phase':'finished','score':'1-0',
                         'league':'Brazil Série A','start_timestamp':1792000000,
                         'variants':[{'pregame_baseline':{
                           'captured_at':'2026-10-01T12:00:00+00:00',
                           'model_status':'experimental_uncalibrated',
                           'forecast':{'one_x_two':{'home':52,'draw':28,'away':20}}}}]})
        result=validation_report(rows)
        self.assertEqual(result['overall']['n'],8)
        self.assertIsNotNone(result['overall']['uniform_baseline_brier'])
        self.assertIsNotNone(result['calibration_error_pct'])
        self.assertFalse(result['validated'])
        self.assertFalse(result['sample_sufficient_for_review'])

if __name__=='__main__':unittest.main()
