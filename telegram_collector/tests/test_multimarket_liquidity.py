import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from telegram_collector.collect import (
    normalize_liquidity, augment_from_nexus_history, normalize_quotes,
    ingest_games,
)

class MultimarketLiquidityTests(unittest.TestCase):
    def test_liquidity_requires_proven_brl_exchange_volume(self):
        liq = {"amount": 3500, "currency": "BRL", "kind": "matched_volume",
               "source": "Authorized Exchange", "observed_at": "2026-10-25T10:00:00Z"}
        self.assertEqual(normalize_liquidity({"liquidity": liq})["status"], "qualified")
        self.assertEqual(normalize_liquidity({"liquidity": {**liq, "amount": 2999}})["status"], "below")
        self.assertEqual(normalize_liquidity({"liquidity": {**liq, "currency": "GBP"}})["status"], "unknown")
        self.assertEqual(normalize_liquidity({"liquidity": {**liq, "source": ""}})["status"], "unknown")
        self.assertEqual(normalize_liquidity({"liquidity": {**liq, "amount": 500000}})["status"], "qualified")
        self.assertEqual(normalize_liquidity({"odds": [{"odd": 1.9} ]})["status"], "unknown")

    def test_history_enrichment_recovers_additional_games_and_bookmakers(self):
        day = "2026-10-25"
        with TemporaryDirectory() as folder:
            path = Path(folder)
            record = {"matches": {"test-1": {"fixture": {
                "id": "test-1", "home": "A", "away": "B", "league": "Sample",
                "phase": "scheduled", "score": "0-0", "start_timestamp": 1792900800,
                "source": "FotMob", "collected_at": "2026-10-25T10:00:00Z"},
                "market_quotes": [
                    {"market": "over_under_25", "selection": "over",
                     "odds": 1.9, "source": "OddsPapi", "bookmaker": "Pinnacle",
                     "captured_at": "2026-10-25T09:00:00Z"},
                    {"market": "over_under_25", "selection": "over",
                     "odds": 1.86, "source": "OddsPapi", "bookmaker": "Bet365",
                     "captured_at": "2026-10-25T09:00:00Z"}
                ]
            }}}
            (path / (day + ".json")).write_text(json.dumps(record))
            games = augment_from_nexus_history([], path, "2026-10-25T14:00:00Z")
            self.assertEqual(len(games), 1)
            self.assertEqual(len(normalize_quotes(games[0])), 2)
            self.assertEqual({q["bookmaker"] for q in normalize_quotes(games[0])},
                             {"Pinnacle", "Bet365"})
            self.assertEqual(ingest_games(games, path / "archive", "2026-10-25T14:00:00Z"), 1)
            stored = json.loads((path / "archive" / (day + ".json")).read_text())
            self.assertEqual(len(stored["games"]["test-1"]["observations"][0]["odds"]), 2)
            self.assertEqual(stored["games"]["test-1"]["observations"][0]["liquidity"]["status"], "unknown")

if __name__ == "__main__":
    unittest.main()
