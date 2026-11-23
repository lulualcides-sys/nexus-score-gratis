"""Regressão: fila de scouts de jogos encerrados não pode ser monopolizada por
partidas que o FotMob devolve sem estatísticas (ligas menores)."""
import unittest
from datetime import datetime, timezone, timedelta
from finished_scouts import select_pending, mark_empty, EMPTY_RETRY_HOURS, EMPTY_MAX_TRIES

NOW = datetime(2026, 11, 17, 22, 0, tzinfo=timezone.utc)


def row(league_id, start, **extra):
    # Termômetro presente: estes testes isolam a fila de SCOUTS.
    return {"fixture": {"phase": "finished", "league_id": league_id,
                        "league_id_verified": True, "start_timestamp": start},
            "thermometer": {"points": [{"minute": 1, "value": 1}]}, **extra}


class FinishedScoutsQueueTests(unittest.TestCase):
    def test_catalog_leagues_first_then_recent(self):
        docs = {"2026-11-17": {"matches": {
            "fotmob-1": row("9138", 300),   # Segunda Federación (sem catálogo)
            "fotmob-2": row("47", 100),     # Premier League
            "fotmob-3": row("114", 200),    # Amistosos (ampliado)
        }}}
        keys = [k for _, k, _ in select_pending(docs, NOW, 10)]
        self.assertEqual(keys, ["fotmob-2", "fotmob-3", "fotmob-1"])

    def test_recently_empty_is_skipped_until_retry_window(self):
        recent = {"checked_at": (NOW - timedelta(hours=1)).isoformat(), "tries": 1}
        old = {"checked_at": (NOW - timedelta(hours=EMPTY_RETRY_HOURS + 1)).isoformat(), "tries": 1}
        exhausted = {"checked_at": (NOW - timedelta(days=3)).isoformat(), "tries": EMPTY_MAX_TRIES}
        docs = {"2026-11-17": {"matches": {
            "fotmob-1": row("47", 1, scouts_empty=recent),
            "fotmob-2": row("47", 2, scouts_empty=old),
            "fotmob-3": row("47", 3, scouts_empty=exhausted),
            "fotmob-4": row("47", 4),
        }}}
        keys = {k for _, k, _ in select_pending(docs, NOW, 10)}
        self.assertEqual(keys, {"fotmob-2", "fotmob-4"})

    def test_complete_stats_and_non_finished_ignored(self):
        full = {"home": {str(i): i for i in range(6)}, "away": {}}
        docs = {"2026-11-17": {"matches": {
            "fotmob-1": row("47", 1, stats=full),
            "fotmob-2": {"fixture": {"phase": "live", "league_id": "47"}},
            "espn-x-3": row("47", 3),
        }}}
        self.assertEqual(select_pending(docs, NOW, 10), [])

    def test_limit_respected_and_mark_empty_counts(self):
        docs = {"d": {"matches": {f"fotmob-{i}": row("47", i) for i in range(1, 9)}}}
        self.assertEqual(len(select_pending(docs, NOW, 5)), 5)
        target = docs["d"]["matches"]["fotmob-1"]
        mark_empty(target, NOW)
        mark_empty(target, NOW)
        self.assertEqual(target["scouts_empty"]["tries"], 2)
        self.assertEqual(target["scouts_empty"]["checked_at"], NOW.isoformat())


if __name__ == "__main__":
    unittest.main()
