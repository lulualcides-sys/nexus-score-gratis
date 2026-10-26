#!/usr/bin/env python3
"""Saúde das fontes GRATUITAS já coletadas pelo NEXUS.

Não faz requisições de rede. Lê somente os status existentes e distingue
indisponibilidade, atrasos, falta de odds e cobertura de jogos importantes.
Não transforma volume não confirmado em liquidez de mercado.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

SOURCES = (
    ("nexus", "status.json", "collected_at", 75*60, "quotes_observed"),
    ("espn_priority", "priority-espn-status.json", "checked_at", 75*60, "new_quotes"),
    ("espn_boxscore", "priority-boxscore-status.json", "checked_at", 75*60, "observed_statistics_fields"),
    ("tipsaudit", "public-no-key/status.json", "checked_at", 75*60, "quotes_indicative"),
    ("pinnacle", "public-no-key/pinnacle-status.json", "checked_at", 4*3600, "odds_observed"),
)


def epoch(value):
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return dt.timestamp() if dt.tzinfo is not None else None
    except (ValueError,TypeError,OverflowError):
        return None


def assess(root, now):
    checks={}
    for name, rel, time_key, max_age, quote_field in SOURCES:
        path=Path(root)/rel
        item={"status":"unavailable", "age_minutes":None, "odds_observed":None,
              "source_file":rel}
        try:
            d=json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(d,dict):
                raise ValueError("Invalid status file")
            stamp=epoch(d.get(time_key))
            age=now.timestamp()-stamp if stamp is not None else None
            if age is None or age < -120 or age > max_age:
                item["status"]="stale"
            else:
                flag=d.get("status") or "ok"
                if flag in ("blocked","partial_blocked","unavailable"):
                    item["status"]=flag
                else:
                    item["status"]="ok"
            if age is not None:
                item["age_minutes"]=round(age/60,1)
            quote=d.get(quote_field)
            if isinstance(quote,int) and not isinstance(quote,bool) and quote >= 0:
                if name=="espn_boxscore":
                    item["statistics_fields_observed"]=quote
                else:
                    item["odds_observed"]=quote
            if name == "pinnacle":
                item["games_priced"]=d.get("matches_checked",0)
                item["denied_requests"]=sum(
                    1 for error in d.get("errors",[]) if
                    isinstance(error,dict) and error.get("http_status") in (401,403,429))
            if name == "espn_boxscore":
                item["summaries_checked"]=d.get("checked",0)
                item["games_with_stats_enriched"]=d.get("games_enriched",0)
            if name == "espn_priority":
                item["scoreboards_checked"]=d.get("boards_ok",0)
                item["priority_fixtures_seen"]=d.get("priority_fixtures_seen",0)
        except (OSError,ValueError,TypeError):
            pass
        checks[name]=item

    radar_path=Path(root)/"priority-coverage.json"
    priority={"status":"unavailable","important_games":None,
              "verified_bookmaker_games":None,"missing_bookmaker_price_games":None}
    try:
        doc=json.loads(radar_path.read_text(encoding="utf-8"))
        at=epoch(doc.get("checked_at"))
        if (isinstance(doc,dict) and at is not None and
                -120 <= now.timestamp()-at <= 75*60):
            priority={"status":"ok","important_games":doc.get("important_games"),
                      "verified_bookmaker_games":doc.get("verified_bookmaker_games"),
                      "missing_bookmaker_price_games":doc.get("missing_bookmaker_price_games")}
        else:
            priority["status"]="stale"
    except (OSError,TypeError,ValueError):
        pass
    available=sum(x["status"]=="ok" for x in checks.values())
    return {
        "schema":1, "checked_at":now.isoformat(),
        "source_count":len(SOURCES), "sources_ok":available,
        "source_status":checks,
        "priority_coverage":priority,
        "overall_status":("ok" if available==len(SOURCES)
                          else "degraded" if available>0 else "unavailable"),
        "important":("Sources marked ok mean freshness/availability, NOT that every fixture "
                     "has verified bookmaker prices or matched liquidity.")
    }


def run(folder, now):
    path=Path(folder)
    report=assess(path,now)
    target=path/"source-health.json"
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in
                      ("checked_at","overall_status","source_count","sources_ok")},ensure_ascii=False))
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",default="market-history")
    args=p.parse_args()
    run(args.archive,datetime.now(timezone.utc))


if __name__=="__main__":
    main()
