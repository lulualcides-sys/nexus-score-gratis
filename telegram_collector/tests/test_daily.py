import unittest
from telegram_collector.daily import summarize, format_message, strict_quote

class DailyMarketTests(unittest.TestCase):
    def test_distinguishes_sports_results_from_qualified_prices(self):
        sample = {"games": {"g1": {"source": ["FotMob"], "kickoff_unix": 1792900800,
          "observations": [
            {"phase": "scheduled", "odds": [{"market": "over_under_25", "selection":"over",
              "odds": 1.95, "source": "OddsPapi", "bookmaker": "Pinnacle",
              "captured_at": "2026-10-24T12:00:00+00:00", "scope": "pregame"}]},
            {"phase": "finished", "odds": [], "settlement": {"match_odds": "home",
              "total_goals": 3, "both_teams_to_score": True, "total_corners": 11,
              "total_yellow_cards": 5}}]}}}
        result = summarize(sample, "2026-10-25")
        self.assertEqual(result["finished"], 1)
        self.assertEqual(result["results"]["over_2_5_yes"], 1)
        self.assertEqual(result["results"]["btts_yes"], 1)
        self.assertEqual(result["market_families_with_verified_prices"], 1)
        self.assertEqual(result["quotes_verified"], 1)
        self.assertNotIn("profit", result)
        self.assertIn("RESULTADOS CONFIRMADOS", format_message(result))

    def test_rejects_unknown_scope_or_missing_book(self):
        quote = {"market": "1x2", "selection": "home", "odds": 2.1,
                 "source": "x", "bookmaker": "a", "captured_at": "2026-10-24T10:00:00Z",
                 "scope": "unverified_time_scope"}
        self.assertFalse(strict_quote(quote, 1792900800))
        quote["scope"] = "pregame"
        self.assertTrue(strict_quote(quote, 1792900800))
        quote["bookmaker"] = ""
        self.assertFalse(strict_quote(quote, 1792900800))

    def test_no_data_is_not_artificial_profit(self):
        result = summarize({"games": {}}, "2026-10-25")
        self.assertEqual(result["games"], 0)
        self.assertEqual(result["quotes_verified"], 0)
        self.assertIn("Sem ROI ou lucro comprovado", format_message(result))

if __name__ == "__main__":
    unittest.main()
