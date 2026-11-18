"""Os IDs de liga do site (JS) e do coletor/sinais (Python) devem ser os mesmos."""
import re
import unittest
from pathlib import Path
from major_league_scope import FOTMOB_IDS, EXTENDED_FOTMOB_IDS

JS = (Path(__file__).resolve().parent.parent / "web" / "nexus-league-coverage.js").read_text(encoding="utf8")


class LeagueIdConsistency(unittest.TestCase):
    def test_main_ids_match(self):
        block = JS[JS.index("const MAIN_IDS"):JS.index("});", JS.index("const MAIN_IDS"))]
        js = dict(re.findall(r"'(\d+)':'(\w+)'", block))
        self.assertEqual(js, FOTMOB_IDS)

    def test_extended_ids_match(self):
        block = JS[JS.index("const extended=["):JS.index("];", JS.index("const extended=["))]
        js = set(re.findall(r",'(\d+)'\]", block))
        self.assertEqual(js, set(EXTENDED_FOTMOB_IDS))


if __name__ == "__main__":
    unittest.main()
