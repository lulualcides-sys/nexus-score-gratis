#!/usr/bin/env python3
"""NEXUS: retrospective walk-forward score test for independent football odds.

Each historical fixture is evaluated with all training dates STRICTLY earlier.
Never uses bookmaker prices or searches for a profitable bet. Reports Brier,
ranked probability score (RPS) and log loss (smaller is better); sample size
and league coverage remain explicit. Not a trading P/L backtest.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, time, timezone
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram_collector.model_only import (
    MODEL_VERSION, historical_rows, make_probability_book, team_rates,
)

BR=ZoneInfo("America/Sao_Paulo")
MAX_HOLDOUT_PER_LEAGUE=20
MIN_LEAGUE_ROWS=45
MIN_DIAGNOSTIC_SAMPLE=40


def outcome(home_goals, away_goals):
    return "1" if home_goals>away_goals else ("X" if home_goals==away_goals else "2")


def assessment(book, home_goals, away_goals):
    y=outcome(home_goals,away_goals)
    ft=book["ft_1x2"]
    v={k:float(ft[k]["probability"]) for k in ("1","X","2")}
    brier=sum((v[k]-int(k==y))**2 for k in v)
    rps=((v["1"]-int(y=="1"))**2
         +(v["1"]+v["X"]-int(y!="2"))**2)/2
    logloss=-math.log(max(1e-12,v[y]))
    total=book["ft_total_goals"]["2.5"]["Over"]["probability"]
    yes=book["btts_ft"]["Sim"]["probability"]
    brier_over=(total-int(home_goals+away_goals>2))**2
    brier_btts=(yes-int(home_goals>0 and away_goals>0))**2
    return brier,rps,logloss,brier_over,brier_btts


def evaluate(rows,now):
    by_league=defaultdict(list)
    for row in rows:
        if row["date"]<now.date():
            by_league[row["league"]].append(row)
    evaluated=defaultdict(list)
    excluded=Counter()
    for league,all_games in by_league.items():
        if len(all_games)<MIN_LEAGUE_ROWS:
            continue
        # Final distinct match dates are a strict chronological holdout.
        ordered=sorted(all_games,key=lambda g:(g["date"],g["home"],g["away"]))
        for row in ordered[-MAX_HOLDOUT_PER_LEAGUE:]:
            when=datetime.combine(row["date"],time(12),tzinfo=timezone.utc)
            fixture={"league_code":league,"home":row["home"],"away":row["away"],
                     "kickoff_unix":when.timestamp()}
            stats,reason=team_rates(rows,fixture,when)
            if stats is None:
                excluded[reason]+=1
                continue
            book=make_probability_book(stats["lambda_home_ft"],
                                       stats["lambda_away_ft"],
                                       stats["first_half_share"])
            evaluated[league].append(assessment(book,*row["ft"]))
    flat=[measure for entries in evaluated.values() for measure in entries]
    def avg(k):
        return round(sum(item[k] for item in flat)/len(flat),5) if flat else None
    return {"schema":1,"model_version":MODEL_VERSION,"evaluated_at":now.isoformat(),
            "status":"diagnostic_sample" if len(flat)>=MIN_DIAGNOSTIC_SAMPLE
                     else "insufficient_backtest_sample",
            "walk_forward":True,"uses_future_results_in_training":False,
            "only_goals_and_match_outcomes":True,
            "historical_matches_available":len(rows),
            "historical_fixtures_tested":len(flat),
            "leagues_tested":len(evaluated),
            "leagues_samples":dict(sorted(((code,len(measures)) for code,measures in
                                           evaluated.items()),key=lambda v:-v[1])),
            "skipped_reasons":dict(excluded),
            "brier_1x2":avg(0),
            "rps_1x2":avg(1),
            "log_loss_1x2":avg(2),
            "brier_over_2_5":avg(3),
            "brier_btts":avg(4),
            "explanation":("Test retrospective scored without later matches in each fit. "
                           "Lower metric is better; this alone does not establish "
                           "calibration, profitability or outperforming bookmakers.")}


def run(history,archive,now):
    rows=historical_rows(history,now)
    result=evaluate(rows,now)
    directory=Path(archive)/"model-only"
    directory.mkdir(parents=True,exist_ok=True)
    (directory/"backtest-latest.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in (
        "status","historical_matches_available","historical_fixtures_tested",
        "leagues_tested","brier_1x2","rps_1x2","brier_btts")},
        ensure_ascii=False))
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history-dir",default="history")
    p.add_argument("--archive",default="market-history")
    args=p.parse_args()
    run(args.history_dir,args.archive,datetime.now(timezone.utc))


if __name__=="__main__":
    main()
