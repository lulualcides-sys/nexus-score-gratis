"""Odds de Mais/Menos 2,5 e Ambas marcam: extraídas do mesmo pacote API-Football
(sem consulta extra), congeladas antes do início e contadas na evidência."""
import unittest
from datetime import datetime, timezone
from api_football_odds import goal_markets
from pregame_audit import market_snapshot
from market_evidence import audit_markets

NOW = int(datetime(2026, 11, 23, 12, tzinfo=timezone.utc).timestamp())
KICK = NOW + 3600


def packet(update_ts=NOW - 60):
    return {"response": [{"fixture": {"id": 7},
            "update": datetime.fromtimestamp(update_ts, timezone.utc).isoformat(),
            "bookmakers": [{"name": "Casa", "bets": [
                {"id": 1, "name": "Match Winner", "values": [
                    {"value": "Home", "odd": "2.0"}, {"value": "Draw", "odd": "3.3"},
                    {"value": "Away", "odd": "3.6"}]},
                {"id": 5, "name": "Goals Over/Under", "values": [
                    {"value": "Over 1.5", "odd": "1.3"}, {"value": "Under 1.5", "odd": "3.4"},
                    {"value": "Over 2.5", "odd": "1.95"}, {"value": "Under 2.5", "odd": "1.85"}]},
                {"id": 8, "name": "Both Teams Score", "values": [
                    {"value": "Yes", "odd": "1.8"}, {"value": "No", "odd": "1.95"}]}]}]}]}


class GoalMarketsTests(unittest.TestCase):
    def test_extracts_only_complete_25_and_btts(self):
        got = {m: (p, b) for m, p, b, _ in goal_markets(packet(), 7, NOW)}
        self.assertEqual(got["over_under_25"][0], {"over": 1.95, "under": 1.85})
        self.assertEqual(got["btts"][0], {"yes": 1.8, "no": 1.95})
        self.assertEqual(set(got), {"over_under_25", "btts"})
        self.assertEqual(goal_markets(packet(update_ts=NOW + 999), 7, NOW), [])
        self.assertEqual(goal_markets(packet(), 8, NOW), [])

    def test_snapshot_only_before_kickoff_and_complete(self):
        at = datetime.fromtimestamp(NOW - 120, timezone.utc).isoformat()
        late = datetime.fromtimestamp(KICK + 60, timezone.utc).isoformat()
        row = {"market_quotes": [
            {"market": "btts", "selection": "yes", "odds": 1.8, "bookmaker": "C", "source": "S", "captured_at": at},
            {"market": "btts", "selection": "no", "odds": 1.95, "bookmaker": "C", "source": "S", "captured_at": at},
            {"market": "over_under_25", "selection": "over", "odds": 1.9, "bookmaker": "C", "source": "S", "captured_at": at},
            {"market": "btts", "selection": "yes", "odds": 9.0, "bookmaker": "C", "source": "S", "captured_at": late},
            {"market": "btts", "selection": "no", "odds": 9.0, "bookmaker": "C", "source": "S", "captured_at": late}]}
        snap = market_snapshot(row, NOW, KICK, "btts")
        self.assertEqual(snap["prices"], {"yes": 1.8, "no": 1.95})
        self.assertIsNone(market_snapshot(row, NOW, KICK, "over_under_25"), "pacote incompleto")

    def test_evidence_counts_priced_goal_markets(self):
        row = {"id": "f1", "pregame_baseline": {
            "model_status": "experimental_uncalibrated",
            "indications": [{"market": "btts", "selection": "yes", "probability": 60.0},
                            {"market": "over_under_25", "selection": "under", "probability": 55.0}],
            "market_odds": {"btts": {"prices": {"yes": 1.9, "no": 1.9}, "recent_at_check": True}},
            "settlement": {"status": "finished", "checks": [
                {"market": "btts", "selection": "yes", "result": "hit"},
                {"market": "over_under_25", "selection": "under", "result": "miss"}]}}}
        m = {x["market"]: x for x in audit_markets([row])["markets"]}
        self.assertEqual(m["btts"]["with_price"], 1)
        self.assertEqual(m["btts"]["theoretical_positive"], 1)
        self.assertEqual(m["over_under_25"]["with_price"], 0)


if __name__ == "__main__":
    unittest.main()
