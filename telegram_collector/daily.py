#!/usr/bin/env python3
"""Resumo diário do arquivo multimercado NEXUS, sem apostas nem odds inventadas."""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
from urllib import request
from zoneinfo import ZoneInfo

try:
    from telegram_collector.collect import MARKET_FAMILIES, FAMILY
except ModuleNotFoundError:
    from collect import MARKET_FAMILIES, FAMILY

TZ = ZoneInfo("America/Sao_Paulo")

def valid_time(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.timestamp() if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None

def strict_quote(quote, kickoff):
    """Cotação auditável: origem, casa, horário e fase corretamente delimitados."""
    if not isinstance(quote, dict):
        return False
    try:
        price = float(quote.get("odds"))
    except (TypeError, ValueError):
        return False
    if not 1.01 < price < 1000 or not quote.get("source") or not quote.get("bookmaker"):
        return False
    captured = valid_time(quote.get("captured_at"))
    if captured is None or kickoff is None or captured > datetime.now(timezone.utc).timestamp() + 120:
        return False
    scope = quote.get("scope")
    if scope == "pregame":
        return captured < kickoff
    if scope == "live":
        return captured >= kickoff
    return False

def summarize(document, day):
    records = document.get("games", {}) if isinstance(document, dict) else {}
    if not isinstance(records, dict):
        raise ValueError("Histórico com formato inválido")
    states = Counter()
    outcomes = Counter()
    families = Counter()
    names = Counter()
    books = Counter()
    sources = Counter()
    priced_fixtures = set()
    unique_quotes = set()
    finals = 0
    qualified_games = set()
    below_games = set()
    qualified_prices = set()
    for game_id, game in records.items():
        if not isinstance(game, dict):
            continue
        observations = game.get("observations") or []
        if not observations:
            continue
        best_status = "unknown"
        for obs in observations:
            liq = obs.get("liquidity") if isinstance(obs, dict) else {}
            if not isinstance(liq, dict):
                continue
            if liq.get("status") == "qualified" and liq.get("currency") == "BRL" and (
                    isinstance(liq.get("amount"), (int, float)) and liq["amount"] >= 3000
                    and liq.get("source") and valid_time(liq.get("observed_at"))):
                best_status = "qualified"
                break
            if liq.get("status") == "below" and liq.get("currency") == "BRL":
                best_status = "below"
        if best_status == "qualified":
            qualified_games.add(str(game_id))
        elif best_status == "below":
            below_games.add(str(game_id))
        latest = observations[-1]
        states[str(latest.get("phase") or "unknown")] += 1
        settled = latest.get("settlement") or {}
        if latest.get("phase") == "finished" and isinstance(settled, dict) and settled.get("match_odds") in ("home", "draw", "away"):
            finals += 1
            outcomes["1x2_" + settled["match_odds"]] += 1
            goals = settled.get("total_goals")
            if isinstance(goals, (int, float)):
                outcomes["over_2_5_" + ("yes" if goals > 2.5 else "no")] += 1
            btts = settled.get("both_teams_to_score")
            if isinstance(btts, bool):
                outcomes["btts_" + ("yes" if btts else "no")] += 1
            for field, prefix, line in (("total_corners", "corners_9_5", 9.5),
                                         ("total_yellow_cards", "cards_4_5", 4.5),
                                         ("total_shots_on_target", "sot_7_5", 7.5)):
                value = settled.get(field)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    outcomes[prefix + "_" + ("yes" if value > line else "no")] += 1
        for source in game.get("source") or []:
            if isinstance(source, str) and source:
                sources[source[:50]] += 1
        kickoff = game.get("kickoff_unix")
        try:
            kickoff = float(kickoff) if kickoff is not None else None
        except (TypeError, ValueError):
            kickoff = None
        for snapshot in observations:
            for quote in snapshot.get("odds") or []:
                if not strict_quote(quote, kickoff):
                    continue
                key = (str(game_id), str(quote.get("market")), str(quote.get("selection")),
                       str(quote.get("source")), str(quote.get("bookmaker")),
                       str(quote.get("captured_at")), str(quote.get("scope")), float(quote["odds"]))
                if key in unique_quotes:
                    continue
                unique_quotes.add(key)
                if str(game_id) in qualified_games:
                    qualified_prices.add(key)
                market = str(quote.get("market") or "unclassified")[:80]
                names[market] += 1
                families[FAMILY.get(market, market)] += 1
                books[str(quote["bookmaker"])[:70]] += 1
                priced_fixtures.add(str(game_id))
    return {
        "schema": 2, "day": day, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "games": len(records), "finished": finals,
        "live": states["live"], "scheduled": states["scheduled"],
        "quotes_verified": len(unique_quotes), "games_with_verified_odds": len(priced_fixtures),
        "liquidity_minimum_brl": 3000,
        "liquidity_qualified_games": len(qualified_games),
        "liquidity_below_games": len(below_games),
        "liquidity_unknown_games": len(records) - len(qualified_games) - len(below_games),
        "qualified_game_quotes_verified": len(qualified_prices),
        "market_families_catalogued": len(MARKET_FAMILIES),
        "market_families_with_verified_prices": len(families),
        "market_families_quoted": dict(families.most_common()),
        "market_names_quoted": dict(names.most_common()),
        "bookmakers": dict(books.most_common()), "sports_sources": dict(sources.most_common()),
        "results": dict(outcomes),
        "note": "Resultados esportivos e odds observadas; sem operação, ROI ou P/L validado."
    }

def format_message(s):
    r = s["results"]
    def pair(yes, no):
        return f'{r.get(yes, 0)} / {r.get(no, 0)}'
    markets = ", ".join(f"{k} ({n})" for k, n in list(s["market_families_quoted"].items())[:5]) or "Nenhum confirmado"
    books = ", ".join(f"{k} ({n})" for k, n in list(s["bookmakers"].items())[:4]) or "Nenhuma casa com odds auditáveis"
    return (
        f"📊 NEXUS DATA LAB | Diário {s['day']}\n"
        f"⚽ Partidas: {s['games']} | Finalizadas: {s['finished']} | Ao vivo: {s['live']}\n"
        f"💰 Volume confirmado ≥ R$ 3 mil: {s['liquidity_qualified_games']} jogos | "
        f"sem volume verificável: {s['liquidity_unknown_games']}\n"
        f"🎯 Odds auditáveis: {s['quotes_verified']} em {s['games_with_verified_odds']} jogos\n"
        f"📚 Famílias com odds: {s['market_families_with_verified_prices']}/{s['market_families_catalogued']}\n"
        f"Mercados: {markets}\n"
        f"Casas: {books}\n\n"
        f"✅ RESULTADOS CONFIRMADOS (sim/não)\n"
        f"1X2: casa {r.get('1x2_home',0)} | empate {r.get('1x2_draw',0)} | fora {r.get('1x2_away',0)}\n"
        f"Over 2.5: {pair('over_2_5_yes','over_2_5_no')}\n"
        f"Ambas marcam: {pair('btts_yes','btts_no')}\n"
        f"Escanteios >9.5: {pair('corners_9_5_yes','corners_9_5_no')}\n"
        f"Amarelos >4.5: {pair('cards_4_5_yes','cards_4_5_no')}\n"
        f"Chutes no alvo >7.5: {pair('sot_7_5_yes','sot_7_5_no')}\n\n"
        f"⚠️ Somente dados observados. Sem ROI ou lucro comprovado.\n"
        f"https://nexus-score-gratis.pages.dev/"
    )

def send(token, chat, message):
    payload = json.dumps({"chat_id": chat, "text": message}, ensure_ascii=False).encode("utf-8")
    req = request.Request("https://api.telegram.org/bot" + token + "/sendMessage",
                          data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=20) as resp:
        answer = json.loads(resp.read(20000))
    if answer.get("ok") is not True:
        raise RuntimeError("Telegram não confirmou recebimento")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", default="market-history")
    parser.add_argument("--day", default=None, help="Dia em America/Sao_Paulo, AAAA-MM-DD")
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()
    day = args.day or (datetime.now(TZ).date() - timedelta(days=1)).isoformat()
    datetime.strptime(day, "%Y-%m-%d")
    archive = Path(args.archive)
    raw = archive / (day + ".json")
    document = json.loads(raw.read_text(encoding="utf-8")) if raw.is_file() else {"games": {}}
    report = summarize(document, day)
    report_dir = archive / "daily"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / (day + ".json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(format_message(report), flush=True)
    if args.no_telegram:
        return
    marker = report_dir / (day + ".sent.json")
    if marker.exists():
        print("Relatório deste dia já enviado; sem repetição.", flush=True)
        return
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("Telegram não conectado nesta Action: confirme os Secrets existentes.", flush=True)
        return
    send(token, chat, format_message(report))
    marker.write_text(json.dumps({"day": day, "sent_at": datetime.now(timezone.utc).isoformat(),
                                  "message_type": "daily_data_report"}, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print("Relatório diário entregue ao Telegram.", flush=True)

if __name__ == "__main__":
    main()
