#!/usr/bin/env python3
"""Coleta independente: lê apenas o snapshot PÚBLICO NEXUS e arquiva evidências sem inventar odds ou P/L."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib import request

SOURCE = "https://nexus-score-gratis.pages.dev/data.json"
MARKET_FAMILIES = (
    "match_odds", "double_chance", "draw_no_bet", "asian_handicap",
    "total_goals", "team_goals", "first_half_goals", "both_teams_to_score",
    "correct_score", "half_time", "half_time_full_time", "odd_even_goals",
    "first_goal", "last_goal", "clean_sheet", "total_corners",
    "team_corners", "corner_handicap", "total_yellow_cards",
    "team_yellow_cards", "red_cards", "total_shots", "total_shots_on_target",
    "big_chances", "total_fouls", "penalties", "goal_time"
)
STAT_FIELDS = ("corners", "shots_on", "shots_off", "shots_total", "yellow_cards",
               "red_cards", "big_chances", "fouls", "possession", "xg",
               "dangerous_attacks")
TOTAL_FIELDS = {"corners": "total_corners", "shots_on": "total_shots_on_target",
                "shots_total": "total_shots", "yellow_cards": "total_yellow_cards",
                "red_cards": "red_cards", "big_chances": "big_chances",
                "fouls": "total_fouls"}
FAMILY = {"1x2": "match_odds", "match_odds": "match_odds",
          "btts": "both_teams_to_score", "both_teams_to_score": "both_teams_to_score",
          "over_under": "total_goals", "over_under_25": "total_goals",
          "double_chance": "double_chance", "correct_score": "correct_score"}


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def finite_nonnegative(v):
    try:
        n = float(v)
        if n >= 0 and n < 100000 and n == n and n != float("inf"):
            return n
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def normalize_quotes(game):
    """Retém somente odds presentes, com hora e fonte. Sem odds de fechamento como entrada."""
    out = []
    for x in game.get("odds") or []:
        if not isinstance(x, dict):
            continue
        odd = finite_nonnegative(x.get("odd", x.get("odds")))
        if odd is None or odd <= 1.0:
            continue
        out.append({"market": str(x.get("market") or "1x2"),
                    "selection": str(x.get("sel") or x.get("selection") or ""),
                    "odds": odd, "source": str(x.get("source") or ""),
                    "bookmaker": str(x.get("bookmaker") or ""),
                    "captured_at": str(x.get("at") or x.get("captured_at") or ""),
                    "scope": str(x.get("phase") or "unverified_time_scope")})
    for group in ("odds_comparison", "live_odds_comparison"):
        for x in game.get(group) or []:
            if not isinstance(x, dict) or not isinstance(x.get("best"), dict):
                continue
            b = x["best"]
            odd = finite_nonnegative(b.get("odds"))
            if odd is None or odd <= 1.0:
                continue
            out.append({"market": str(x.get("market") or "unknown"),
                        "selection": str(x.get("selection") or ""),
                        "odds": odd, "source": str(b.get("source") or ""),
                        "bookmaker": str(b.get("bookmaker") or ""),
                        "captured_at": str(b.get("at") or ""),
                        "scope": str(x.get("phase") or ("live" if group.startswith("live") else "pregame"))})
    # O mesmo preço pode aparecer na lista e comparação. Deduplicação exata.
    unique = {}
    for q in out:
        key = json.dumps((q["market"], q["selection"], q["odds"],
                          q["source"], q["bookmaker"], q["captured_at"]), ensure_ascii=False)
        if key not in unique or q["scope"] != "unverified_time_scope":
            unique[key] = q
    return list(unique.values())


def settle_markets(game):
    """Resultados esportivos observados, sem inferir cotações, EV ou operação financeira."""
    if game.get("phase") != "finished":
        return {}
    score = re.fullmatch(r"(\d{1,2})-(\d{1,2})", str(game.get("score") or ""))
    if not score:
        return {}
    h, a = map(int, score.groups())
    out = {"match_odds": "home" if h > a else "away" if a > h else "draw",
           "total_goals": h + a, "home_goals": h, "away_goals": a,
           "both_teams_to_score": h > 0 and a > 0,
           "correct_score": f"{h}-{a}",
           "double_chance": {"1X": h >= a, "12": h != a, "X2": a >= h},
           "odd_even_goals": "even" if (h + a) % 2 == 0 else "odd"}
    stats = game.get("stats") or {}
    home, away = stats.get("home"), stats.get("away")
    if isinstance(home, dict) and isinstance(away, dict):
        for field, market in TOTAL_FIELDS.items():
            hv, av = finite_nonnegative(home.get(field)), finite_nonnegative(away.get(field))
            if hv is not None and av is not None:
                out[market] = hv + av
                out[f"{field}_home"] = hv
                out[f"{field}_away"] = av
    return out


def observation(game, collected_at):
    stats = game.get("stats") or {}
    limited_stats = {}
    for side in ("home", "away"):
        raw = stats.get(side) if isinstance(stats, dict) else None
        if isinstance(raw, dict):
            values = {k: raw[k] for k in STAT_FIELDS if finite_nonnegative(raw.get(k)) is not None}
            if values:
                limited_stats[side] = values
    return {"recorded_at": collected_at, "source_observed_at": game.get("observed_at"),
            "phase": game.get("phase"), "minute": game.get("minute"),
            "score": game.get("score"), "stats": limited_stats,
            "stats_observed_at": game.get("stats_observed_at"),
            "pressure_observed_at": game.get("pressure_observed_at"),
            "pressure_last_minute": game.get("pressure_last_minute"),
            "odds": normalize_quotes(game), "settlement": settle_markets(game)}


def signature(snapshot):
    # Não cria histórico falso a cada execução quando o estado esportivo não mudou.
    core = {k: v for k, v in snapshot.items()
            if k not in ("recorded_at", "source_observed_at", "stats_observed_at",
                         "pressure_observed_at")}
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def ingest_games(games, directory, collected_at):
    directory.mkdir(parents=True, exist_ok=True)
    by_day = {}
    for g in games:
        if not isinstance(g, dict):
            continue
        day, match_id = str(g.get("day") or ""), str(g.get("id") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or not match_id:
            continue
        by_day.setdefault(day, []).append(g)
    changed = 0
    for day, fixtures in by_day.items():
        dest = directory / (day + ".json")
        try:
            doc = json.loads(dest.read_text(encoding="utf-8")) if dest.exists() else {}
            if not isinstance(doc, dict):
                raise ValueError("invalid archive")
        except (OSError, ValueError) as exc:
            raise ValueError(f"Arquivo do histórico inválido: {dest}") from exc
        if not doc:
            doc = {"schema": 1, "day": day, "games": {}}
        modified = False
        for g in fixtures:
            match_id = str(g["id"])
            record = doc["games"].setdefault(match_id, {
                "id": match_id, "day": day, "home": str(g.get("home") or ""),
                "away": str(g.get("away") or ""), "league": str(g.get("league") or ""),
                "source": g.get("sources") or [g.get("source") or "unknown"],
                "kickoff_unix": g.get("start_timestamp"), "observations": []})
            snapshot = observation(g, collected_at)
            snap_hash = signature(snapshot)
            if not record["observations"] or signature(record["observations"][-1]) != snap_hash:
                record["observations"].append(snapshot)
                changed += 1
                modified = True
        if modified:
            dest.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return changed


def get_snapshot(url):
    if not url.startswith("https://"):
        raise ValueError("Somente HTTPS permitido para a fonte NEXUS")
    req = request.Request(url, headers={"User-Agent": "NexusMarketResearch/1.0", "Accept": "application/json"})
    with request.urlopen(req, timeout=45) as resp:
        payload = resp.read(40 * 1024 * 1024 + 1)
    if len(payload) > 40 * 1024 * 1024:
        raise ValueError("Snapshot NEXUS excedeu o limite de 40 MiB")
    result = json.loads(payload)
    if not isinstance(result, dict) or not isinstance(result.get("games"), list):
        raise ValueError("Formato de jogos incompatível com NEXUS")
    return result


def report_from_games(games, updated_at, changed):
    quotes, finished, live, market_names = 0, 0, 0, Counter()
    for game in games:
        if not isinstance(game, dict):
            continue
        live += game.get("phase") == "live"
        finished += game.get("phase") == "finished"
        q = normalize_quotes(game)
        quotes += len(q)
        for item in q:
            market_names[item["market"]] += 1
    families = {}
    for family in MARKET_FAMILIES:
        aliases = [k for k, v in FAMILY.items() if v == family]
        actual = sum(n for k, n in market_names.items() if FAMILY.get(k, k) == family or k in aliases)
        families[family] = {"prices_observed": actual,
                            "status": "odds_observed" if actual else "prices_unavailable"}
    return {"schema": 1, "collected_at": now_utc(), "nexus_exported_at": updated_at,
            "games_in_feed": len(games), "live_games_in_feed": live,
            "finished_games_in_feed": finished, "new_observations": changed,
            "quotes_observed": quotes, "market_families": families,
            "quoted_market_names": dict(market_names),
            "note": "Pesquisa e coleta: sem EV validado, sem execução, sem P/L real."}


def telegram_send(report):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("Telegram não configurado: configure os dois secrets no GitHub.", flush=True)
        return False
    if report["new_observations"] == 0:
        print("Sem novidades esportivas para notificar.", flush=True)
        return False
    markets = ", ".join(f"{k}: {n}" for k, n in sorted(
        report["quoted_market_names"].items(), key=lambda kv: -kv[1])[:7]) or "Nenhuma cotação verificável"
    msg = (f"📊 NEXUS | Coleta de mercados\n"
           f"Jogos na base: {report['games_in_feed']} | Ao vivo: {report['live_games_in_feed']}\n"
           f"Novas observações: {report['new_observations']}\n"
           f"Cotações observadas: {report['quotes_observed']}\n"
           f"Mercados com preços: {markets}\n"
           f"⚠️ Monitoramento de dados, não sinal de lucro ou aposta.\n"
           f"https://nexus-score-gratis.pages.dev/")
    payload = json.dumps({"chat_id": chat, "text": msg}, ensure_ascii=False).encode()
    req = request.Request("https://api.telegram.org/bot" + token + "/sendMessage",
                          data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=20) as response:
        result = json.loads(response.read(20000))
    if not result.get("ok"):
        raise RuntimeError("Telegram não confirmou o envio")
    print("Resumo enviado ao Telegram.", flush=True)
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default=os.environ.get("NEXUS_SOURCE_URL") or SOURCE)
    p.add_argument("--archive", default="market-history")
    p.add_argument("--no-telegram", action="store_true")
    args = p.parse_args()
    archive = Path(args.archive)
    try:
        result = get_snapshot(args.source)
        updated = str(result.get("exported_at") or "")
        if not updated:
            raise ValueError("Snapshot sem horário de exportação NEXUS")
        collected = now_utc()
        changed = ingest_games(result["games"], archive, collected)
        report = report_from_games(result["games"], updated, changed)
        (archive / "status.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({k: report[k] for k in (
            "collected_at", "nexus_exported_at", "games_in_feed",
            "new_observations", "quotes_observed")}, ensure_ascii=False))
        if not args.no_telegram:
            telegram_send(report)
    except Exception as exc:
        # Não declarar como coletado se o provedor ou Telegram falhar.
        print(f"Coleta com erro: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
