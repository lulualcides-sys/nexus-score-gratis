import unittest
from datetime import date
from telegram_collector.predictive_validation import (
    league_prior, shadow, score, reliability, report,
)


def row(day, ft, league="bra.1"):
    return {"league":league,"home":"home","away":"away",
            "date":date(2026,10,day),"ft":ft,"ht":None}


class PredictiveValidationTests(unittest.TestCase):
    def test_prior_is_strictly_past_including_same_day_guard(self):
        x = [row(i, (1, 0)) for i in range(1,21)]
        x.extend([row(21, (0, 10)) for _ in range(10)])
        before = league_prior(x, "bra.1", date(2026,10,21))
        self.assertEqual(before["training_games"],20)
        self.assertGreater(before["ft"]["1"], .75)
        self.assertAlmostEqual(sum(before["ft"].values()),1)
        self.assertIsNone(league_prior(x[:18], "bra.1", date(2026,10,21)))

    def test_shadow_preserves_simplex_without_changing_inputs(self):
        a = {"ft":{"1":.5,"X":.3,"2":.2},"over_2_5":.6,"btts":.5}
        b = {"ft":{"1":.3,"X":.3,"2":.4},"over_2_5":.4,"btts":.4}
        blended = shadow(a,b)
        self.assertAlmostEqual(blended["ft"]["1"],.46)
        self.assertAlmostEqual(sum(blended["ft"].values()),1)
        self.assertEqual(a["ft"]["1"],.5)
        self.assertGreater(score(a,(2,0))["brier_1x2"],0)
        with self.assertRaises(ValueError):
            shadow(a,b,1.5)

    def test_paired_comparison_has_reliability_and_no_promotion(self):
        a = {"ft":{"1":.5,"X":.3,"2":.2},"over_2_5":.6,"btts":.5}
        b = {"ft":{"1":.4,"X":.3,"2":.3},"over_2_5":.5,"btts":.4}
        result = report([("bra.1",(2,1),a,b)]*40)
        self.assertEqual(result["paired_matches"],40)
        self.assertEqual(result["metrics"]["poisson_original"]["n"],40)
        self.assertEqual(result["metrics"]["league_blend_20pct_shadow"]["n"],40)
        self.assertFalse(result["promotion_allowed"])
        self.assertTrue(result["production_model_unchanged"])
        self.assertEqual(result["metrics"]["poisson_original"]["calibration_btts"]["bins"][2]["n"],40)
        self.assertAlmostEqual(result["metrics"]["poisson_original"]["calibration_over_2_5"]["ece"],.4)
        self.assertEqual(report([])["status"],"insufficient_paired_sample")


if __name__ == "__main__":
    unittest.main()
