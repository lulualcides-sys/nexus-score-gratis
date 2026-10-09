import json
import tempfile
import unittest
from pathlib import Path
from probe import normalise,evaluate,current_teams,evaluate_understat

class SafeProbeTests(unittest.TestCase):
    def test_accents_are_normalised_but_clubs_not_guessed(self):
        self.assertEqual(normalise("São Paulo FC"),"sao paulo fc")
        self.assertNotEqual(normalise("Manchester United"),normalise("Man City"))
    def test_only_exact_unique_matches(self):
        rows=[{"team":"São Paulo FC","elo":1699},
              {"team":"São Paulo FC","elo":1701},
              {"team":"Santos","elo":1552},
              {"team":"Chelsea","elo":None},
              {"team":"Arsenal","elo":1800}]
        result=evaluate(rows,{"sao paulo fc","santos","arsenal","man city"})
        self.assertEqual(result["matched_teams"],2)
        self.assertNotIn("sao paulo fc",result["examples"])
        self.assertEqual(result["match_rate_pct"],50.0)
    def test_history_is_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder)
            p=d/"2026-10-09.json"
            p.write_text(json.dumps({"matches":{"x":{"fixture":{
                "home":"Arsenal","away":"Chelsea"}}}}))
            before=p.read_bytes()
            found=current_teams(d)
            self.assertEqual(found,{"arsenal","chelsea"})
            self.assertEqual(p.read_bytes(),before)
    def test_understat_xg_needs_two_verified_fields(self):
        data=[{"home_xg":1.25,"away_xg":0.83},
              {"home_xg":None,"away_xg":1.15},
              {"home_xg":float("nan"),"away_xg":0.4},
              {"home_xg":-2,"away_xg":0.4}]
        s=evaluate_understat(data)
        self.assertEqual(s["rows"],4)
        self.assertEqual(s["with_both_verified_xg"],1)
    def test_invalid_ratings_rejected(self):
        result=evaluate([{"team":"A","elo":float("nan")},
                         {"team":"B","elo":1000},
                         {"team":"C","elo":2900},
                         {"team":"D","elo":0}],{"a","b","c","d"})
        self.assertEqual(result["matched_teams"],2)
if __name__=="__main__":unittest.main()
