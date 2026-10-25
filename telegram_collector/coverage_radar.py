#!/usr/bin/env python3
"""Auditoria da COBERTURA das partidas prioritárias, sem inferir preços ou liquidez.

Combina histórico NEXUS/ESPN com feed público TipsAudit. Preços da TipsAudit
sem timestamp da própria casa são APENAS indicativos e NÃO entram como odds
verificadas, operações simuladas ou acima de R$3k de liquidez.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from espn_scoreboard_odds import normalized_team
from telegram_collector.priority_espn import league_code, PRIORITY_ORDER
from telegram_collector.daily import strict_quote

ZONE = ZoneInfo("America/Sao_Paulo")
HORIZON_HOURS = 48
MAX_REPORTED_MISSING = 50


def unix(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.timestamp() if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def priority_match(league, record=None):
    # O código explícito do placar ESPN prevalece sobre nomes ambíguos.
    if isinstance(record,dict):
        code = str(record.get("league_code") or "")
        if code in PRIORITY_ORDER:
            return code
        gid = str(record.get("id") or "")
        for code in PRIORITY_ORDER:
            if gid.startswith("espn-" + code + "-"):
                return code
    return league_code(league)

def normalized_club(name):
    key = normalized_team(name)
    # Apenas aliases inequívocos, não fuzzy matching de times.
    aliases = {
        "lafc": "los angeles",
        "la galaxy": "los angeles galaxy",
        "academico de viseu": "academico viseu",
        "columbus crew ii": "columbus crew 2",
    }
    return aliases.get(key,key)


def same_teams_and_time(a, b):
    x, y = normalized_club(a.get("home")), normalized_club(a.get("away"))
    bx, by = normalized_club(b.get("home")), normalized_club(b.get("away"))
    if not all((x, y, bx, by)) or x != bx or y != by:
        return False
    left_code = priority_match(a.get("league"),a)
    right_code = priority_match(b.get("league"),b)
    if left_code and right_code and left_code != right_code:
        return False
    try:
        a_ts, b_ts = float(a["kickoff_unix"]), float(b["kickoff_unix"])
        return 0 < a_ts and abs(a_ts - b_ts) <= 600
    except (TypeError, ValueError, KeyError, OverflowError):
        return False


def verified_odds(record):
    """Somente observações reais do bookmaker, com hora, fase e origem."""
    found = set()
    kickoff = record.get("kickoff_unix")
    for obs in record.get("observations") or []:
        if not isinstance(obs, dict):
            continue
        for quote in obs.get("odds") or []:
            if strict_quote(quote, kickoff):
                found.add((str(quote.get("market")), str(quote.get("selection")),
                           str(quote.get("bookmaker")), str(quote.get("captured_at")),
                           float(quote["odds"])))
    return found


def collect_records(folder, now):
    folder = Path(folder)
    local = now.astimezone(ZONE).date()
    out = []
    # Covers midnight UTC/local boundaries without requesting stale seasons.
    for shift in (-1, 0, 1, 2):
        date = (local + timedelta(days=shift)).isoformat()
        f = folder / (date + ".json")
        if not f.is_file():
            continue
        document = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(document.get("games"), dict):
            raise ValueError("Histórico NEXUS malformado: " + date)
        for match_id, game in document["games"].items():
            if not isinstance(game, dict):
                continue
            try:
                kickoff = float(game.get("kickoff_unix") or 0)
            except (TypeError, ValueError, OverflowError):
                continue
            if not now.timestamp() - 3600 <= kickoff <= now.timestamp() + HORIZON_HOURS*3600:
                continue
            if not game.get("home") or not game.get("away"):
                continue
            code = priority_match(game.get("league"),{**game,"id":str(match_id)})
            if not code:
                continue
            observations = game.get("observations") or []
            status = observations[-1].get("phase") if observations and isinstance(observations[-1],dict) else "unknown"
            rec = {
                "home": str(game["home"]), "away": str(game["away"]),
                "league": str(game.get("league") or ""), "league_code": code,
                "kickoff_unix": kickoff, "phase": status,
                "data_sources": (game.get("source") if isinstance(game.get("source"),list)
                                 else [game["source"]] if isinstance(game.get("source"),str)
                                 else []),
                "verified_quotes": len(verified_odds(game)),
                "indicative_bookmaker_quotes": [],
                "fair_odds_modelled": None,
                "tipsaudit_source_url": None,
                "tipsaudit_id": None,
                "source_confirmed": "NEXUS or ESPN",
            }
            # Avoid duplicates of ESPN + FotMob by exact clubs and ±10 min.
            linked = next((old for old in out if same_teams_and_time(old, rec)),None)
            if linked:
                if rec["verified_quotes"] > linked["verified_quotes"]:
                    linked["verified_quotes"] = rec["verified_quotes"]
                for item in rec["data_sources"]:
                    if item not in linked["data_sources"]:
                        linked["data_sources"].append(item)
                continue
            out.append(rec)
    return out


def enrich_tipsaudit(records, path, now):
    path = Path(path)
    if not path.is_file():
        return {"status": "unavailable", "matched": 0, "indicative": 0, "new_priority": 0}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("matches"),list):
        raise ValueError("Malformed TipsAudit history; cannot join")
    matched, indicative, added = 0, 0, 0
    for item in data["matches"]:
        if not isinstance(item,dict):
            continue
        kickoff = unix(item.get("kickoff_utc"))
        if kickoff is None or kickoff < now.timestamp()-3600 or kickoff > now.timestamp()+HORIZON_HOURS*3600:
            continue
        code = priority_match(item.get("league"))
        if not code:
            continue
        target = {"home": str(item.get("home") or ""), "away": str(item.get("away") or ""),
                  "kickoff_unix": kickoff}
        if not target["home"] or not target["away"]:
            continue
        candidates = [r for r in records if same_teams_and_time(r, target)]
        if len(candidates) > 1:
            continue # no ambiguous union
        rec = candidates[0] if candidates else None
        if rec is None:
            rec = {
                **target, "league": str(item.get("league") or ""), "league_code": code,
                "phase": "unknown", "verified_quotes": 0,
                "indicative_bookmaker_quotes": [], "fair_odds_modelled": None,
                "tipsaudit_source_url": None, "tipsaudit_id": None,
                "source_confirmed": "TipsAudit schedule only", "data_sources": ["TipsAudit"],
            }
            records.append(rec)
            added += 1
        else:
            matched += 1
        rec["tipsaudit_id"] = str(item.get("provider_match_id") or "")[:80]
        rec["tipsaudit_source_url"] = str(item.get("source_url") or "")[:400]
        odds = item.get("best_soft_bookmaker_quote")
        # Do NOT treat modelled fair odds as bookmaker odds.
        if (isinstance(odds,dict) and odds.get("verification") ==
                "indicative_feed_quote_unconfirmed_source_time" and odds.get("bookmaker")
                and odds.get("price") and unix(odds.get("feed_generated_at")) is not None):
            rec["indicative_bookmaker_quotes"] = [{
                "selection": odds.get("selection"), "price": odds.get("price"),
                "bookmaker": odds.get("bookmaker"), "source": "TipsAudit",
                "status": "indicative_unverified_timestamp",
            }]
            indicative += 1
        fair = item.get("benchmark_fair_odds")
        if isinstance(fair,dict) and fair:
            rec["fair_odds_modelled"] = fair
    return {"status": "checked", "matched": matched, "indicative": indicative,
            "new_priority": added}



def enrich_pinnacle(records, path, now):
    """Usa apenas odds observadas do feed guest Pinnacle, sem preço inferido.

    Correspondência dos DOIS clubes e kickoff <= 10min, sem criar fixture
    fictícia e sem aceitar snapshot com mais de 4 horas.
    """
    path = Path(path)
    if not path.exists():
        return {"status": "unavailable", "matched": 0, "new_verified_game": 0,
                "offers": 0, "market_families": {}}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc,dict) or doc.get("schema") != 1:
        raise ValueError("Pinnacle guest snapshot schema mismatch")
    if not isinstance(doc.get("matches"),dict):
        raise ValueError("Pinnacle guest snapshot match list malformed")
    at = unix(doc.get("checked_at"))
    age = now.timestamp() - at if at is not None else float("inf")
    if not -120 <= age <= 4 * 3600:
        return {"status": "stale", "matched": 0, "new_verified_game": 0,
                "offers": 0, "market_families": {}}
    matched, gains, offers = 0, 0, 0
    fam = {}
    for entry in doc["matches"].values():
        if not isinstance(entry,dict):
            continue
        when = unix(entry.get("kickoff_utc"))
        if when is None or when <= now.timestamp()-3600 or when > now.timestamp()+HORIZON_HOURS*3600:
            continue
        target = {"home":entry.get("home"),"away":entry.get("away"),
                  "kickoff_unix":when}
        candidates = [rec for rec in records if same_teams_and_time(rec,target)]
        if len(candidates) != 1:
            continue
        good = set()
        prices = entry.get("odds") or []
        if not isinstance(prices,list):
            continue
        for q in prices:
            if not isinstance(q,dict) or q.get("bookmaker") != "Pinnacle":
                continue
            quote_at = unix(q.get("observed_at"))
            if quote_at is None or quote_at >= when or quote_at > now.timestamp() + 120:
                continue
            try:
                price = float(q.get("odds_decimal"))
            except (ValueError, TypeError, OverflowError):
                continue
            if not 1.01 < price < 1000 or not q.get("raw_market_key") or not q.get("selection"):
                continue
            key = (str(q["raw_market_key"]),str(q["selection"]),price,quote_at,str(q.get("line")))
            good.add(key)
            name = str(q.get("market_family") or "unclassified")
            fam[name] = fam.get(name,0)+1
        if not good:
            continue
        rec = candidates[0]
        had_price = rec.get("verified_quotes",0) > 0
        # Adiciona QUOTATIONS da Pinnacle, e não snapshots de odds justas
        # calculadas pelo TipsAudit.
        rec["pinnacle_guest_quotes"] = len(good)
        rec["verified_quotes"] = int(rec.get("verified_quotes") or 0) + len(good)
        sources = rec.setdefault("data_sources",[])
        if "Pinnacle guest" not in sources:
            sources.append("Pinnacle guest")
        matched += 1
        gains += not had_price
        offers += len(good)
    return {"status":"checked", "matched":matched, "new_verified_game":gains,
            "offers":offers, "market_families":fam}

def build(directory, now):
    folder = Path(directory)
    games = collect_records(folder, now)
    feed = enrich_tipsaudit(games, folder / "public-no-key" / "tipsaudit-latest.json", now)
    pinnacle = enrich_pinnacle(games, folder / "public-no-key" / "pinnacle-latest.json", now)
    games.sort(key=lambda g: (PRIORITY_ORDER.get(g["league_code"],999), g["kickoff_unix"],g["home"]))
    verified = [x for x in games if x["verified_quotes"]]
    indicative_only = [x for x in games if not x["verified_quotes"] and x["indicative_bookmaker_quotes"]]
    missing = [x for x in games if not x["verified_quotes"] and not x["indicative_bookmaker_quotes"]]
    for rec in games:
        rec["coverage"] = ("verified_price" if rec["verified_quotes"]
                           else "indicative_only" if rec["indicative_bookmaker_quotes"]
                           else "no_bookmaker_price")
    result = {
        "schema": 1, "checked_at": now.astimezone(timezone.utc).isoformat(),
        "horizon_hours": HORIZON_HOURS, "important_games": len(games),
        "verified_bookmaker_games": len(verified),
        "indicative_only_games": len(indicative_only),
        "missing_bookmaker_price_games": len(missing),
        "tipsaudit": feed,
        "pinnacle_guest": pinnacle,
        "priority_fixtures": games[:150],
        "top_missing": [{k:v for k,v in item.items() if k not in ("fair_odds_modelled",)}
                        for item in missing[:MAX_REPORTED_MISSING]],
        "explanation": ("Verified: timestamped source bookmaker quote. Indicative: bookmaker price from "
                        "third party without origin timestamp; not accepted as executable odd. "
                        "Missing: do not invent quote. No volume >3000 BRL inferred.")
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", default="market-history")
    args = parser.parse_args()
    folder = Path(args.archive)
    doc = build(folder, datetime.now(timezone.utc))
    target = folder / "priority-coverage.json"
    target.write_text(json.dumps(doc, indent=2, ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:doc[k] for k in (
        "checked_at","important_games","verified_bookmaker_games",
        "indicative_only_games","missing_bookmaker_price_games")},ensure_ascii=False))


if __name__ == "__main__":
    main()
