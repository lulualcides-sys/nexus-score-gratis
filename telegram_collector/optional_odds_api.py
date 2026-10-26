#!/usr/bin/env python3
"""Optional official FREE The Odds API for soccer corners/cards, fail-closed.

User-owned THE_ODDS_API_KEY GitHub secret REQUIRED. No key -> no HTTP calls.
Never creates/logs in to accounts, invents prices, uses third-party keys or
exceeds an intentionally conservative FREE-tier local budget.
Provider: the-odds-api.com (NOT the similarly named theoddsapi.com).
"""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from telegram_collector.coverage_radar import same_teams_and_time

BR=ZoneInfo("America/Sao_Paulo")
API="https://api.the-odds-api.com/v4/sports/"
ALLOWED_SPORTS={
    "eng.1":"soccer_epl",
    "esp.1":"soccer_spain_la_liga",
    "ger.1":"soccer_germany_bundesliga",
    "ita.1":"soccer_italy_serie_a",
    "fra.1":"soccer_france_ligue_one",
    "bra.1":"soccer_brazil_campeonato",
    "arg.1":"soccer_argentina_primera_division",
    "mex.1":"soccer_mexico_ligamx",
    "usa.1":"soccer_usa_mls",
    "por.1":"soccer_portugal_primeira_liga",
    "ned.1":"soccer_netherlands_eredivisie",
    "uefa.champions":"soccer_uefa_champs_league",
    "uefa.europa":"soccer_uefa_europa_league",
    "conmebol.libertadores":"soccer_conmebol_copa_libertadores",
    "conmebol.sudamericana":"soccer_conmebol_copa_sudamericana",
}
MARKET_KEYS={
    "alternate_totals_corners":"total_corners",
    "alternate_totals_cards":"total_cards",
}
MAX_DAILY_EVENTS=2
MAX_FREE_EVENT_LISTS=8
MAX_MONTHLY_LOCAL_CREDITS=240
MIN_PROVIDER_CREDITS_LEFT=20
MAX_RESPONSE=1_500_000


def as_utc(value):
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError,ValueError,OverflowError):
        return None


def get_json(sport, event_id, key, reader=urlopen):
    if sport not in ALLOWED_SPORTS.values():
        raise ValueError("Invalid sport code")
    if event_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",str(event_id)):
        raise ValueError("Invalid provider event ID")
    url=API+sport+"/"
    if event_id is None:
        url+="events?"
        params={"apiKey":key}
    else:
        url+="events/"+str(event_id)+"/odds?"
        params={"apiKey":key,"regions":"uk","markets":",".join(MARKET_KEYS),
                "oddsFormat":"decimal"}
    request=Request(url+urlencode(params),headers={
        "Accept":"application/json",
        "User-Agent":"NEXUS-public-football-research/1.0",
    })
    # No retries, no logging URLs containing the user-provided API secret.
    with reader(request,timeout=12) as response:
        data=response.read(MAX_RESPONSE+1)
        header={name:response.headers.get(name) for name in
                ("x-requests-last","x-requests-remaining")}
    if len(data)>MAX_RESPONSE:
        raise ValueError("Official odds response too large")
    parsed=json.loads(data)
    return parsed,header



def probe_key(key, reader=urlopen):
    """Free /v4/sports credential check, zero API credits per provider docs.

    Return only a boolean and the public quota number: never print URL/token.
    """
    request=Request("https://api.the-odds-api.com/v4/sports/?" +
                    urlencode({"apiKey":key}),headers={
                        "Accept":"application/json",
                        "User-Agent":"NEXUS-public-football-research/1.0"})
    with reader(request,timeout=12) as response:
        raw=response.read(MAX_RESPONSE+1)
        remaining=response.headers.get("x-requests-remaining")
    if len(raw)>MAX_RESPONSE:
        raise ValueError("Provider credential-check response too large")
    payload=json.loads(raw)
    if not isinstance(payload,list):
        raise ValueError("Provider credential-check unexpected schema")
    remaining_count=None
    if remaining is not None:
        try:
            remaining_count=max(0,int(remaining))
        except (ValueError,TypeError):
            pass
    return {"valid":True, "remaining_credits":remaining_count}


def parse_market_prices(payload, match, checked):
    """No odds unless exact event identity, bookmaker, price and time match."""
    if not isinstance(payload,dict) or not isinstance(payload.get("bookmakers"),list):
        return []
    kickoff=as_utc(match["kickoff_utc"])
    if kickoff is None or not checked < kickoff:
        return []
    if str(payload.get("id") or "")!=str(match.get("provider_event_id")):
        return []
    listed={
        "home":payload.get("home_team"),
        "away":payload.get("away_team"),
        "kickoff_unix":kickoff.timestamp(),
    }
    expected={
        "home":match["home"],"away":match["away"],
        "kickoff_unix":kickoff.timestamp(),
    }
    if not same_teams_and_time(listed,expected):
        return []
    output=[]
    for house in payload["bookmakers"][:60]:
        if not isinstance(house,dict):
            continue
        bookmaker=str(house.get("title") or "").strip()[:80]
        if not bookmaker or not isinstance(house.get("markets"),list):
            continue
        for market in house["markets"][:40]:
            if not isinstance(market,dict):
                continue
            family=MARKET_KEYS.get(market.get("key"))
            updated=as_utc(market.get("last_update"))
            if family is None or updated is None or updated > checked or updated >= kickoff:
                continue
            outcomes=market.get("outcomes")
            if not isinstance(outcomes,list):
                continue
            for outcome in outcomes[:60]:
                if not isinstance(outcome,dict):
                    continue
                selection=str(outcome.get("name") or "").strip().lower()
                if selection not in ("over","under"):
                    continue
                try:
                    odd=float(outcome.get("price"))
                    line=float(outcome.get("point"))
                except (ValueError,TypeError,OverflowError):
                    continue
                if (not math.isfinite(odd) or not 1.01<odd<1000 or
                        not math.isfinite(line) or not 0<line<100):
                    continue
                output.append({
                    "market_family":family,
                    "raw_market_key":market["key"],
                    "selection":selection,
                    "line":line,"odds_decimal":round(odd,5),
                    "bookmaker":bookmaker,
                    "provider_event_id":payload["id"],
                    "captured_at":checked.isoformat(),
                    "bookmaker_market_updated_at":updated.isoformat(),
                    "source":"The Odds API free official user-key feed",
                    "liquidity_verified":False,
                    "bet_executed":False,
                })
    return output


def read_targets(folder, now):
    path=Path(folder)/"priority-coverage.json"
    if not path.is_file():
        return []
    report=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report,dict) or report.get("schema")!=1:
        return []
    updated=as_utc(report.get("checked_at"))
    if updated is None or not -120 <= (now-updated).total_seconds() <= 3*3600:
        return []
    targets=[]
    for game in report.get("priority_fixtures") or []:
        if not isinstance(game,dict) or game.get("league_code") not in ALLOWED_SPORTS:
            continue
        kickoff=float(game.get("kickoff_unix") or 0)
        if not now.timestamp() < kickoff <= now.timestamp()+36*3600:
            continue
        # Match odds / goal odds do not imply ANY corners/cards pricing.
        # Search these missing markets even if 1X2 is fully verified.
        has_corners = int(game.get("official_verified_total_corners_quotes") or 0) > 0
        has_cards = int(game.get("official_verified_total_cards_quotes") or 0) > 0
        if has_corners and has_cards:
            continue
        targets.append({**game,"kickoff_utc":datetime.fromtimestamp(kickoff,timezone.utc).isoformat()})
    targets.sort(key=lambda g:g["kickoff_unix"])
    return targets[:24]


def daily_budget(folder,now):
    month=now.astimezone(BR).strftime("%Y-%m")
    file=Path(folder)/("budget-"+month+".json")
    if not file.is_file():
        return file,{"schema":1,"month":month,"local_credits_reserved":0,"daily_lookups":{}}
    d=json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(d,dict) or d.get("schema")!=1 or d.get("month")!=month:
        raise ValueError("Budget ledger invalid")
    return file,d


def atomic_write(path,data):
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":"))+"\n",
                   encoding="utf-8")
    tmp.replace(path)


def run(folder, now, key=None, getter=get_json, probe=None):
    archive=Path(folder)/"official-free-odds"
    archive.mkdir(parents=True,exist_ok=True)
    status={"schema":1,"checked_at":now.isoformat(),
            "source":"The Odds API (the-odds-api.com)",
            "status":"no_key","events_matched":0,
            "event_odds_requests":0,"prices_observed":0,"matches_checked":0,
            "market_families":{},"errors":[],
            "account_required":True,"bookmaker_volume_verified":False}
    key=key if key is not None else os.getenv("THE_ODDS_API_KEY","")
    if not key:
        atomic_write(archive/"status.json",status)
        return status
    status["key_configured"]=True
    if probe is not None:
        try:
            verified=probe(key)
            if not isinstance(verified,dict) or verified.get("valid") is not True:
                raise ValueError("Unexpected credential verification")
            status["credential_status"]="verified"
            remaining=verified.get("remaining_credits")
            if isinstance(remaining,int):
                status["provider_credits_remaining"]=remaining
                if remaining < MIN_PROVIDER_CREDITS_LEFT:
                    status["status"]="provider_quota_low"
                    atomic_write(archive/"status.json",status)
                    return status
        except HTTPError as exc:
            status["credential_status"]="invalid_or_restricted"
            status["status"]="invalid_key_or_permission" if exc.code in (401,403) else "key_validation_failed"
            status["errors"].append({"status":exc.code,"type":"HTTPError"})
            atomic_write(archive/"status.json",status)
            return status
        except (URLError,ValueError,OSError,TimeoutError) as exc:
            status["credential_status"]="unverified"
            status["status"]="key_validation_failed"
            status["errors"].append({"type":type(exc).__name__})
            atomic_write(archive/"status.json",status)
            return status
    ledger_path,ledger=daily_budget(archive,now)
    day=now.astimezone(BR).date().isoformat()
    used=ledger.setdefault("daily_lookups",{}).setdefault(day,[])
    reserved=int(ledger.get("local_credits_reserved") or 0)
    if len(used)>=MAX_DAILY_EVENTS or reserved+2>MAX_MONTHLY_LOCAL_CREDITS:
        status["status"]="local_quota_guard"
        atomic_write(archive/"status.json",status)
        return status
    targets=read_targets(Path(folder),now)
    status["eligible_priority_games"]=len(targets)
    status["status"]="ok" if targets else "key_valid_no_eligible_fixture"
    events_cache={}
    for target in targets:
        if len(used)>=MAX_DAILY_EVENTS or reserved+2>MAX_MONTHLY_LOCAL_CREDITS:
            break
        sport=ALLOWED_SPORTS[target["league_code"]]
        identity=(sport+"|"+target["home"]+"|"+target["away"]+"|"+target["kickoff_utc"])
        if identity in used:
            continue
        try:
            if sport not in events_cache:
                if len(events_cache)>=MAX_FREE_EVENT_LISTS:
                    status["free_event_list_limit_reached"]=True
                    break
                listing,_=getter(sport,None,key)
                if not isinstance(listing,list):
                    raise ValueError("Official event list invalid")
                events_cache[sport]=listing
                status["free_event_lists_checked"]=len(events_cache)
                status["free_events_seen"]=int(status.get("free_events_seen") or 0)+len(listing)
            events=events_cache[sport]
            possibles=[]
            for event in events:
                if not isinstance(event,dict):
                    continue
                check={
                    "home":event.get("home_team"),
                    "away":event.get("away_team"),
                    "kickoff_unix":as_utc(event.get("commence_time")).timestamp()
                    if as_utc(event.get("commence_time")) else None,
                }
                if same_teams_and_time(target,check):
                    possibles.append(event)
            if len(possibles)!=1:
                if len(possibles)==0:
                    status["events_not_matched"]=int(status.get("events_not_matched") or 0)+1
                else:
                    status["ambiguous_events"]=int(status.get("ambiguous_events") or 0)+1
                continue
            event_id=str(possibles[0].get("id") or "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",event_id):
                continue
            match={**target,"provider_event_id":event_id}
            # Reserve the maximum 2 market credits BEFORE the paid request,
            # preventing repeated calls after transient network failures.
            reserved+=2
            ledger["local_credits_reserved"]=reserved
            used.append(identity)
            atomic_write(ledger_path,ledger)
            status["event_odds_requests"]+=1
            prices,headers=getter(sport,event_id,key)
            remain=headers.get("x-requests-remaining")
            if remain is not None:
                try:
                    if int(remain) < MIN_PROVIDER_CREDITS_LEFT:
                        status["status"]="provider_quota_low"
                except (ValueError,TypeError):
                    pass
            parsed=parse_market_prices(prices,match,now)
            status["events_matched"]+=1
            status["matches_checked"]+=1
            status["prices_observed"]+=len(parsed)
            for q in parsed:
                fam=q["market_family"]
                status["market_families"][fam]=status["market_families"].get(fam,0)+1
            if parsed:
                file=archive/("quotes-"+day+".json")
                data=json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {
                    "schema":1,"day":day,"matches":{}}
                games=data.setdefault("matches",{})
                rec=games.setdefault(event_id,{
                    "home":match["home"],"away":match["away"],
                    "kickoff_utc":match["kickoff_utc"],
                    "league_code":target["league_code"],"source":"The Odds API",
                    "observations":[]})
                rec["observations"].append({"captured_at":now.isoformat(),"prices":parsed})
                atomic_write(file,data)
            if status["status"]=="provider_quota_low":
                break
        except HTTPError as exc:
            status["errors"].append({"status":exc.code,"type":"HTTPError"})
            if exc.code in (401,403,429):
                status["status"]="restricted_or_quota"
                break
        except (URLError,ValueError,OSError,TypeError,OverflowError) as exc:
            status["errors"].append({"type":type(exc).__name__})
    atomic_write(archive/"status.json",status)
    return status


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",default="market-history")
    args=p.parse_args()
    report=run(args.archive,datetime.now(timezone.utc),probe=probe_key)
    print(json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
