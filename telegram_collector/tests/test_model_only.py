"""Tests for NEXUS math-only independent bookmaker-free football pricing."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from telegram_collector.model_only import (
    generate, historical_rows, make_probability_book, normalized_team,
    team_rates, scoreline, integer_goals,
)

NOW=datetime(2026,10,25,15,0,tzinfo=timezone.utc)


def priors(n=75,league="eng.1",with_ht=True):
    result=[]
    for j in range(n):
        # Realistically variable team strengths and outcomes, not odds.
        h,a=("Arsenal","Chelsea") if j%2==0 else ("Chelsea","Arsenal")
        ft=[(2,1),(1,1),(1,0),(0,1),(2,2)][j%5]
        ht=(int(ft[0]>1),int(ft[1]>0)) if with_ht else None
        result.append({
            "league":league,"home":normalized_team(h),"away":normalized_team(a),
            "date":(NOW-timedelta(days=2+j)).date(),
            "ft":ft,"ht":ht,
            "source":"unit-test finished match"
        })
    return result


def p(market,key):
    return market[key]["probability"]


class MathsTests(unittest.TestCase):
    def test_market_probabilities_all_coherent_and_theoretical_odds(self):
        market=make_probability_book(1.65,1.12,.44)
        for category in ("ft_1x2","ht_1x2","ht_ft","btts_ft","btts_ht"):
            self.assertAlmostEqual(sum(v["probability"] for v in market[category].values()),1,places=4)
        self.assertEqual(len(market["ht_ft"]),9)
        self.assertEqual(len(market["ft_1x2"]),3)
        self.assertEqual(len(market["ht_1x2"]),3)
        self.assertEqual(len(market["double_chance_ft"]),3)
        for end in ("1","X","2"):
            self.assertAlmostEqual(
                sum(item["probability"] for name,item in market["ht_ft"].items()
                    if name.split("/")[1]==end),
                p(market["ft_1x2"],end),delta=.00001)
            self.assertAlmostEqual(
                sum(item["probability"] for name,item in market["ht_ft"].items()
                    if name.split("/")[0]==end),
                p(market["ht_1x2"],end),delta=.00001)
        self.assertAlmostEqual(
            p(market["double_chance_ft"],"1X"),
            p(market["ft_1x2"],"1")+p(market["ft_1x2"],"X"),places=5)
        for group in ("ft_total_goals","ht_total_goals","home_team_goals_ft",
                      "away_team_goals_ft"):
            for line,item in market[group].items():
                self.assertAlmostEqual(sum(v["probability"] for v in item.values()),1,places=5)
                self.assertAlmostEqual(item["Over"]["fair_odds"],
                                       1/item["Over"]["probability"],delta=.002)
        self.assertGreater(p(market["ft_total_goals"]["2.5"],"Over"),
                           p(market["ht_total_goals"]["2.5"],"Over"))
        self.assertGreater(p(market["btts_ft"],"Sim"),p(market["btts_ht"],"Sim"))
        self.assertEqual(len(market["correct_score_ft"]),8)
        self.assertGreater(p(market["ft_1x2"],"1"),p(market["ft_1x2"],"2"))

    def test_equal_expectations_roughly_equal_win_probabilities(self):
        market=make_probability_book(1.3,1.3,.45)
        self.assertAlmostEqual(p(market["ft_1x2"],"1"),p(market["ft_1x2"],"2"),places=5)
        self.assertAlmostEqual(p(market["ht_1x2"],"1"),p(market["ht_1x2"],"2"),places=5)
        with self.assertRaises(ValueError):
            make_probability_book(float("nan"),1,.45)

    def test_no_team_history_means_no_market_fabrication(self):
        hist=priors()
        fixture={"league_code":"eng.1","home":"Arsenal","away":"Brighton",
                 "kickoff_unix":(NOW+timedelta(days=1)).timestamp()}
        rates,reason=team_rates(hist,fixture,NOW)
        self.assertIsNone(rates)
        self.assertEqual(reason,"insufficient_team_results")
        fixture["away"]="Chelsea"
        rates,reason=team_rates(hist,fixture,NOW)
        self.assertIsNone(reason)
        self.assertTrue(.35<=rates["lambda_home_ft"]<=3.4)
        self.assertTrue(.35<=rates["first_half_share"]<=.6)
        self.assertEqual(rates["half_time_calibration_source"],"league_observed_halftimes")

    def test_missing_halftime_data_does_not_invent_ht_odds(self):
        fixture={"league_code":"eng.1","home":"Arsenal","away":"Chelsea",
                 "kickoff_unix":(NOW+timedelta(days=1)).timestamp()}
        rates,reason=team_rates(priors(with_ht=False),fixture,NOW)
        self.assertIsNone(rates)
        self.assertEqual(reason,"insufficient_halftime_results")

    def test_read_only_finished_score_results_and_cc0_data_with_no_future_leak(self):
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)
            date=(NOW-timedelta(days=15)).date().isoformat()
            future=(NOW+timedelta(days=2)).date().isoformat()
            folder.joinpath(date+".json").write_text(json.dumps({
                "matches":{
                    "past":{"fixture":{"phase":"finished","start_timestamp":
                        (NOW-timedelta(days=15)).timestamp(),
                        "home":"Arsenal","away":"Chelsea",
                        "league_code":"eng.1","score":"2-0"}},
                    "live":{"fixture":{"phase":"live","start_timestamp":
                        (NOW-timedelta(days=1)).timestamp(),
                        "home":"Liverpool","away":"Everton",
                        "league_code":"eng.1","score":"1-0"}},
                    "not_done":{"fixture":{"phase":"finished","start_timestamp":
                        (NOW+timedelta(days=1)).timestamp(),
                        "home":"Arsenal","away":"Everton",
                        "league_code":"eng.1","score":"9-0"}}}}))
            folder.joinpath("openfootball_cc0_cache.json").write_text(json.dumps({
                "entries":{"2026-27/en.1.json":{"matches":[
                    {"date":date,"team1":"Arsenal FC","team2":"Chelsea FC",
                     "score":{"ft":[2,0],"ht":[1,0]}},
                    {"date":date,"team1":"Everton FC","team2":"Manchester United FC",
                     "score":[0,0]}, # placeholder must be dropped
                    {"date":future,"team1":"Liverpool","team2":"Everton",
                     "score":{"ft":[3,0],"ht":[2,0]}},
                    {"date":date,"team1":"Manchester City","team2":"Brentford",
                     "score":{"ft":[2,1],"ht":[3,0]}} # impossible HT
                ]}}}))
            rows=historical_rows(folder,NOW)
            self.assertEqual(len(rows),2)
            self.assertEqual(next(m for m in rows if m["home"]=="arsenal")["ht"],(1,0))
            self.assertNotIn("liverpool",[m["home"] for m in rows])
            self.assertTrue(all(m["date"]<NOW.date() for m in rows))
            other=next(m for m in rows if m["home"]=="manchester city")
            self.assertIsNone(other["ht"])

    def test_calendar_stale_and_forecast_separate_from_bookmaker_quotes(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)
            h=p/"history"
            a=p/"market-history"
            h.mkdir();a.mkdir()
            future=(NOW+timedelta(days=1)).timestamp()
            a.joinpath("priority-coverage.json").write_text(json.dumps({
                "schema":1,"checked_at":NOW.isoformat(),
                "priority_fixtures":[{"league_code":"eng.1",
                    "home":"Arsenal","away":"Chelsea","kickoff_unix":future},
                    {"league_code":"eng.1","home":"Arsenal",
                     "away":"Chelsea","kickoff_unix":future},
                    {"league_code":"eng.1","home":"Arsenal","away":"Chelsea",
                     "kickoff_unix":(NOW-timedelta(hours=1)).timestamp()}]}))
            # No finished matches: return one refused forecast with explicit reason.
            x=generate(h,a,NOW)
            self.assertEqual(x["fixtures_found"],1)
            self.assertEqual(x["fixtures_priced"],0)
            self.assertEqual(x["fixtures_without_model"],1)
            self.assertEqual(x["fixtures"][0]["model_status"],"insufficient_league_results")
            self.assertNotIn("markets",x["fixtures"][0])
            self.assertTrue(x["fixtures"][0]["not_a_bookmaker_quote"])
            self.assertEqual(x["excluded_markets"],
                             ["handicap","escanteios","cartoes","jogadores"])

    def test_goals_parser_strict(self):
        self.assertEqual(scoreline("2-1"),(2,1))
        self.assertEqual(scoreline("1:0"),(1,0))
        self.assertIsNone(scoreline("2 (pens) - 1"))
        self.assertIsNone(integer_goals(-1))
        self.assertIsNone(integer_goals(True))


if __name__=="__main__":
    unittest.main()
