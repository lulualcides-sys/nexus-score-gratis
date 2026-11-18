"""Regressão: escopo Python (sinais/30-70) usa ID FotMob quando existir."""
import unittest
from major_league_scope import league_id, major_men


class LeagueScopeIdTests(unittest.TestCase):
    def test_same_name_other_countries_rejected(self):
        self.assertEqual(league_id("Premier League", "47"), "premier")
        for fid in ("522", "263", "441", "63", "9066", "116", "529"):
            self.assertIsNone(league_id("Premier League", fid), fid)
        self.assertIsNone(league_id("Ligue 1", "516"))
        self.assertIsNone(league_id("Bundesliga", "38"))
        self.assertIsNone(league_id("CAF Champions League Qualification", "10619"))

    def test_brazil_series_by_id_and_accent(self):
        self.assertEqual(league_id("Série A", "268"), "br_a")
        self.assertEqual(league_id("Série A"), "br_a")
        self.assertEqual(league_id("Série B", "8814"), "br_b")
        self.assertEqual(league_id("Série B"), "br_b")
        self.assertEqual(league_id("Serie A", "55"), "italy")

    def test_women_youth_second_division_rejected(self):
        for name in ("Liga MX Femenil Apertura", "Eredivisie Vrouwen",
                     "Liga Portugal 2", "Premier League U18", "Premier League 2"):
            self.assertIsNone(league_id(name), name)
        self.assertIsNone(league_id("Liga MX Femenil Apertura", "9906"))

    def test_major_men_reads_row_league_id(self):
        self.assertTrue(major_men({"league": "Premier League", "league_id": "47",
                                   "home": "Arsenal", "away": "Chelsea"}))
        self.assertFalse(major_men({"league": "Premier League", "league_id": "522",
                                    "home": "Hearts of Oak", "away": "Samartex"}))
        # Linhas antigas sem ID continuam pelo nome.
        self.assertTrue(major_men({"league": "LaLiga", "home": "A", "away": "B"}))


if __name__ == "__main__":
    unittest.main()
