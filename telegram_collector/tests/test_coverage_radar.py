import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from telegram_collector.coverage_radar import (
    build, collect_records, same_teams_and_time, priority_match, enrich_pinnacle
)

class CoverageRadarTests(unittest.TestCase):
    def test_cross_provider_matches_and_quote_levels_without_fabrication(self):
        now = datetime.now(timezone.utc)
        kickoff = now + timedelta(hours=2)
        k = kickoff.isoformat()
        book_time = (now-timedelta(minutes=1)).isoformat()
        record = {
            "schema": 1, "day": kickoff.astimezone(
                __import__("zoneinfo").ZoneInfo("America/Sao_Paulo")
            ).date().isoformat(),
            "games": {
                "fotmob-1": {
                    "home": "Real Madrid", "away": "Barcelona FC", "league": "La Liga",
                    "kickoff_unix": int(kickoff.timestamp()),
                    "source": ["FotMob"],
                    "observations": [
                        {"phase": "scheduled", "odds": [{
                            "market": "1x2", "selection": "home", "odds": 2.02,
                            "bookmaker": "BookA", "source": "ESPN",
                            "captured_at": book_time, "scope": "pregame"
                        }]}
                    ]
                },
                "espn-dup": {
                    "home": "Real Madrid CF", "away": "Barcelona",
                    "league": "La Liga", "kickoff_unix": int(kickoff.timestamp()),
                    "source": ["ESPN"], "observations": [{"phase": "scheduled","odds":[]}]
                },
                "no-price": {
                    "home": "Inter", "away": "Milan", "league": "Serie A Itália",
                    "kickoff_unix": int(kickoff.timestamp()),
                    "source": ["FotMob"], "observations": [{"phase":"scheduled", "odds":[]}]
                }
            }
        }
        feed = {"matches": [
            {"home":"Real Madrid", "away":"Barcelona", "league":"La Liga",
             "kickoff_utc":k, "provider_match_id":"11","benchmark_fair_odds":{"home":2.1},
             "best_soft_bookmaker_quote": None},
            {"home":"Boca Juniors", "away":"River Plate", "league":"Liga Profesional Argentina",
             "kickoff_utc":k, "provider_match_id":"12","benchmark_fair_odds":{"home":2.3},
             "best_soft_bookmaker_quote": {
                "bookmaker":"BookB", "price":2.2, "selection":"home",
                "feed_generated_at": now.isoformat(),
                "verification":"indicative_feed_quote_unconfirmed_source_time"}}
        ]}
        with TemporaryDirectory() as folder:
            p=Path(folder)
            (p/(record["day"]+".json")).write_text(json.dumps(record))
            (p/"public-no-key").mkdir()
            (p/"public-no-key"/"tipsaudit-latest.json").write_text(json.dumps(feed))
            out = build(p,now)
        self.assertEqual(out["important_games"],3)
        self.assertEqual(out["verified_bookmaker_games"],1)
        self.assertEqual(out["indicative_only_games"],1)
        self.assertEqual(out["missing_bookmaker_price_games"],1)
        self.assertEqual(out["tipsaudit"]["new_priority"],1)
        v=next(x for x in out["priority_fixtures"] if x["home"]=="Real Madrid")
        self.assertEqual(v["verified_quotes"],1)
        self.assertFalse(v["indicative_bookmaker_quotes"])
        only=next(x for x in out["priority_fixtures"] if x["home"]=="Boca Juniors")
        self.assertEqual(only["coverage"],"indicative_only")
        self.assertEqual(only["verified_quotes"],0)

    def test_reversed_home_away_never_merged(self):
        self.assertFalse(same_teams_and_time(
            {"home":"A","away":"B","kickoff_unix":1000},
            {"home":"B","away":"A","kickoff_unix":1000}))
        self.assertTrue(same_teams_and_time(
            {"home":"Real Madrid CF","away":"Barcelona","kickoff_unix":2000},
            {"home":"Real Madrid","away":"Barcelona FC","kickoff_unix":2200}))

    def test_protected_club_aliases_and_correct_league_identity(self):
        self.assertTrue(same_teams_and_time(
            {"home":"LAFC", "away":"LA Galaxy","kickoff_unix":1100000,
             "league":"usa.1"},
            {"home":"Los Angeles FC", "away":"Los Angeles Galaxy",
             "kickoff_unix":1100200,"league":"MLS"}))
        self.assertTrue(same_teams_and_time(
            {"home":"Sporting CP","away":"Académico Viseu","kickoff_unix":1100000,
             "league":"por.1"},
            {"home":"Sporting CP","away":"Académico de Viseu",
             "kickoff_unix":1100000,"league":"Liga Portugal"}))
        self.assertFalse(same_teams_and_time(
            {"home":"Team A","away":"Team B","kickoff_unix":1100000,
             "league":"eng.1"},
            {"home":"Team A","away":"Team B","kickoff_unix":1100000,
             "league":"ita.1"}))
        self.assertIsNone(priority_match("Canadian Premier League"))
        self.assertIsNone(priority_match("MLS Next Pro"))
        self.assertIsNone(priority_match("Liga MX Femenil Apertura"))
        self.assertEqual(priority_match("Premier League",{"league_code":"eng.1"}),"eng.1")
        self.assertEqual(priority_match("Premier League",{"id":"espn-eng.1-123"}),"eng.1")

    def test_guest_pinnacle_is_verified_only_if_pregame_recent_same_teams(self):
        now=datetime.now(timezone.utc)
        k=(now+timedelta(hours=2)).timestamp()
        records=[{"home":"Liverpool","away":"Chelsea","league":"Premier League",
                  "league_code":"eng.1","kickoff_unix":k,
                  "verified_quotes":0, "indicative_bookmaker_quotes":[],
                  "data_sources":["ESPN"]}]
        quote = {"bookmaker":"Pinnacle", "source":"Pinnacle public guest web feed",
                 "selection":"over", "raw_market_key":"s;0;t;2.5",
                 "market_family":"total_goals", "odds_decimal":1.94,
                 "line":2.5,"observed_at":now.isoformat()}
        payload={"schema":1,"checked_at":now.isoformat(),
                 "matches":{"22":{"home":"Liverpool FC","away":"Chelsea",
                                  "kickoff_utc":datetime.fromtimestamp(k,timezone.utc).isoformat(),
                                  "odds":[quote]}}}
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"pinnacle-latest.json"
            path.write_text(json.dumps(payload))
            out=enrich_pinnacle(records,path,now)
            self.assertEqual(out["new_verified_game"],1)
            self.assertEqual(records[0]["verified_quotes"],1)
            self.assertEqual(out["market_families"]["total_goals"],1)
            records[0]["verified_quotes"]=0
            payload["matches"]["22"]["odds"][0]["observed_at"]=(now+timedelta(hours=5)).isoformat()
            path.write_text(json.dumps(payload))
            bad=enrich_pinnacle(records,path,now)
            self.assertEqual(bad["offers"],0)
            self.assertEqual(records[0]["verified_quotes"],0)

    def test_no_archive_is_empty_not_invented(self):
        with TemporaryDirectory() as folder:
            result = build(Path(folder), datetime.now(timezone.utc))
            self.assertEqual(result["important_games"], 0)
            self.assertEqual(result["missing_bookmaker_price_games"], 0)
            self.assertEqual(result["tipsaudit"]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
