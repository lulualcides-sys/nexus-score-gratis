"""Regressão: o pré-jogo deve usar o secret THE_ODDS_API_KEY já cadastrado."""
import unittest
from pathlib import Path

WF = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "nexus-pregame.yml").read_text(encoding="utf8")


class OddsSecretNames(unittest.TestCase):
    def test_the_odds_api_accepts_existing_secret(self):
        self.assertIn("NEXUS_THE_ODDS_API_KEY: ${{ secrets.NEXUS_THE_ODDS_API_KEY || secrets.THE_ODDS_API_KEY }}", WF)

    def test_other_keys_still_wired(self):
        self.assertIn("NEXUS_API_FOOTBALL_KEY: ${{ secrets.NEXUS_API_FOOTBALL_KEY }}", WF)
        self.assertIn("NEXUS_ODDSPAPI_KEY: ${{ secrets.NEXUS_ODDSPAPI_KEY }}", WF)


if __name__ == "__main__":
    unittest.main()
