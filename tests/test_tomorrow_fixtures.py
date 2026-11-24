"""Regressão: jogos de AMANHÃ precisam entrar no histórico para a previsão
pré-jogo ser congelada antes do apito (302 jogos com dados completos ficaram
sem previsão porque só entravam no histórico no próprio dia)."""
import json
import tempfile
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import fotmob_three_days as ftd

BR = timezone(timedelta(hours=-3))


class TomorrowFixturesTests(unittest.TestCase):
    def test_tomorrow_games_are_stored(self):
        today = date.fromisoformat(ftd.DAY)
        tomorrow = today + timedelta(days=1)
        kick = int(datetime.combine(tomorrow, time(16, 0), BR).timestamp())
        game = {"id": "fotmob-123", "home": "A", "away": "B", "phase": "scheduled",
                "start_timestamp": kick, "league": "Premier League", "score": "?-?"}
        with tempfile.TemporaryDirectory() as d, \
                patch.object(ftd, "HISTORY", Path(d)), \
                patch.object(ftd, "fotmob_list", lambda day: [game]):
            ftd.run()
            saved = json.loads((Path(d) / (tomorrow.isoformat() + ".json")).read_text())
        self.assertIn("fotmob-123", saved["matches"])

    def test_form_collectors_include_tomorrow(self):
        for mod in ("team_form.py", "fotmob_form.py"):
            src = Path(__file__).resolve().parent.parent.joinpath(mod).read_text(encoding="utf8")
            self.assertIn("timedelta(days=1)", src, mod)


if __name__ == "__main__":
    unittest.main()
