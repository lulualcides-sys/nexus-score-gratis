#!/usr/bin/env python3
"""NEXUS public ESPN soccer boxscore fallback: corners, cards and shots.

Reads only ESPN public soccer summary JSON for already verified matches.
No logins, keys, browser evasion, price invention, or third-party credentials.
Preserves market prices; imports observed TEAM STATS separately so finished
sports-market outcomes can be settled only when both teams have real counts.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from espn_scoreboard_odds import normalized_team
from telegram_collector.collect import settle_markets
from telegram_collector.priority_espn import PRIORITY_CODES

ZONE = ZoneInfo("America/Sao_Paulo")
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/"
MAX_FETCH = 6
MAX_RESPONSE_BYTES = 2_000_000
MIN_RETRY_FINISHED_SECONDS = 3 * 3600
MIN_RETRY_LIVE_SECONDS = 18 * 60
FIELDS = {
    "wonCorners": "corners",
    "cornerKicks": "corners",
    "yellowCards": "yellow_cards",
    "redCards": "red_cards",
    "shotsOnTarget": "shots_on",
    "totalShots": "shots_total",
    "fouls": "fouls",
}
SIDE_MIN_VALIDATION = ("corners", "yellow_cards", "shots_on", "shots_total")


def as_count(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str) and not re.fullmatch(r"\s*\d{1,4}\s*", value):
        return None
    try:
        val = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if math.isfinite(val) and 0 <= val <= 9999 and val.is_integer():
        return int(val)
    return None


def utc_seconds(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.timestamp() if dt.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def fetch_summary(code, event_id):
    if code not in PRIORITY_CODES or not re.fullmatch(r"\d{1,16}", str(event_id)):
        raise ValueError("Invalid ESPN event path")
    url = BASE + code + "/summary?" + urlencode({"event":str(event_id)})
    request = Request(url, headers={"User-Agent":"NEXUS-Football-Research/1.0",
                                    "Accept":"application/json"})
    with urlopen(request, timeout=9) as response:
        raw = response.read(MAX_RESPONSE_BYTES+1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("ESPN boxscore too large")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("ESPN returned unexpected summary schema")
    return payload


def parse_boxscore(payload, home, away):
    """Require both TEAM identities; unknown stat is ABSENT, not zero."""
    box = payload.get("boxscore") if isinstance(payload, dict) else None
    if not isinstance(box, dict) or not isinstance(box.get("teams"), list):
        return None
    hnorm, anorm = normalized_team(home), normalized_team(away)
    if not hnorm or not anorm or hnorm == anorm:
        return None
    sides = {}
    for item in box["teams"]:
        if not isinstance(item,dict) or not isinstance(item.get("team"),dict):
            continue
        label = str(item["team"].get("displayName") or item["team"].get("name") or "")
        name = normalized_team(label)
        if name not in (hnorm,anorm):
            continue
        side = "home" if name == hnorm else "away"
        if side in sides:
            return None
        raw = item.get("statistics")
        if not isinstance(raw,list):
            continue
        stats={}
        for stat in raw:
            if not isinstance(stat,dict):
                continue
            mapped = FIELDS.get(stat.get("name"))
            if not mapped:
                continue
            count=as_count(stat.get("value"))
            if count is not None:
                stats[mapped]=count
        sides[side]=stats
    if set(sides) != {"home","away"}:
        return None
    if not any(k in sides["home"] and k in sides["away"] for k in SIDE_MIN_VALIDATION):
        return None
    return sides


def already_complete(snapshot):
    stats = snapshot.get("stats") or {}
    if not isinstance(stats,dict):
        return False
    a,b=stats.get("home"),stats.get("away")
    return bool(isinstance(a,dict) and isinstance(b,dict) and
                all(key in a and key in b for key in SIDE_MIN_VALIDATION))


def should_query(game, now):
    if not isinstance(game,dict):
        return False
    code=str(game.get("espn_league_code") or "")
    event_id=str(game.get("espn_event_id") or "")
    if code not in PRIORITY_CODES or not re.fullmatch(r"\d{1,16}",event_id):
        return False
    previous=game.get("observations") or []
    if not previous or not isinstance(previous[-1],dict):
        return False
    last=previous[-1]
    phase=last.get("phase")
    if phase not in ("live","finished"):
        return False
    kickoff=game.get("kickoff_unix")
    try:
        kickoff=float(kickoff)
    except (TypeError,ValueError,OverflowError):
        return False
    if (not math.isfinite(kickoff) or kickoff > now.timestamp()
            or kickoff < now.timestamp()-36*3600):
        return False
    if phase=="finished" and already_complete(last):
        return False
    checked=utc_seconds(game.get("espn_boxscore_last_checked"))
    wait=MIN_RETRY_LIVE_SECONDS if phase=="live" else MIN_RETRY_FINISHED_SECONDS
    if checked is not None and -120 <= now.timestamp()-checked < wait:
        return False
    return True


def apply_stats(game, data, observed):
    previous = game.get("observations") or []
    if not previous or not isinstance(previous[-1],dict):
        return False,0
    latest=previous[-1]
    parsed=parse_boxscore(data,game.get("home"),game.get("away"))
    if not parsed:
        return False,0
    # Do not ever rewrite bookmaker quotes, kickoff, or phase.
    updated=dict(latest)
    old_stats=latest.get("stats") or {}
    if not isinstance(old_stats,dict):
        old_stats={}
    combined={}
    new_fields=0
    for side in ("home","away"):
        prior=old_stats.get(side)
        side_stats=dict(prior) if isinstance(prior,dict) else {}
        for key,value in parsed[side].items():
            if side_stats.get(key) != value:
                new_fields+=1
            side_stats[key]=value
        combined[side]=side_stats
    if not new_fields:
        return False,0
    updated["stats"]=combined
    updated["stats_observed_at"]=observed
    updated["stats_source"]="ESPN public soccer boxscore"
    updated["recorded_at"]=observed
    if updated.get("phase")=="finished":
        # This only adds outcomes when both sides have observed counters.
        updated["settlement"]=settle_markets(updated)
    game["observations"].append(updated)
    return True,new_fields


def run(folder, now, fetcher=fetch_summary, max_requests=MAX_FETCH):
    folder=Path(folder)
    local=now.astimezone(ZONE).date()
    candidates=[]
    files={}
    for offset in (-1,0,1):
        day=(local+timedelta(days=offset)).isoformat()
        file=folder/(day+".json")
        if not file.is_file():
            continue
        doc=json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(doc,dict) or not isinstance(doc.get("games"),dict):
            raise ValueError("Malformed existing market archive: "+day)
        files[day]=doc
        for game in doc["games"].values():
            if should_query(game,now):
                recent=(game.get("observations") or [{}])[-1]
                # Prioritize live and recently finished priority games.
                kickoff=float(game["kickoff_unix"])
                order=(0 if recent.get("phase")=="live" else 1,
                       -kickoff if recent.get("phase")=="finished" else kickoff)
                candidates.append((order,day,game))
    candidates.sort(key=lambda item:item[0])
    report={"schema":1,"checked_at":now.isoformat(),"status":"ok",
            "candidates":len(candidates),"checked":0,"games_enriched":0,
            "observed_statistics_fields":0,"errors":[],
            "source":"ESPN public soccer summary / boxscore",
            "bookmaker_odds_observed":0,"liquidity_verified":False}
    touched=set()
    for _,day,game in candidates[:max_requests]:
        code,id_=game["espn_league_code"],game["espn_event_id"]
        try:
            summary=fetcher(code,id_)
            changed,count=apply_stats(game,summary,now.astimezone(timezone.utc).isoformat())
            report["checked"]+=1
            report["games_enriched"]+=int(changed)
            report["observed_statistics_fields"]+=count
            game["espn_boxscore_last_checked"]=now.isoformat()
            touched.add(day)
        except Exception as exc:
            if len(report["errors"])<6:
                report["errors"].append({"event_id":id_,"type":type(exc).__name__})
    if not report["checked"] and report["errors"]:
        report["status"]="unavailable"
    for day in touched:
        path=folder/(day+".json")
        temp=path.with_suffix(".stats.tmp")
        temp.write_text(json.dumps(files[day],ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
        temp.replace(path)
    (folder/"priority-boxscore-status.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",default="market-history")
    args=p.parse_args()
    result=run(args.archive,datetime.now(timezone.utc))
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
