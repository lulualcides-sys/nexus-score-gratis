import unittest
from major_league_scope import league_id, major_men


class MajorMenLeagueTests(unittest.TestCase):
    def test_brazil_a_and_b_are_distinct(self):
        for name in ("Brasileirão Série A","Campeonato Brasileiro Série A",
                     "Brazil Serie A","Brazilian Serie A"):
            self.assertEqual(league_id(name),"br_a",name)
        for name in ("Brasileirão Série B","Campeonato Brasileiro Série B",
                     "Brazilian Serie B","Serie B do Brasil"):
            self.assertEqual(league_id(name),"br_b",name)

    def test_keep_other_major_mens_and_reject_womens_leagues(self):
        for name in ("Premier League","La Liga","Serie A","Bundesliga",
                     "Ligue 1","UEFA Champions League","Copa Libertadores"):
            self.assertIsNotNone(league_id(name),name)
        for name in ("Women's Champions League","Brasileirão Feminino",
                     "NWSL","Serie A Femminile","Liga F",
                     "U20 Bundesliga","Friendly"):
            self.assertIsNone(league_id(name),name)

    def test_requested_four_competitions_and_espn_ids(self):
        aliases={
            "saudi":["Saudi Pro League","Saudi Professional League",
                     "Roshn Saudi League","ksa.1"],
            "conference":["UEFA Conference League","UEFA Europa Conference League",
                          "uefa.europa.conf"],
            "championship":["EFL Championship","English Championship","Championship",
                            "eng.2"],
            "eerste":["Eerste Divisie","Keuken Kampioen Divisie",
                      "Dutch Eerste Divisie","ned.2"],
        }
        for key,names in aliases.items():
            for name in names:
                self.assertEqual(league_id(name),key,name)
                self.assertTrue(major_men({"league":name,"home":"A","away":"B"}),name)
        for name in ("Women's UEFA Conference League","Saudi Women's League",
                     "Dutch Tweede Divisie","Conference North","English League One"):
            self.assertIsNone(league_id(name),name)

    def test_womens_teams_rejected_even_in_major_league(self):
        self.assertFalse(major_men({"league":"Premier League",
                         "home":"Arsenal Women","away":"Chelsea Women"}))
        self.assertFalse(major_men({"league":"Brasileirão Série A",
                         "gender":"female","home":"Casa","away":"Fora"}))
        self.assertTrue(major_men({"league":"Brasileirão Série B",
                         "home":"Santos","away":"Ceará"}))


if __name__=="__main__":
    unittest.main()
