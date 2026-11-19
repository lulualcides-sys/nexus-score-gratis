"""Regressão: odds ESPN por ID FotMob. "Série A" (Brasileirão no FotMob) ia
para a agenda da Serie A italiana; "Premier League" de Gana ia para a inglesa."""
import unittest
from espn_scoreboard_odds import fixture_espn_code, collect_odds


def fx(league, lid, verified=True):
    return {"league": league, "league_id": lid, "league_id_verified": verified}


class EspnLeagueIdTests(unittest.TestCase):
    def test_ids_decide(self):
        self.assertEqual(fixture_espn_code(fx("Série A", "268")), "bra.1")
        self.assertEqual(fixture_espn_code(fx("Serie A", "55")), "ita.1")
        self.assertEqual(fixture_espn_code(fx("Premier League", "47")), "eng.1")
        self.assertIsNone(fixture_espn_code(fx("Premier League", "522")))
        self.assertEqual(fixture_espn_code(fx("Friendlies", "114")), "fifa.friendly")
        self.assertEqual(fixture_espn_code(fx("Super Lig", "71")), "tur.1")

    def test_espn_rows_and_unverified_fall_back_to_name(self):
        self.assertEqual(fixture_espn_code({"league": "bra.1"}), "bra.1")
        self.assertEqual(fixture_espn_code(fx("Major League Soccer", "913550", False)), "usa.1")

    def test_main_leagues_queried_first(self):
        now = 1_800_000_000
        docs = {"d": {"matches": {}}}
        cands = []
        leagues = [("Segunda", "9138")] + [(f"Liga {i}", lid) for i, lid in
                   enumerate(["71", "40", "64", "38", "69", "46", "59", "67", "135",
                              "196", "274", "273", "161", "246", "131", "223", "140",
                              "86", "146", "110"])] + [("Série A", "268")]
        for i, (name, lid) in enumerate(leagues):
            key = f"fotmob-{i}"
            docs["d"]["matches"][key] = {"fixture": {**fx(name, lid), "phase": "scheduled",
                                                     "start_timestamp": now + 3600,
                                                     "home": "A", "away": "B"}}
            cands.append(("d", key, 3600))
        urls = []

        def fetch(url):
            urls.append(url)
            return {"events": []}
        collect_odds(docs, cands, now, fetcher=fetch)
        self.assertIn("/bra.1/", urls[0], "Brasileirão consultado primeiro")
        self.assertLessEqual(len(urls), 18)


if __name__ == "__main__":
    unittest.main()
