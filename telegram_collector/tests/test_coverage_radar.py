import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from telegram_collector.coverage_radar import (
    build, collect_records, same_teams_and_time, priority_match, enrich_pinnacle, read_book_quality
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

    def test_book_quality_attached_only_if_fresh(self):
        now=datetime.now(timezone.utc)
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"pinnacle-depth.json"
            p.write_text(json.dumps({"schema":1,"checked_at":now.isoformat(),
                "status":"fresh","complete_market_lines":77,
                "incomplete_market_lines":3,"families":{"match_odds":{
                    "complete_lines":22,"median_overround_pct":5.1}}}))
            good=read_book_quality(p,now)
            self.assertEqual(good["complete_market_lines"],77)
            self.assertEqual(good["families"]["match_odds"]["median_overround_pct"],5.1)
            old=read_book_quality(p,now+timedelta(hours=5))
            self.assertEqual(old["status"],"stale")

    def test_price_movements_only_from_valid_two_pregame_observations(self):
        from telegram_collector.coverage_radar import read_price_movements
        now=datetime.now(timezone.utc)
        before=(now-timedelta(minutes=40)).isoformat()
        after=(now-timedelta(minutes=10)).isoformat()
        kickoff=(now+timedelta(hours=2)).isoformat()
        data={"schema":1,"checked_at":now.isoformat(),"status":"fresh",
              "market_selections_with_changes":4,"snapshots_processed":8,
              "top_changes":[{"home":"Flamengo","away":"Corinthians",
                  "raw_market_key":"s;0;ou;2.5","market_family":"total_goals",
                  "selection":"over","first_odds":2.15,"last_odds":1.92,
                  "first_observed":before,"last_observed":after,
                  "kickoff_utc":kickoff,"implied_probability_change_pp":5.57,
                  "betting_execution_confirmed":False}]}
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"pinnacle-motion-latest.json"
            p.write_text(json.dumps(data))
            summary=read_price_movements(p,now)
            self.assertEqual(summary["status"],"fresh")
            self.assertEqual(len(summary["top_changes"]),1)
            data["top_changes"][0]["last_observed"]=(now+timedelta(hours=3)).isoformat()
            p.write_text(json.dumps(data))
            self.assertEqual(read_price_movements(p,now)["top_changes"],[])
            data["top_changes"][0]["last_observed"]=after
            data["checked_at"]=(now-timedelta(hours=5)).isoformat()
            p.write_text(json.dumps(data))
            self.assertEqual(read_price_movements(p,now)["status"],"stale")

    def test_actual_match_stats_do_not_masquerade_as_corner_card_odds(self):
        now=datetime.now(timezone.utc)
        kickoff=now-timedelta(minutes=40)
        local_day=kickoff.astimezone(__import__("zoneinfo").ZoneInfo("America/Sao_Paulo")).date().isoformat()
        matches={"schema":1,"day":local_day,"games":{
            "espn-eng.1-123":{
                "id":"espn-eng.1-123","home":"Arsenal","away":"Chelsea",
                "league":"Premier League","league_code":"eng.1",
                "kickoff_unix":kickoff.timestamp(),"source":["ESPN"],
                "observations":[{"phase":"finished","score":"1-1","odds":[],
                    "stats_source":"ESPN public soccer boxscore",
                    "stats":{"home":{"corners":8,"yellow_cards":2,"shots_on":5},
                             "away":{"corners":2,"yellow_cards":3,"shots_on":4}}}]}}}
        with TemporaryDirectory() as folder:
            p=Path(folder)
            (p/(local_day+".json")).write_text(json.dumps(matches))
            results=build(p,now)
            self.assertEqual(results["games_with_corners_stats"],1)
            self.assertEqual(results["games_with_yellow_cards_stats"],1)
            self.assertEqual(results["games_with_shots_on_target_stats"],1)
            self.assertEqual(results["verified_bookmaker_games"],0)
            self.assertEqual(results["missing_bookmaker_price_games"],1)
            game=results["priority_fixtures"][0]
            self.assertEqual(game["boxscore_stats_source"],"ESPN public soccer boxscore")

    def test_official_real_corners_cards_only_after_identity_and_bookmaker_time(self):
        from telegram_collector.coverage_radar import enrich_official_corners_cards
        now=datetime.now(timezone.utc)
        kickoff=now+timedelta(hours=2)
        game={
            "home":"Liverpool","away":"Chelsea","league":"Premier League",
            "league_code":"eng.1","kickoff_unix":kickoff.timestamp(),
            "verified_quotes":0,"data_sources":[]}
        base={"raw_market_key":"alternate_totals_corners",
              "market_family":"total_corners","selection":"over",
              "line":9.5,"odds_decimal":1.95,"bookmaker":"Example Sportsbook",
              "captured_at":now.isoformat(),
              "bookmaker_market_updated_at":now.isoformat(),
              "source":"The Odds API free official user-key feed"}
        book={"schema":1,"matches":{"event-1":{
            "home":"Liverpool","away":"Chelsea","kickoff_utc":kickoff.isoformat(),
            "league_code":"eng.1",
            "observations":[{"captured_at":now.isoformat(),
                             "prices":[base,{**base,
                                      "raw_market_key":"alternate_totals_cards",
                                      "market_family":"total_cards","line":4.5}]}]}}}
        with TemporaryDirectory() as folder:
            directory=Path(folder)
            file=directory/("quotes-"+now.astimezone(
                __import__("zoneinfo").ZoneInfo("America/Sao_Paulo")).date().isoformat()+".json")
            file.write_text(json.dumps(book))
            result=enrich_official_corners_cards([game],directory,now)
            self.assertEqual(result["verified_corners_quotes"],1)
            self.assertEqual(result["verified_cards_quotes"],1)
            self.assertEqual(game["verified_quotes"],2)
            self.assertFalse(result["liquidity_verified"])
            wrong={**book}
            wrong=json.loads(json.dumps(book))
            wrong["matches"]["event-1"]["home"]="Manchester United"
            file.write_text(json.dumps(wrong))
            record={**game,"verified_quotes":0,
                    "data_sources":[]}
            rejected=enrich_official_corners_cards([record],directory,now)
            self.assertEqual(rejected["verified_corners_quotes"],0)
            self.assertEqual(record["verified_quotes"],0)
            stale=json.loads(json.dumps(book))
            stale["matches"]["event-1"]["observations"][0]["prices"][0][
                "bookmaker_market_updated_at"]=(now+timedelta(hours=3)).isoformat()
            file.write_text(json.dumps(stale))
            record={**game,"verified_quotes":0,"data_sources":[]}
            trusted=enrich_official_corners_cards([record],directory,now)
            self.assertEqual(trusted["verified_corners_quotes"],0)
            self.assertEqual(trusted["verified_cards_quotes"],1)

    def test_no_archive_is_empty_not_invented(self):
        with TemporaryDirectory() as folder:
            result = build(Path(folder), datetime.now(timezone.utc))
            self.assertEqual(result["important_games"], 0)
            self.assertEqual(result["missing_bookmaker_price_games"], 0)
            self.assertEqual(result["tipsaudit"]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
