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
            last = observations[-1] if observations and isinstance(observations[-1],dict) else {}
            status = last.get("phase") or "unknown"
            stats = last.get("stats") or {}
            home_stats = stats.get("home") if isinstance(stats,dict) else None
            away_stats = stats.get("away") if isinstance(stats,dict) else None
            def both_observed(field):
                return (status in ("live","finished") and
                        isinstance(home_stats,dict) and isinstance(away_stats,dict)
                        and isinstance(home_stats.get(field),(int,float))
                        and isinstance(away_stats.get(field),(int,float))
                        and not isinstance(home_stats[field],bool)
                        and not isinstance(away_stats[field],bool)
                        and 0 <= home_stats[field] < 10000 and 0 <= away_stats[field] < 10000)
            rec = {
                "home": str(game["home"]), "away": str(game["away"]),
                "league": str(game.get("league") or ""), "league_code": code,
                "kickoff_unix": kickoff, "phase": status,
                "data_sources": (game.get("source") if isinstance(game.get("source"),list)
                                 else [game["source"]] if isinstance(game.get("source"),str)
                                 else []),
                "verified_quotes": len(verified_odds(game)),
                "observed_corner_counts": both_observed("corners"),
                "observed_card_counts": both_observed("yellow_cards"),
                "observed_shots_on_counts": both_observed("shots_on"),
                "boxscore_stats_source": str(last.get("stats_source") or "")[:80],
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
                for field in ("observed_corner_counts","observed_card_counts","observed_shots_on_counts"):
                    linked[field] = bool(linked.get(field)) or rec[field]
                if rec["boxscore_stats_source"] and not linked.get("boxscore_stats_source"):
                    linked["boxscore_stats_source"]=rec["boxscore_stats_source"]
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



def enrich_official_corners_cards(records, directory, now):
    """Only authenticated *owner-supplied* free API quotes, matched exactly.

    Never conflate observed sports stats with real bookmaker odds; no key
    means no quotes and no fabricated liquidity claim.
    """
    from telegram_collector.optional_odds_api import as_utc, MARKET_KEYS
    folder=Path(directory)
    seen=set()
    family_counts={"total_corners":0,"total_cards":0}
    priced_games=set()
    checked_files=0
    for day_offset in (-1,0):
        day=(now.astimezone(ZONE).date()+timedelta(days=day_offset)).isoformat()
        file=folder/("quotes-"+day+".json")
        if not file.is_file():
            continue
        data=json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(data,dict) or data.get("schema")!=1 or not isinstance(data.get("matches"),dict):
            continue
        checked_files+=1
        for event_id,event in data["matches"].items():
            if not isinstance(event,dict):
                continue
            kickoff=as_utc(event.get("kickoff_utc"))
            if kickoff is None:
                continue
            target={"home":event.get("home"),"away":event.get("away"),
                    "kickoff_unix":kickoff.timestamp(),
                    "league_code":event.get("league_code")}
            candidates=[x for x in records if same_teams_and_time(x,target)]
            if len(candidates)!=1:
                continue
            game=candidates[0]
            for obs in event.get("observations") or []:
                if not isinstance(obs,dict):
                    continue
                at=as_utc(obs.get("captured_at"))
                if at is None or not at < kickoff or not -120 <= (now-at).total_seconds() <= 4*3600:
                    continue
                for q in obs.get("prices") or []:
                    if not isinstance(q,dict) or not q.get("bookmaker"):
                        continue
                    family=q.get("market_family")
                    if family not in MARKET_KEYS.values() or MARKET_KEYS.get(q.get("raw_market_key")) != family:
                        continue
                    source_at=as_utc(q.get("bookmaker_market_updated_at"))
                    if source_at is None or not source_at <= at or source_at >= kickoff:
                        continue
                    if q.get("source")!="The Odds API free official user-key feed":
                        continue
                    try:
                        price=float(q["odds_decimal"])
                        line=float(q["line"])
                    except (ValueError,TypeError,OverflowError,KeyError):
                        continue
                    if not 1.01<price<1000 or not 0<line<100:
                        continue
                    if q.get("selection") not in ("over","under"):
                        continue
                    id_=(event_id,str(q["bookmaker"]),family,line,q["selection"],at.isoformat(),price)
                    if id_ in seen:
                        continue
                    seen.add(id_)
                    family_counts[family]+=1
                    priced_games.add(id(game))
                    game["verified_quotes"]=int(game.get("verified_quotes") or 0)+1
                    key="official_verified_"+family+"_quotes"
                    game[key]=int(game.get(key) or 0)+1
                    sources=game.setdefault("data_sources",[])
                    if "The Odds API official free" not in sources:
                        sources.append("The Odds API official free")
    return {"status":"checked" if checked_files else "no_observed_prices",
            "priced_games":len(priced_games),
            "verified_corners_quotes":family_counts["total_corners"],
            "verified_cards_quotes":family_counts["total_cards"],
            "files_checked":checked_files,
            "liquidity_verified":False}


def read_book_quality(path, now):
    """Não repassar indicadores de preços antigos como se fossem atuais."""
    path=Path(path)
    if not path.is_file():
        return {"status":"unavailable"}
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        at=unix(data.get("checked_at")) if isinstance(data,dict) else None
        if (not isinstance(data,dict) or data.get("schema")!=1
                or data.get("status")!="fresh" or at is None
                or not -120 <= now.timestamp()-at <= 4*3600):
            return {"status":"stale"}
        return {
            "status":"fresh",
            "bookmaker_snapshot_at":data.get("bookmaker_snapshot_at"),
            "complete_market_lines":int(data.get("complete_market_lines",0)),
            "incomplete_market_lines":int(data.get("incomplete_market_lines",0)),
            "odds_eligible_for_quality":int(data.get("odds_eligible_for_quality",0)),
            "invalid_quote_records":int(data.get("invalid_quote_records",0)),
            "families":data.get("families") or {},
        }
    except (OSError,ValueError,TypeError):
        return {"status":"unavailable"}



def read_price_movements(path, now):
    """Movimentos só se houve duas cotações pré-jogo e última coleta recente."""
    path = Path(path)
    if not path.is_file():
        return {"status":"unavailable"}
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        at=unix(data.get("checked_at")) if isinstance(data,dict) else None
        if (not isinstance(data,dict) or data.get("schema")!=1 or
                data.get("status")!="fresh" or at is None or
                not -120 <= now.timestamp()-at <= 4*3600):
            return {"status":"stale"}
        rows=data.get("top_changes")
        if not isinstance(rows,list):
            return {"status":"unavailable"}
        good=[]
        for row in rows[:15]:
            if not isinstance(row,dict) or row.get("betting_execution_confirmed") is not False:
                continue
            try:
                delta=float(row.get("implied_probability_change_pp"))
                start=unix(row.get("first_observed"))
                end=unix(row.get("last_observed"))
                kickoff=unix(row.get("kickoff_utc"))
            except (ValueError,TypeError,OverflowError):
                continue
            if (start is None or end is None or kickoff is None or
                    not start < end < kickoff or abs(delta)>100 or
                    not row.get("home") or not row.get("away") or
                    not row.get("raw_market_key") or not row.get("selection")):
                continue
            good.append({k:row[k] for k in ("home","away","market_family",
                                          "raw_market_key","selection",
                                          "first_odds","last_odds",
                                          "implied_probability_change_pp")})
        return {
            "status":"fresh", "selections_with_changes":int(
                data.get("market_selections_with_changes") or 0),
            "historical_snapshots":int(data.get("snapshots_processed") or 0),
            "top_changes":good[:3],
        }
    except (OSError,ValueError,TypeError,KeyError,OverflowError):
        return {"status":"unavailable"}


def build(directory, now):
    folder = Path(directory)
    games = collect_records(folder, now)
    feed = enrich_tipsaudit(games, folder / "public-no-key" / "tipsaudit-latest.json", now)
    pinnacle = enrich_pinnacle(games, folder / "public-no-key" / "pinnacle-latest.json", now)
    official = enrich_official_corners_cards(games, folder / "official-free-odds", now)
    quality = read_book_quality(folder / "public-no-key" / "pinnacle-depth.json", now)
    movements = read_price_movements(folder / "public-no-key" / "pinnacle-motion-latest.json", now)
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
        "games_with_corners_stats": sum(bool(x.get("observed_corner_counts")) for x in games),
        "games_with_yellow_cards_stats": sum(bool(x.get("observed_card_counts")) for x in games),
        "games_with_shots_on_target_stats": sum(bool(x.get("observed_shots_on_counts")) for x in games),
        "tipsaudit": feed,
        "pinnacle_guest": pinnacle,
        "official_corners_cards": official,
        "book_quality": quality,
        "price_movements": movements,
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
