#!/usr/bin/env python3
"""NEXUS: movimentos de preço observados na Pinnacle, sem vazamento temporal.

Consome APENAS o histórico já coletado, não consulta apostas e não deduz odds.
Compara primeiro/último preço da MESMA seleção/linha/mercado em snapshots
pré-jogo com timestamp, e classifica variação em pontos de probabilidade implícita.
Nenhum movimento implica lucro, oportunidade de arbitragem ou execução.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from telegram_collector.pinnacle_guest import timestamp

MAX_MARKETS_PER_SNAPSHOT = 1200
MAX_GAME_SNAPSHOTS = 100
MAX_TOP = 15
MAX_FRESH_SECONDS = 4 * 3600


def normalized_price(q):
    if not isinstance(q, dict) or q.get("bookmaker") != "Pinnacle":
        return None
    market = str(q.get("raw_market_key") or "")[:150]
    family = str(q.get("market_family") or "")[:60]
    selection = str(q.get("selection") or "").strip().lower()[:60]
    if not market or not family or not selection:
        return None
    try:
        odds = float(q.get("odds_decimal"))
    except (ValueError, TypeError, OverflowError):
        return None
    if not math.isfinite(odds) or not 1.01 < odds < 1000:
        return None
    return (family, market, selection), odds


def summarize(document, now):
    if not isinstance(document, dict) or document.get("schema") != 1:
        raise ValueError("Unexpected Pinnacle archive schema")
    games = document.get("games")
    if not isinstance(games, dict):
        raise ValueError("Missing Pinnacle game history")
    changes = []
    touched = 0
    snapshots_read = 0
    bad = 0
    last_seen = None
    for match_id, game in games.items():
        if not isinstance(game, dict):
            continue
        kickoff = timestamp(game.get("kickoff_utc"))
        if kickoff is None:
            continue
        shots = game.get("snapshots")
        if not isinstance(shots, list):
            continue
        movements = {}
        valid_snapshots = 0
        # Never trust input ordering. A bounded slice protects against
        # accidentally loading a malformed/oversized history.
        for shot in sorted(shots[-MAX_GAME_SNAPSHOTS:],
                           key=lambda s: str(s.get("observed_at") or "") if isinstance(s, dict) else ""):
            if not isinstance(shot, dict):
                bad += 1
                continue
            shot_at = timestamp(shot.get("observed_at"))
            if shot_at is None or shot_at >= kickoff or shot_at > now:
                bad += 1
                continue
            quotes = shot.get("quotes")
            if not isinstance(quotes, list):
                bad += 1
                continue
            # Exactly one observation per selection in each captured snapshot.
            distinct = {}
            for quote in quotes[:MAX_MARKETS_PER_SNAPSHOT]:
                parsed = normalized_price(quote)
                if parsed is None:
                    bad += 1
                    continue
                ident, price = parsed
                observed_quote = timestamp(quote.get("observed_at"))
                if observed_quote is None or observed_quote > shot_at or observed_quote >= kickoff:
                    bad += 1
                    continue
                distinct[ident] = price
            if not distinct:
                continue
            valid_snapshots += 1
            snapshots_read += 1
            if last_seen is None or shot_at > last_seen:
                last_seen = shot_at
            for ident, quote_price in distinct.items():
                prev = movements.get(ident)
                if prev is None:
                    movements[ident] = [shot_at, quote_price, shot_at, quote_price, 1]
                else:
                    if shot_at > prev[2]:
                        prev[2], prev[3] = shot_at, quote_price
                    prev[4] += 1
        if valid_snapshots:
            touched += 1
        for (family, market, selection), (first_t, first_price, last_t, last_price, samples) in movements.items():
            if samples < 2 or last_t <= first_t or first_price == last_price:
                continue
            # Price growth means lower implied probability; do not call "green".
            change_pp = 100 * ((1 / last_price) - (1 / first_price))
            changes.append({
                "home": str(game.get("home") or "")[:90],
                "away": str(game.get("away") or "")[:90],
                "league": str(game.get("league") or "")[:90],
                "kickoff_utc": kickoff.isoformat(),
                "market_family": family,
                "raw_market_key": market,
                "selection": selection,
                "first_odds": round(first_price, 4),
                "last_odds": round(last_price, 4),
                "first_observed": first_t.isoformat(),
                "last_observed": last_t.isoformat(),
                "implied_probability_change_pp": round(change_pp, 3),
                "observations": samples,
                "source": "Pinnacle public guest historical captures",
                "betting_execution_confirmed": False,
            })
    changes.sort(key=lambda v: -abs(v["implied_probability_change_pp"]))
    age_s = (now-last_seen).total_seconds() if last_seen else None
    freshness = "fresh" if age_s is not None and 0 <= age_s <= MAX_FRESH_SECONDS else "historical_or_unavailable"
    return {
        "schema": 1,
        "checked_at": now.isoformat(),
        "day": str(document.get("observed_day") or ""),
        "status": freshness,
        "games_with_price_history": touched,
        "snapshots_processed": snapshots_read,
        "market_selections_with_changes": len(changes),
        "invalid_quote_records": bad,
        "newest_capture_at": last_seen.isoformat() if last_seen else None,
        "top_changes": changes[:MAX_TOP],
        "note": "Movimento calculado em odds observadas antes do jogo. Não é EV, ROI, lucro, volume ou recomendação."
    }


def run(folder, now):
    folder = Path(folder) / "public-no-key"
    day = now.astimezone(__import__("zoneinfo").ZoneInfo("America/Sao_Paulo")).date().isoformat()
    source = folder / ("pinnacle-" + day + ".json")
    target = folder / "pinnacle-motion-latest.json"
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
        report = summarize(data, now)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        report = {"schema":1, "checked_at":now.isoformat(), "day":day,
                  "status":"unavailable","error_type":type(exc).__name__,
                  "market_selections_with_changes":0,"top_changes":[]}
    target.write_text(json.dumps(report, ensure_ascii=False, separators=(",",":"))+"\n",
                      encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "top_changes"},ensure_ascii=False))
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",default="market-history")
    a=p.parse_args()
    run(Path(a.archive), datetime.now(timezone.utc))


if __name__=="__main__":
    main()
