"""Odds pré-jogo: ESPN (grátis) busca jogos até 30 h à frente, incluindo amanhã."""
import unittest
from pathlib import Path
import pregame_refresh as pr


class OddsWindowTests(unittest.TestCase):
    def test_espn_window_covers_tomorrow(self):
        now = 1_800_000_000
        docs = {"d": {"matches": {
            "a": {"fixture": {"phase": "scheduled", "start_timestamp": now + 3 * 3600}},
            "b": {"fixture": {"phase": "scheduled", "start_timestamp": now + 20 * 3600}},
            "c": {"fixture": {"phase": "scheduled", "start_timestamp": now + 40 * 3600}}}}}
        short = {k for _, k, _ in pr.fixture_candidates(docs, now, lookahead=6 * 3600)}
        long = {k for _, k, _ in pr.fixture_candidates(docs, now, lookahead=pr.ESPN_LOOKAHEAD)}
        self.assertEqual(short, {"a"})
        self.assertEqual(long, {"a", "b"})

    def test_tomorrow_always_loaded(self):
        src = Path(pr.__file__).read_text(encoding="utf8")
        self.assertIn("days.append(today+timedelta(days=1))", src)
        self.assertNotIn("if local_hour>=18:days.append", src)
        self.assertIn("espn_scoreboard_odds(docs,espn_candidates,now_ts)", src)


if __name__ == "__main__":
    unittest.main()
