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


if __name__ == "__main__":
    unittest.main()
