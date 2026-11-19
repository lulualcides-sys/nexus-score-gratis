"""Regressão: duas partidas com o mesmo horário de início derrubavam o job
(TypeError ao comparar dicts) e impediam salvar as odds pré-jogo."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from oddspapi_historical import collect


class HistoricalSortTests(unittest.TestCase):
    def test_same_kickoff_does_not_crash(self):
        kick = int(datetime(2026, 11, 17, 19, 0, tzinfo=timezone.utc).timestamp())
        now = kick + 6 * 3600

        def match(ident, home):
            return {"oddspapi_fixture_id": ident,
                    "fixture": {"phase": "finished", "start_timestamp": kick, "home": home}}
        # Mesmo ID OddsPapi em duas linhas (fontes duplicadas), conteúdo diferente.
        docs = {"2026-11-17": {"matches": {"a": match("id1", "A"), "b": match("id1", "B")}}}
        with tempfile.TemporaryDirectory() as d:
            out = collect(docs, now, key="k", fetcher=lambda url: {}, enabled=True,
                          ledger_path=Path(d) / "h.json", sleep_fn=lambda s: None)
        self.assertIsInstance(out, dict)
        self.assertEqual(out["requests"], 1, "ID duplicado consultado uma vez só")


if __name__ == "__main__":
    unittest.main()
