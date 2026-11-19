"""Regressão: tabelas de liga do catálogo antes de amistosos/copas sem tabela."""
import unittest
from standings_context import league_priority


def games(day, key, rank=4):
    return [(rank, day, key)]


DOCS = {"d": {"matches": {k: {"fixture": {"league_id_verified": True}}
                          for k in ("a", "b", "c", "e")}}}


class StandingsPriorityTests(unittest.TestCase):
    def test_order(self):
        targets = {"114": games("d", "a"), "9138": games("d", "b"),
                   "47": games("d", "c"), "71": games("d", "e")}
        order = sorted(targets, key=lambda lid: league_priority(lid, targets[lid], DOCS, {}))
        self.assertEqual(order, ["47", "71", "9138", "114"])

    def test_live_still_first(self):
        targets = {"47": games("d", "c"), "9138": games("d", "b", rank=0)}
        order = sorted(targets, key=lambda lid: league_priority(lid, targets[lid], DOCS, {}))
        self.assertEqual(order[0], "9138")


class NoTableMemoryTests(unittest.TestCase):
    def test_recent_no_table_is_skipped_for_24h(self):
        from datetime import datetime, timezone, timedelta
        from standings_context import skip_no_table, NO_TABLE_HOURS
        now = datetime(2026, 11, 19, 1, 0, tzinfo=timezone.utc)
        memory = {"9213": (now - timedelta(hours=2)).isoformat(),
                  "9545": (now - timedelta(hours=NO_TABLE_HOURS + 1)).isoformat(),
                  "bad": "x", "268": (now - timedelta(hours=1)).isoformat(),
                  "114": (now - timedelta(hours=1)).isoformat()}
        self.assertTrue(skip_no_table("9213", memory, now))
        self.assertFalse(skip_no_table("9545", memory, now))
        self.assertFalse(skip_no_table("bad", memory, now))
        self.assertFalse(skip_no_table("47", memory, now))
        self.assertFalse(skip_no_table("268", memory, now), "Brasileirão sempre tenta de novo")
        self.assertTrue(skip_no_table("114", memory, now), "amistosos não têm tabela")


if __name__ == "__main__":
    unittest.main()
