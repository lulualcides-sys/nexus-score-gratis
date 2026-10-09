import unittest
from archive_understat import normalized
class ArchiveTests(unittest.TestCase):
    def sample(self,**kwargs):
        s={"game_id":123456,"date":"2026-04-14T19:00:00Z",
           "home_team":"Arsenal","away_team":"Chelsea",
           "home_goals":2,"away_goals":1,"home_xg":1.68,
           "away_xg":0.75,"is_result":True}
        s.update(kwargs)
        return s
    def test_xg_and_result_from_completed_match_only(self):
        result=normalized([self.sample(),self.sample(game_id=123457,is_result=False)])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["home_xg"],1.68)
        self.assertEqual(result[0]["away_xg"],0.75)
    def test_bad_or_missing_xg_is_omitted(self):
        self.assertEqual(normalized([self.sample(away_xg=None),
            self.sample(home_xg=float("nan"))]),[])
    def test_id_conflict_rejected(self):
        with self.assertRaises(ValueError):
            normalized([self.sample(),self.sample(away_xg=2.5)])
    def test_wrong_season_and_unfinished_match_excluded(self):
        self.assertEqual(normalized([self.sample(date="2026-08-01"),
             self.sample(is_result=False)]),[])
if __name__=="__main__":unittest.main()
