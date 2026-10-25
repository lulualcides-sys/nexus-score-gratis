import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
import json
from telegram_collector.public_no_key import parse, archive_changes

class PublicNoKeyTests(unittest.TestCase):
    def sample(self):
        return {
            "source": "TipsAudit fair odds",
            "generated_at": "2026-10-25T18:00:00Z",
            "predictions": [{
                "id": 88, "league": "Serie A",
                "home": "A", "away": "B", "kickoff_utc": "2026-10-26T19:00:00Z",
                "fair_odds": {"home": 1.65, "draw": 3.6, "away": 5.1},
                "value": {"selection": "1", "best_soft_odds": 1.71, "bookmaker": "ExampleBook"},
                "fair_read_at": "2026-10-25T17:45:00Z"
            }]
        }

    def test_bookmaker_price_distinct_from_calculated_fair_odds(self):
        out = parse(self.sample())
        self.assertEqual(len(out["matches"]), 1)
        market = out["matches"][0]
        self.assertEqual(market["benchmark_fair_odds"]["home"], 1.65)
        self.assertFalse(market["benchmark_is_bookmaker_price"])
        q = market["best_soft_bookmaker_quote"]
        self.assertEqual(q["price"], 1.71)
        self.assertEqual(q["selection"], "home")
        self.assertEqual(q["price_source_updated_at"], None)
        self.assertIn("unconfirmed", q["verification"])
        self.assertEqual(out["attribution_required"], "https://tipsaudit.com/")

    def test_archive_prices_only_when_changed(self):
        data = parse(self.sample())
        with TemporaryDirectory() as folder:
            target = Path(folder)
            self.assertEqual(archive_changes(data, target), 1)
            self.assertEqual(archive_changes(data, target), 0)
            data["matches"][0]["best_soft_bookmaker_quote"]["price"] = 1.76
            self.assertEqual(archive_changes(data, target), 1)
            files = list(target.glob("tipsaudit-*.json"))
            self.assertEqual(len(files), 1)
            saved = json.loads(files[0].read_text())
            record = next(iter(saved["matches"].values()))
            self.assertEqual(len(record["snapshots"]), 2)
            self.assertEqual(record["snapshots"][0]["bookmaker_quote_indicative"]["price"], 1.71)
            self.assertEqual(record["snapshots"][1]["bookmaker_quote_indicative"]["price"], 1.76)

    def test_no_odd_invented_from_fair_odds(self):
        sample = self.sample()
        sample["predictions"][0].pop("value")
        q = parse(sample)["matches"][0]["best_soft_bookmaker_quote"]
        self.assertIsNone(q)

    def test_invalid_feed_rejected(self):
        with self.assertRaises(ValueError):
            parse({"generated_at": "2026-10-25T18:00:00Z", "predictions": None})
        with self.assertRaises(ValueError):
            parse({"generated_at": "", "predictions": []})

if __name__ == "__main__":
    unittest.main()
