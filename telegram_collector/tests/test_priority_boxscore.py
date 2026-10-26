import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from telegram_collector.priority_boxscore import (
    parse_boxscore, as_count, should_query, apply_stats, run,
)

NOW = datetime(2026,10,25,23,0,tzinfo=timezone.utc)
KICK = NOW-timedelta(hours=3)

def summary(home="Liverpool", away="Chelsea"):
    return {"boxscore":{"teams":[
        {"team":{"displayName":home},"statistics":[
            {"name":"wonCorners","value":"7"},
            {"name":"yellowCards","value":"3"},
            {"name":"shotsOnTarget","value":"5"},
            {"name":"totalShots","value":"12"}]},
        {"team":{"displayName":away},"statistics":[
            {"name":"wonCorners","value":"4"},
            {"name":"yellowCards","value":"1"},
            {"name":"shotsOnTarget","value":"2"},
            {"name":"totalShots","value":"8"}]}
    ]}}

def game(phase="finished"):
    return {"id":"espn-eng.1-12345","espn_event_id":"12345",
            "espn_league_code":"eng.1",
            "league":"Premier League","home":"Liverpool","away":"Chelsea",
            "kickoff_unix":KICK.timestamp(),
            "observations":[{"phase":phase,"minute":90,"score":"2-1","odds":[
                {"market":"1x2","selection":"home","odds":1.9,
                 "bookmaker":"Example","source":"ESPN",
                 "captured_at":(KICK-timedelta(hours=1)).isoformat(),
                 "scope":"pregame"}],"stats":{},"settlement":{}}]}

class BoxscoreTests(unittest.TestCase):
    def test_parse_real_team_fields_without_inventing_values(self):
        values=parse_boxscore(summary(),"Liverpool","Chelsea")
        self.assertEqual(values["home"]["corners"],7)
        self.assertEqual(values["away"]["yellow_cards"],1)
        self.assertEqual(values["home"]["shots_on"],5)
        self.assertNotIn("red_cards",values["home"])
        self.assertIsNone(parse_boxscore(summary("Arsenal","Chelsea"),
                                         "Liverpool","Chelsea"))
        self.assertIsNone(parse_boxscore({"boxscore":{"teams":[]}},
                                         "Liverpool","Chelsea"))
        self.assertIsNone(as_count("5%"))
        self.assertIsNone(as_count("4/7"))
        self.assertIsNone(as_count(-2))

    def test_preserve_original_prices_and_settle_observed_sports_markets(self):
        rec=game()
        original=json.dumps(rec["observations"][0]["odds"],sort_keys=True)
        updated,n=apply_stats(rec,summary(),NOW.isoformat())
        self.assertTrue(updated)
        self.assertEqual(n,8)
        snap=rec["observations"][-1]
        self.assertEqual(json.dumps(snap["odds"],sort_keys=True),original)
        self.assertEqual(snap["settlement"]["total_corners"],11)
        self.assertEqual(snap["settlement"]["total_yellow_cards"],4)
        self.assertEqual(snap["settlement"]["total_shots_on_target"],7)
        self.assertNotIn("red_cards",snap["settlement"])
        again,_=apply_stats(rec,summary(),NOW.isoformat())
        self.assertFalse(again)

    def test_recent_live_and_finished_only(self):
        current=game()
        self.assertTrue(should_query(current,NOW))
        current["espn_boxscore_last_checked"]=NOW.isoformat()
        self.assertFalse(should_query(current,NOW+timedelta(minutes=4)))
        current["observations"][-1]["phase"]="scheduled"
        self.assertFalse(should_query(current,NOW+timedelta(hours=4)))
        current["observations"][-1]["phase"]="live"
        self.assertTrue(should_query(current,NOW+timedelta(minutes=20)))

    def test_bounded_offline_fetch_and_safe_persistence(self):
        with TemporaryDirectory() as temp:
            folder=Path(temp)
            day=NOW.astimezone(__import__("zoneinfo").ZoneInfo("America/Sao_Paulo")).date().isoformat()
            f=folder/(day+".json")
            f.write_text(json.dumps({"schema":1,"day":day,"games":{"123":game()}}))
            calls=[]
            def fetch(code,id_):
                calls.append((code,id_))
                return summary()
            status=run(folder,NOW,fetcher=fetch,max_requests=1)
            self.assertEqual(status["games_enriched"],1)
            self.assertEqual(status["observed_statistics_fields"],8)
            self.assertEqual(calls,[("eng.1","12345")])
            updated=json.loads(f.read_text())
            self.assertEqual(len(updated["games"]["123"]["observations"]),2)
            self.assertTrue((folder/"priority-boxscore-status.json").exists())
            retry=run(folder,NOW+timedelta(minutes=5),fetcher=fetch,max_requests=1)
            self.assertEqual(retry["checked"],0)
            self.assertEqual(len(calls),1)

    def test_live_stats_do_not_move_backwards_when_espn_is_late(self):
        record=game("live")
        record["observations"][-1]["stats"]={
            "home":{"corners":9,"yellow_cards":4,"shots_on":6},
            "away":{"corners":5,"yellow_cards":1,"shots_on":2}}
        changed,_=apply_stats(record,summary(),NOW.isoformat())
        self.assertTrue(changed)
        snap=record["observations"][-1]
        self.assertEqual(snap["stats"]["home"]["corners"],9)
        self.assertEqual(snap["stats"]["away"]["corners"],5)
        self.assertEqual(snap["stats"]["home"]["yellow_cards"],4)
        self.assertEqual(snap["stats"]["away"]["shots_total"],8)
        self.assertEqual(snap["odds"],record["observations"][0]["odds"])

    def test_summary_bad_team_names_does_not_change_stats(self):
        original=game()
        before=json.dumps(original,sort_keys=True)
        done,n=apply_stats(original,summary("Arsenal","Chelsea"),NOW.isoformat())
        self.assertFalse(done)
        self.assertEqual(n,0)
        self.assertEqual(json.dumps(original,sort_keys=True),before)

if __name__=="__main__":
    unittest.main()
