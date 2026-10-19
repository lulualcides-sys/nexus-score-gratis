import unittest
from datetime import datetime, timezone
from the_odds_api_source import (threeway_from_event, find_matching_fixture, collect_odds)

NOW=1791580000-220

def fixture():
    return {"fixture":{"home":"Lexington SC","away":"FC Tulsa","phase":"scheduled",
      "start_timestamp":NOW+2000,"league":"USL Championship"}}

def event(start=NOW+2000, away="FC Tulsa"):
    return {"home_team":"Lexington SC","away_team":away,
      "commence_time":datetime.fromtimestamp(start,timezone.utc).isoformat(),
      "bookmakers":[{"key":"example","title":"Casa demonstrada","last_update":
         datetime.fromtimestamp(NOW-120,timezone.utc).isoformat(),
         "markets":[{"key":"h2h","outcomes":[
            {"name":"Lexington SC","price":2.1},{"name":"Draw","price":3.2},
            {"name":"FC Tulsa","price":3.7}]}]}]}

class OddsAPISourceTests(unittest.TestCase):
    def test_complete_h2h_with_named_teams_and_timestamp(self):
        r=threeway_from_event(event(),NOW)
        self.assertEqual(r[0]["home"],2.1)
        self.assertEqual(r[0]["draw"],3.2)
        self.assertEqual(r[1],"Casa demonstrada")
    def test_strict_rejects_incomplete_or_stale_market(self):
        incomplete=event()
        incomplete["bookmakers"][0]["markets"][0]["outcomes"].pop()
        self.assertIsNone(threeway_from_event(incomplete,NOW))
        old=event()
        old["bookmakers"][0]["last_update"]=datetime.fromtimestamp(NOW-172800,timezone.utc).isoformat()
        self.assertIsNone(threeway_from_event(old,NOW))
    def test_only_unique_fixture_matches_and_not_same_team_on_wrong_date(self):
        f=fixture()["fixture"]
        self.assertIsNotNone(find_matching_fixture(f,[event()]))
        self.assertIsNone(find_matching_fixture(f,[event(away="Indy Eleven")]))
        self.assertIsNone(find_matching_fixture(f,[event(start=NOW+4000)]))
        self.assertIsNone(find_matching_fixture(f,[event(),event()]))
    def test_free_monthly_budget_does_not_poll_every_five_minutes(self):
        row=fixture()
        docs={'2026-10-09':{'matches':{'fotmob-1':row}}}
        calls=[]
        def fetch(url):calls.append(url);return []
        status=collect_odds(docs,[('2026-10-09','fotmob-1',2000)],NOW+600,key='free',fetcher=fetch)
        self.assertEqual(status['status'],'waiting_free_slot')
        self.assertEqual(calls,[])
    def test_soccer_region_groups_in_catalog(self):
        from the_odds_api_source import fixture_sport_keys
        sports=[{'key':'soccer_epl','group':'Soccer - England','title':'EPL'},
                {'key':'basketball_nba','group':'Basketball','title':'NBA'}]
        self.assertEqual(fixture_sport_keys('Premier League',sports),['soccer_epl'])

    def test_skip_without_key_and_no_api_call(self):
        row=fixture(); docs={"2026-10-09":{"matches":{"fotmob-1":row}}}
        status=collect_odds(docs,[("2026-10-09","fotmob-1",2000)],NOW,key="",fetcher=lambda url:1)
        self.assertEqual(status["status"],"not_configured")
        self.assertFalse(row.get("odds_quotes"))
    def test_capture_only_when_key_and_fixture_matched(self):
        row=fixture(); docs={"2026-10-09":{"matches":{"fotmob-1":row}}}
        calls=[]
        def fetch(url):
            calls.append(url)
            if "/sports/?" in url:
                return [{"key":"soccer_usa_usl","group":"Soccer","title":"USL Championship",
                         "active":True}]
            return [event()]
        status=collect_odds(docs,[("2026-10-09","fotmob-1",2000)],NOW,key="a-test-key",fetcher=fetch)
        self.assertEqual(status["quotes_added"],3)
        self.assertEqual(status["matched"],1)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(x["source"]=="The Odds API" for x in row["odds_quotes"]))

if __name__=="__main__":unittest.main()
