import unittest
from datetime import datetime,timedelta,timezone

from telegram_collector.model_backtest import assessment,evaluate
from telegram_collector.model_only import make_probability_book

NOW=datetime(2026,10,25,14,0,tzinfo=timezone.utc)


class IndependentBacktestTests(unittest.TestCase):
    def test_scoring_proper_rules_always_nonnegative(self):
        m=make_probability_book(1.8,1.0,.44)
        for score in ((2,0),(0,1),(1,1),(3,2)):
            metrics=assessment(m,*score)
            self.assertEqual(len(metrics),5)
            self.assertTrue(all(v>=0 for v in metrics))
            self.assertTrue(metrics[1]<=1)
            self.assertTrue(metrics[3]<=1)

    def test_walk_forward_uses_only_prior_fixture_dates(self):
        rows=[]
        for k in range(95):
            date=(NOW-timedelta(days=95-k)).date()
            home,away=("Arsenal","Chelsea") if k%2==0 else ("Chelsea","Arsenal")
            full=((1,1) if k%3==0 else (2,1))
            half=(1,0)
            rows.append({"league":"eng.1","home":home.lower(),"away":away.lower(),
                         "date":date,"ft":full,"ht":half,
                         "source":"test"})
        a=evaluate(rows,NOW)
        self.assertEqual(a["historical_matches_available"],95)
        self.assertGreater(a["historical_fixtures_tested"],0)
        self.assertLessEqual(a["historical_fixtures_tested"],20)
        self.assertTrue(a["walk_forward"])
        self.assertFalse(a["uses_future_results_in_training"])
        self.assertIsNotNone(a["brier_1x2"])
        self.assertIsNotNone(a["rps_1x2"])
        rows.extend([{"league":"eng.1","home":"Arsenal","away":"Chelsea",
                      "date":(NOW+timedelta(days=7)).date(),"ft":(12,0),
                      "ht":(8,0),"source":"test"}])
        b=evaluate(rows,NOW)
        self.assertEqual(a["rps_1x2"],b["rps_1x2"])
        self.assertEqual(a["historical_fixtures_tested"],b["historical_fixtures_tested"])

    def test_too_few_matches_never_claim_validation(self):
        rows=[{"league":"eng.1","home":"a","away":"b",
               "date":(NOW-timedelta(days=k)).date(),
               "ft":(1,0),"ht":(1,0),"source":"test"} for k in range(1,12)]
        result=evaluate(rows,NOW)
        self.assertEqual(result["status"],"insufficient_backtest_sample")
        self.assertIsNone(result["brier_1x2"])


if __name__=="__main__":
    unittest.main()
