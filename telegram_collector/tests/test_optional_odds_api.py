import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from telegram_collector.optional_odds_api import (
    parse_market_prices, read_targets, run,MAX_DAILY_EVENTS
)

NOW=datetime(2026,10,25,23,0,tzinfo=timezone.utc)
START=NOW+timedelta(hours=5)

def event():
    return {"id":"abcd1234","sport_key":"soccer_epl","home_team":"Liverpool",
            "away_team":"Chelsea","commence_time":START.isoformat()}

def target():
    return {"home":"Liverpool","away":"Chelsea","league_code":"eng.1",
            "kickoff_unix":START.timestamp(),
            "kickoff_utc":START.isoformat(),"coverage":"no_bookmaker_price"}

def odds():
    return {**event(),"bookmakers":[{
        "key":"pinnacle","title":"Pinnacle",
        "markets":[
            {"key":"alternate_totals_corners",
             "last_update":NOW.isoformat(),
             "outcomes":[{"name":"Over","point":9.5,"price":1.92},
                         {"name":"Under","point":9.5,"price":1.91}]},
            {"key":"alternate_totals_cards",
             "last_update":NOW.isoformat(),
             "outcomes":[{"name":"Over","point":4.5,"price":2.08},
                         {"name":"Under","point":4.5,"price":1.82}]}
        ]}]}

class OfficialOptionalOddsTests(unittest.TestCase):
    def make_data(self,folder):
        r={"schema":1,"checked_at":NOW.isoformat(),"priority_fixtures":[target()]}
        (Path(folder)/"priority-coverage.json").write_text(json.dumps(r))

    def test_secret_missing_does_not_call_network(self):
        with TemporaryDirectory() as folder:
            result=run(folder,NOW,key="",getter=lambda *x: (_ for _ in ()).throw(
                AssertionError("must not call")))
            self.assertEqual(result["status"],"no_key")
            self.assertEqual(result["prices_observed"],0)
            self.assertTrue((Path(folder)/"official-free-odds"/"status.json").exists())

    def test_actual_total_corners_and_cards_quotes_match_source_and_timestamp(self):
        data=odds()
        quotes=parse_market_prices(data,{**target(),"provider_event_id":"abcd1234"},NOW)
        self.assertEqual(len(quotes),4)
        self.assertEqual({q["market_family"] for q in quotes},{"total_corners","total_cards"})
        self.assertEqual({q["line"] for q in quotes},{9.5,4.5})
        self.assertTrue(all(q["bookmaker"]=="Pinnacle" for q in quotes))
        self.assertTrue(all(q["bet_executed"] is False for q in quotes))
        self.assertTrue(all(q["liquidity_verified"] is False for q in quotes))
        bad=odds()
        bad["home_team"],bad["away_team"]=bad["away_team"],bad["home_team"]
        self.assertEqual(parse_market_prices(bad,{**target(),"provider_event_id":"abcd1234"},NOW),[])
        stale=odds()
        stale["bookmakers"][0]["markets"][0]["last_update"]=(NOW+timedelta(hours=6)).isoformat()
        self.assertEqual(len(parse_market_prices(stale,{**target(),"provider_event_id":"abcd1234"},NOW)),2)

    def test_key_enables_two_bounded_calls_and_ledger_prevents_more(self):
        with TemporaryDirectory() as folder:
            self.make_data(folder)
            calls=[]
            def fake(sport,event_id,key):
                calls.append((sport,event_id))
                self.assertEqual(key,"own-personal-free-key")
                return ([event()],{}) if event_id is None else (
                    odds(),{"x-requests-remaining":"450"})
            first=run(folder,NOW,key="own-personal-free-key",getter=fake)
            self.assertEqual(first["prices_observed"],4)
            self.assertEqual(first["event_odds_requests"],1)
            second=run(folder,NOW+timedelta(minutes=5),key="own-personal-free-key",getter=fake)
            self.assertEqual(second["event_odds_requests"],0)
            self.assertEqual(calls,[("soccer_epl",None),("soccer_epl","abcd1234")])
            saved=list((Path(folder)/"official-free-odds").glob("quotes-*.json"))
            self.assertEqual(len(saved),1)
            assert_quotes=json.loads(saved[0].read_text())["matches"]["abcd1234"]["observations"]
            self.assertEqual(len(assert_quotes),1)
            self.assertEqual(len(assert_quotes[0]["prices"]),4)
            budget=list((Path(folder)/"official-free-odds").glob("budget-*.json"))
            self.assertEqual(json.loads(budget[0].read_text())["local_credits_reserved"],2)

    def test_missing_event_never_spends_quota_or_makes_up_bookmaker_prices(self):
        with TemporaryDirectory() as folder:
            self.make_data(folder)
            checked=[]
            def empty(sport,event_id,key):
                checked.append(event_id)
                return ([{**event(),"home_team":"Arsenal"}],{})
            result=run(folder,NOW,key="own-key",getter=empty)
            self.assertEqual(result["event_odds_requests"],0)
            self.assertEqual(result["prices_observed"],0)
            self.assertEqual(checked,[None])
            self.assertFalse(list((Path(folder)/"official-free-odds").glob("quotes-*.json")))

if __name__=="__main__":
    unittest.main()
