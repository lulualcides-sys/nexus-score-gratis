import unittest
from telegram_collector.collect import normalize_quotes, settle_markets, observation, ingest_games, MARKET_FAMILIES
from tempfile import TemporaryDirectory
from pathlib import Path
import json

class MarketCollectorTests(unittest.TestCase):
    def test_all_market_families_kept_even_without_prices(self):
        self.assertIn("total_corners", MARKET_FAMILIES)
        self.assertIn("match_odds", MARKET_FAMILIES)
        self.assertIn("half_time", MARKET_FAMILIES)
        self.assertIn("asian_handicap", MARKET_FAMILIES)

    def test_quotes_use_real_price_source_and_timestamp(self):
        game = {"odds": [{"sel": "home", "odd": 2.05, "source": "ESPN", "at": "2026-10-25T10:00:00+00:00"}],
                "odds_comparison": [{"market": "1x2", "selection": "away", "best": {"odds": 3.1, "source": "ESPN", "at": "2026-10-25T09:30:00+00:00"}}]}
        quotes = normalize_quotes(game)
        self.assertEqual(len(quotes), 2)
        self.assertEqual(quotes[0]["market"], "1x2")
        self.assertEqual(quotes[0]["odds"], 2.05)
        self.assertEqual(quotes[0]["captured_at"], "2026-10-25T10:00:00+00:00")

    def test_finished_without_stats_does_not_invent_corner_outcome(self):
        g = {"phase": "finished", "score": "2-1", "stats": {}}
        m = settle_markets(g)
        self.assertEqual(m["match_odds"], "home")
        self.assertEqual(m["total_goals"], 3)
        self.assertNotIn("total_corners", m)

    def test_live_game_never_settled(self):
        self.assertEqual(settle_markets({"phase": "live", "score": "2-0"}), {})

    def test_confirmed_stats_include_corners_shots_cards(self):
        g = {"phase": "finished", "score": "1-1", "stats": {"home": {"corners": 3, "shots_on": 2, "yellow_cards": 1},
                                                             "away": {"corners": 6, "shots_on": 5, "yellow_cards": 3}}}
        m = settle_markets(g)
        self.assertEqual(m["total_corners"], 9)
        self.assertEqual(m["total_shots_on_target"], 7)
        self.assertEqual(m["total_yellow_cards"], 4)

    def test_dedupe_and_preserve_snapshot_changes(self):
        g = {"id": "fixture-A", "day": "2026-10-25", "home": "Casa", "away": "Fora",
             "phase": "live", "minute": 40, "score": "0-0", "stats": {}, "odds": []}
        with TemporaryDirectory() as root:
            a = ingest_games([g], Path(root), "2026-10-25T12:00:00Z")
            b = ingest_games([g], Path(root), "2026-10-25T12:05:00Z")
            g["minute"] = 41
            c = ingest_games([g], Path(root), "2026-10-25T12:10:00Z")
            self.assertEqual((a, b, c), (1, 0, 1))
            file = json.loads((Path(root) / "2026-10-25.json").read_text())
            self.assertEqual(len(file["games"]["fixture-A"]["observations"]), 2)

    def test_no_derived_prices_or_ev(self):
        s = observation({"phase": "scheduled", "odds": [], "stats": {}}, "2026-10-25T12:00:00Z")
        self.assertEqual(s["odds"], [])
        self.assertNotIn("ev", s)
        self.assertEqual(s["settlement"], {})

if __name__ == "__main__":
    unittest.main()
