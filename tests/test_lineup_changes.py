"""Aviso de escalação: titulares habituais (>=60% dos últimos jogos, mínimo 3
jogos anteriores) ausentes do XI do jogo. Só com dados reais de escalação."""
import unittest
from lineup_changes import build


def xi(ids, status="confirmed"):
    return {"status": status, "starters": [{"id": str(i), "name": f"J{i}"} for i in ids]}


def game(gid, ts, home_id, lineup, phase="finished"):
    return gid, {"fixture": {"id": gid, "start_timestamp": ts, "home_id": home_id, "away_id": "999",
                             "phase": phase, "home": "Time", "away": "Outro"},
                 "lineups": {"home": lineup}}


class LineupChangesTests(unittest.TestCase):
    def test_missing_habitual_starters(self):
        base = list(range(1, 12))
        rows = dict([game("g0", 50, "7", xi(base)), game("g1", 100, "7", xi(base)), game("g2", 200, "7", xi(base)),
                     game("g3", 300, "7", xi(base[:10] + [20])),
                     game("g4", 400, "7", xi([1, 2, 3, 4, 5, 6, 7, 8, 30, 31, 32]), phase="scheduled")])
        rep = build({"d": {"matches": rows}})
        home = rep["g4"]["home"]
        self.assertEqual(home["prior_games"], 4)
        # J11: 3/4 = 75% < 80% -> não é habitual; J9 e J10: 4/4
        self.assertEqual(sorted(home["missing"]), ["J10", "J9"])
        self.assertNotIn("g1", rep, "sem jogos anteriores suficientes")

    def test_needs_three_prior_games_and_real_lineup(self):
        rows = dict([game("g0", 50, "7", xi(range(1, 12))), game("g1", 100, "7", xi(range(1, 12))), game("g2", 200, "7", xi(range(1, 12))),
                     game("g3", 300, "7", xi(range(20, 31)))])
        self.assertNotIn("g2", build({"d": {"matches": rows}}), "só 3 jogos anteriores")
        rows2 = dict([game("z", 50, "7", xi(range(1, 12))), game("a", 100, "7", xi(range(1, 12))), game("b", 200, "7", xi(range(1, 12))),
                      game("c", 300, "7", xi(range(1, 12))), game("d", 400, "7", {})])
        self.assertNotIn("d", build({"d": {"matches": rows2}}))


if __name__ == "__main__":
    unittest.main()
