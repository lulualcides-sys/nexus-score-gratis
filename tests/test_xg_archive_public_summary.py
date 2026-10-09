import unittest
import web_export as web
class HistoricalXgTests(unittest.TestCase):
    def test_summary_safe(self):
        doc={"ready_for_research":True,"integrated_into_live_ev":False,
             "source":"soccerdata Understat","season":"2025/2026",
             "games_with_home_away_xg":380,"raw_games":[{"private":"irrelevante"}]}
        result=web.historical_xg_summary(doc)
        self.assertTrue(result["available"])
        self.assertEqual(result["matches_verified"],380)
        self.assertNotIn("raw_games",result)
        self.assertFalse(result["live_xg"])
        self.assertFalse(result["ev_plus"])
    def test_missing_or_forged_source(self):
        self.assertFalse(web.historical_xg_summary({})["available"])
        self.assertFalse(web.historical_xg_summary({
            "ready_for_research":True,"integrated_into_live_ev":False,
            "source":"Outros","season":"2025/2026",
            "games_with_home_away_xg":380})["available"])
if __name__=="__main__":unittest.main()
