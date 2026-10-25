import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from tempfile import TemporaryDirectory
from unittest import TestCase

from telegram_collector.pinnacle_guest import (
    decimal_american, parse_markets, parse_matchup, get_focus_matches,
    classify_market, run
)
NOW = datetime(2026,10,25,13,0,tzinfo=timezone.utc)
KICK = NOW + timedelta(hours=3)

def sample_match(mid=111, league="Premier League", live=False):
    return {"id":mid,"league":{"id":3,"name":league},
            "startTime":KICK.isoformat(),
            "isLive": live,"participants":[
                {"alignment":"home","name":"Liverpool"},
                {"alignment":"away","name":"Chelsea"}],"hasMarkets":True}

def market(key="s;0;t;2.5", typ="", first=-125, second=110):
    return {"key":key,"type":typ,"period":0,
            "prices":[{"designation":"over","points":2.5,"price":first},
                      {"designation":"under","points":2.5,"price":second}]}

class PinnacleGuestTests(TestCase):
    def test_american_to_decimal_strict(self):
        self.assertEqual(decimal_american(-125),1.8)
        self.assertEqual(decimal_american(150),2.5)
        self.assertIsNone(decimal_american(2.15))
        self.assertIsNone(decimal_american(0))
        self.assertIsNone(decimal_american(float("nan")))

    def test_actual_prices_with_market_and_line_are_not_probabilities(self):
        q=parse_markets([market(),market("s;1;s;-0.5")],NOW)
        self.assertEqual(len(q),4)
        self.assertEqual(q[0]["bookmaker"],"Pinnacle")
        self.assertEqual(q[0]["market_family"],"total_goals")
        self.assertEqual(q[0]["line"],2.5)
        self.assertEqual(q[0]["odds_decimal"],1.8)
        self.assertEqual(q[2]["market_family"],"first_half_handicap")
        self.assertEqual(q[2]["period"],0)
        self.assertIn("guest_feed",q[0]["odds_kind"])
        self.assertFalse(any("probability" in x for x in q))

    def test_market_envelopes_are_supported_without_inventing_prices(self):
        self.assertEqual(len(parse_markets({"markets":[market()]},NOW)),2)
        self.assertEqual(len(parse_markets({"data":[market()]},NOW)),2)
        self.assertEqual(parse_markets({"error":"blocked"},NOW),[])

    def test_full_match_team_total_and_half_time_are_not_mixed(self):
        self.assertEqual(classify_market({}, "s;0;tt;1.5;home"), "team_goals")
        self.assertEqual(classify_market({}, "s;0;ou;2.5"), "total_goals")
        self.assertEqual(classify_market({}, "s;1;tt;0.5;home"), "first_half_team_goals")
        self.assertEqual(classify_market({}, "s;1;ou;1.5"), "first_half_goals")
        self.assertEqual(classify_market({}, "s;1;m"), "half_time")
        self.assertEqual(classify_market({}, "s;0;s;-0.5"), "asian_handicap")
        self.assertEqual(classify_market({}, "unsupported"), "unclassified")

    def test_closed_markets_and_missing_selections_dropped(self):
        stopped={**market(),"status":"suspended"}
        odd={**market(),"prices":[{"designation":"over","price":1.80}]}
        self.assertEqual(len(parse_markets([stopped,odd],NOW)),0)
        self.assertEqual(len(parse_markets([market(key="")],NOW)),0)

    def test_priority_sort_and_ignore_live(self):
        matchups=[sample_match(mid=1,league="Minor League"),
                  sample_match(mid=2,league="UEFA Champions League"),
                  sample_match(mid=3,league="La Liga",live=True)]
        selected=get_focus_matches(matchups,NOW,limit=3)
        self.assertEqual([m["provider_matchup_id"] for m in selected],[2,1])

    def test_snapshots_are_deduplicated_only_changes_retained(self):
        odds=[market(), market("s;0;m",typ="moneyline")]
        options=[sample_match()]
        def feed(path):
            return options if path == "/sports/29/matchups/highlighted" else odds
        with TemporaryDirectory() as d:
            a=run(Path(d),NOW,getter=feed)
            self.assertEqual(a["odds_observed"],4)
            self.assertEqual(a["new_price_snapshots"],1)
            b=run(Path(d),NOW+timedelta(minutes=3),getter=feed)
            self.assertEqual(b["new_price_snapshots"],0)
            odds[0]["prices"][0]["price"]=-120
            c=run(Path(d),NOW+timedelta(minutes=6),getter=feed)
            self.assertEqual(c["new_price_snapshots"],1)
            p=next((Path(d)/"public-no-key").glob("pinnacle-20*.json"))
            saved=json.loads(p.read_text())
            self.assertEqual(len(saved["games"]["111"]["snapshots"]),2)

    def test_supported_guest_envelope(self):
        wrapped = {"matchups": [sample_match()]}
        self.assertEqual(get_focus_matches(wrapped,NOW)[0]["provider_matchup_id"],111)
        with self.assertRaises(ValueError):
            get_focus_matches({"error": "restricted"},NOW)

    def test_rate_or_access_block_stops_next_requests_and_keeps_prices(self):
        calls = []
        matches = [sample_match(mid=1),sample_match(mid=2),sample_match(mid=3)]
        def getter(path):
            calls.append(path)
            if path == "/sports/29/matchups/highlighted":
                return matches
            if path.endswith("/2/markets/related/straight"):
                raise HTTPError(path, 403, "Forbidden", None, None)
            return [market()]
        with TemporaryDirectory() as folder:
            result=run(Path(folder),NOW,getter=getter,max_games=3)
            self.assertEqual(result["status"],"partial_blocked")
            self.assertEqual(result["matches_checked"],1)
            self.assertEqual(result["odds_observed"],2)
            self.assertEqual(len(calls),3)
            stored=Path(folder)/"public-no-key"/"pinnacle-latest.json"
            self.assertTrue(stored.exists())

    def test_feed_unavailable_does_not_claim_prices(self):
        def blocked(path):
            raise PermissionError("403")
        with TemporaryDirectory() as d:
            result=run(Path(d),NOW,getter=blocked)
            self.assertEqual(result["status"],"unavailable")
            self.assertEqual(result["odds_observed"],0)
            self.assertFalse((Path(d)/"public-no-key"/"pinnacle-latest.json").exists())
            self.assertTrue((Path(d)/"public-no-key"/"pinnacle-status.json").exists())

if __name__=="__main__":
    import unittest
    unittest.main()
