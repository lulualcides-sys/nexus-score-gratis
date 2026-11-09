import unittest
from datetime import date, datetime, timezone
from telegram_collector.league_stats import summarize


NOW = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)


def fixture(day, score, ht=None, league="eng.1"):
    return {"league": league, "home": "home", "away": "away",
            "date": date(2026, 10, day), "ft": score, "ht": ht,
            "source": "test"}


class LeagueStatsTests(unittest.TestCase):
    def test_dedup_future_and_ht_coverage_are_truthful(self):
        rows = [fixture(1, (2, 1), (1, 0)), fixture(1, (2, 1), (1, 0)),
                fixture(2, (0, 0)), fixture(3, (1, 2), (0, 1))]
        rows.append({"league":"eng.1","home":"home","away":"away",
                     "date":date(2026,11,10),"ft":(9,9),"ht":(5,5)})
        x = summarize(rows, NOW)
        self.assertEqual(x["unique_finished_matches"], 3)
        self.assertEqual(x["half_time_available"], 2)
        l = x["leagues"][0]["all"]
        self.assertEqual(l["matches"], 3)
        self.assertEqual(l["ft_1x2"]["home"], 1)
        self.assertEqual(l["ft_1x2"]["draw"], 1)
        self.assertEqual(l["ft_1x2"]["away"], 1)
        self.assertEqual(l["ht"]["available_matches"], 2)
        self.assertEqual(l["ht"]["over_0_5_pct"], 100)
        self.assertEqual(l["goals_ft"]["over_2_5_pct"], 66.67)
        self.assertIsNone(x["leagues"][0]["recent"])

    def test_league_recent_window_and_invalid_ht_rejected(self):
        rows = []
        for i in range(21):
            rows.append({"league": "bra.1", "home": "h"+str(i), "away": "a"+str(i),
                         "date": date(2026, 10, i+1),
                         "ft": (1, 0) if i == 0 else (2, 1), "ht": None})
        x = summarize(rows, NOW)["leagues"][0]
        self.assertEqual(x["all"]["matches"], 21)
        self.assertEqual(x["recent"]["matches"], 20)
        self.assertEqual(x["all"]["ht"]["coverage_pct"], 0)
        self.assertIsNone(x["all"]["ht"]["over_0_5_pct"])
        rows[0]["ht"] = (2, 0)
        with self.assertRaises(ValueError):
            summarize(rows, NOW)


if __name__ == "__main__":
    unittest.main()
