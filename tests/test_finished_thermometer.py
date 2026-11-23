"""Termômetro pós-jogo: a mesma consulta de detalhes dos jogos encerrados
também guarda a pressão por minuto quando o FotMob a publica. Nunca inventa."""
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import finished_scouts as fs

NOW = datetime(2026, 11, 23, 20, 0, tzinfo=timezone.utc)
FULL = {"home": {str(i): i for i in range(6)}, "away": {}}


def row(**extra):
    return {"fixture": {"phase": "finished", "league_id": "47", "league_id_verified": True,
                        "start_timestamp": 100}, **extra}


class FinishedThermometerTests(unittest.TestCase):
    def test_game_with_stats_but_no_thermometer_is_eligible(self):
        docs = {"d": {"matches": {"fotmob-1": row(stats=FULL),
                                  "fotmob-2": row(stats=FULL, thermometer={"points": [{"minute": 1, "value": 5}]})}}}
        self.assertEqual([k for _, k, _ in fs.select_pending(docs, NOW, 10)], ["fotmob-1"])

    def test_momentum_not_published_waits_and_gives_up(self):
        recent = {"checked_at": (NOW - timedelta(hours=1)).isoformat(), "tries": 1}
        done = {"checked_at": (NOW - timedelta(days=2)).isoformat(), "tries": fs.EMPTY_MAX_TRIES}
        docs = {"d": {"matches": {"fotmob-1": row(stats=FULL, momentum_empty=recent),
                                  "fotmob-2": row(stats=FULL, momentum_empty=done)}}}
        self.assertEqual(fs.select_pending(docs, NOW, 10), [])

    def test_apply_saves_real_points_and_marks_missing(self):
        r = row(stats=FULL)
        fs.apply_detail(r, {"home": {}, "away": {}}, [{"minute": 1, "value": 10}, {"minute": 2, "value": -4}], NOW)
        self.assertEqual(len(r["thermometer"]["points"]), 2)
        self.assertEqual(r["thermometer"]["source"], "FotMob pós-jogo")
        r2 = row(stats=FULL)
        fs.apply_detail(r2, {"home": {}, "away": {}}, [], NOW)
        self.assertNotIn("thermometer", r2)
        self.assertEqual(r2["momentum_empty"]["tries"], 1)


if __name__ == "__main__":
    unittest.main()
