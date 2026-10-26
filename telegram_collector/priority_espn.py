#!/usr/bin/env python3
"""Fallback gratuito para cobertura de jogos importantes via placares ESPN públicos.

Somente GET JSON sem chave (não contorna login, proteção ou limites).
Guarda partidas sem odds como sem odds e preços 1X2 completos só antes do
apito, com bookmaker identificado e hora exata em que o feed foi observado.
Não modifica o NEXUS principal; escreve apenas na branch de dados.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from espn_scoreboard_odds import normalized_team, parse_ts
from odds_capture import threeway
from telegram_collector.collect import settle_markets

ZONE = ZoneInfo("America/Sao_Paulo")
API = "https://site.api.espn.com/apis/site/v2/sports/soccer/"
PRIORITY = (
    ("uefa.champions", "Champions League"),
    ("conmebol.libertadores", "Libertadores"),
    ("bra.1", "Brasileirão Série A"),
    ("eng.1", "Premier League"),
    ("esp.1", "La Liga"),
    ("ita.1", "Serie A Itália"),
    ("ger.1", "Bundesliga"),
    ("fra.1", "Ligue 1"),
    ("mex.1", "Liga MX"),
    ("arg.1", "Liga Profesional Argentina"),
    ("uefa.europa", "Europa League"),
    ("conmebol.sudamericana", "Sul-Americana"),
    ("usa.1", "MLS"),
    ("bra.copa_do_brazil", "Copa do Brasil"),
    ("por.1", "Liga Portugal"),
    ("ned.1", "Eredivisie"),
    ("col.1", "Colômbia Primera A"),
)
ALIASES = (
    ("uefa.champions", ("champions league", "uefa champions league", "liga dos campeoes")),
    ("conmebol.libertadores", ("libertadores", "copa libertadores", "conmebol libertadores")),
    ("conmebol.sudamericana", ("sudamericana", "sul americana", "sul-americana")),
    ("bra.copa_do_brazil", ("copa do brasil",)),
    ("bra.1", ("brasileirao", "brasileirao serie a", "brazilian serie a")),
    ("eng.1", ("premier league", "eng.1")),
    ("esp.1", ("laliga", "la liga", "esp.1")),
    ("ita.1", ("serie a italy", "serie a italia", "italian serie a", "ita.1")),
    ("ger.1", ("bundesliga", "ger.1")),
    ("fra.1", ("ligue 1", "fra.1")),
    ("mex.1", ("liga mx", "mex.1")),
    ("arg.1", ("liga profesional argentina", "argentine primera", "argentina primera", "arg.1")),
    ("uefa.europa", ("europa league", "uefa.europa")),
    ("usa.1", ("major league soccer", "mls", "usa.1")),
    ("por.1", ("liga portugal", "primeira liga portugal", "por.1")),
    ("ned.1", ("eredivisie", "ned.1")),
    ("col.1", ("colombian primera a", "colombia primera a", "col.1")),
)
PRIORITY_CODES = {code for code, _ in PRIORITY}
PRIORITY_ORDER = {code: i for i, (code, _) in enumerate(PRIORITY)}
MAX_BOARDS = 10
MAX_SUMMARIES = 3
SUMMARY_HORIZON_HOURS = 8
MAX_BYTES = 2_000_000
MATCH_WINDOW_SECONDS = 600
RUN_HORIZON_HOURS = 28


def league_code(name):
    """Only unequivocal competition names, never a fuzzy substring.

    'Canadian Premier League' != 'English Premier League';
    'MLS Next Pro' != 'MLS'; women's leagues != men's league codes.
    """
    key = normalized_team(name)
    if not key:
        return None
    excluded = ("femen", "feminin", "women", "womens", "feminil",
                "next pro", "premier league canada", "canadian premier",
                "sub 20", "u20", "u19", "u21", "u23", "reserves", "reserve",
                "juvenil", "youth", "segunda", "division 2")
    if any(x in key for x in excluded):
        return None
    # Generic "Premier League" is not a country identifier.
    if key == "premier league":
        return None
    for code, aliases in ALIASES:
        names = {normalized_team(code)} | {normalized_team(alias) for alias in aliases}
        # Some ESPN fixtures include a clearly delimited stage suffix.
        if key in names or any(
            key.startswith(alias + " " + stage)
            for alias in names if alias
            for stage in ("group", "round", "quarter", "semi", "final",
                          "playoff", "playoffs", "apertura", "clausura")
        ):
            return code
    return None


def valid_odds(offers, at, kickoff, source="ESPN public scoreboard"):
    """Um trio completo 1/X/2 do mesmo bookmaker. Sem bookmaker -> sem preço."""
    if not 0 < at < kickoff:
        return []
    clean = []
    for offer in offers if isinstance(offers, list) else [offers]:
        if not isinstance(offer, dict):
            continue
        provider = offer.get("provider")
        book = (provider.get("name") if isinstance(provider, dict) else provider) or offer.get("providerName")
        if not isinstance(book, str) or not book.strip():
            continue
        prices = threeway(offer)
        if set(prices) != {"home", "draw", "away"}:
            continue
        if any(not isinstance(x, (int,float)) or not math.isfinite(x)
               or x <= 1.01 or x >= 1000 for x in prices.values()):
            continue
        for selection in ("home", "draw", "away"):
            clean.append({
                "market": "1x2", "selection": selection, "odds": prices[selection],
                "source": source, "bookmaker": book.strip()[:60],
                "captured_at": datetime.fromtimestamp(at, timezone.utc).isoformat(),
                "scope": "pregame", "time_basis": "public_feed_observed",
            })
    return clean


def parse_event(event):
    if not isinstance(event, dict) or not str(event.get("id") or "").isdigit():
        return None
    ts = parse_ts(event.get("date"))
    if not ts:
        return None
    competitions = event.get("competitions")
    if not isinstance(competitions, list) or not competitions:
        return None
    comp = competitions[0]
    if not isinstance(comp, dict):
        return None
    competitors = comp.get("competitors") or []
    if not isinstance(competitors, list):
        return None
    home = [x for x in competitors if isinstance(x,dict) and x.get("homeAway") == "home"]
    away = [x for x in competitors if isinstance(x,dict) and x.get("homeAway") == "away"]
    if len(home) != 1 or len(away) != 1:
        return None
    def label(entry):
        team = entry.get("team") or {}
        return str(team.get("displayName") or team.get("name") or "").strip() if isinstance(team,dict) else ""
    h, a = label(home[0]), label(away[0])
    if not h or not a or normalized_team(h) == normalized_team(a):
        return None
    status = event.get("status") or {}
    status_type = status.get("type") if isinstance(status, dict) else {}
    state = status_type.get("state") if isinstance(status_type, dict) else None
    phase = {"pre": "scheduled", "in": "live", "post": "finished"}.get(state) if isinstance(state, str) else None
    if not phase:
        return None
    score = ""
    if phase == "finished":
        hs, ans = str(home[0].get("score") or ""), str(away[0].get("score") or "")
        if re.fullmatch(r"\d{1,2}", hs) and re.fullmatch(r"\d{1,2}", ans):
            score = hs + "-" + ans
    return {"espn_id": str(event["id"]), "ts": ts, "home": h, "away": a,
            "phase": phase, "score": score, "odds": comp.get("odds") or []}


def choose_boards(now, archives, max_boards=MAX_BOARDS):
    today = now.astimezone(ZONE).date()
    end = now.timestamp() + RUN_HORIZON_HOURS * 3600
    soon = {}
    for data in archives.values():
        if not isinstance(data, dict):
            continue
        for game in (data.get("games") or {}).values():
            if not isinstance(game, dict):
                continue
            if game.get("observations") and game["observations"][-1].get("phase") != "scheduled":
                continue
            try:
                kickoff = int(game.get("kickoff_unix") or 0)
            except (ValueError, TypeError):
                continue
            if not now.timestamp() < kickoff <= end:
                continue
            gid = str(game.get("id") or "")
            saved = str(game.get("league_code") or "")
            code = saved if saved in PRIORITY_CODES else league_code(game.get("league"))
            if not code:
                code = next((x for x in PRIORITY_CODES if gid.startswith("espn-" + x + "-")),None)
            if code:
                key = (code, datetime.fromtimestamp(kickoff, ZONE).date().isoformat())
                soon[key] = min(soon.get(key, kickoff), kickoff)
    board_dates = (today.isoformat(), (today + timedelta(days=1)).isoformat())
    urgent = sorted(soon, key=lambda item: (soon[item], PRIORITY_ORDER.get(item[0], 999)))
    selected = urgent[:max_boards]
    # Public league catalog from ESPN-API (GitHub), rotate remaining boards.
    routine = [(code, day) for day in board_dates for code, _ in PRIORITY]
    slot = now.hour * 3 + now.minute // 20
    start = (slot * max_boards) % len(routine)
    for offset in range(len(routine)):
        if len(selected) >= max_boards:
            break
        item = routine[(start + offset) % len(routine)]
        if item not in selected:
            selected.append(item)
    return selected


def http_board(code, day):
    if code not in PRIORITY_CODES or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("Unsupported ESPN scoreboard")
    url = API + code + "/scoreboard?" + urlencode({"dates": day.replace("-", ""), "limit": 100})
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "NEXUS-DataLab/1.0"})
    with urlopen(req, timeout=8) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("ESPN response too large")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError("Invalid ESPN response")
    return payload["events"]


def http_summary(code, event_id):
    """Officially public ESPN site JSON, without account/key; bounded fallback."""
    if code not in PRIORITY_CODES or not re.fullmatch(r"\d{1,16}", str(event_id)):
        raise ValueError("Invalid ESPN summary identifier")
    url = API + code + "/summary?" + urlencode({"event": event_id})
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "NEXUS-DataLab/1.0"})
    with urlopen(req, timeout=8) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("ESPN summary response too large")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Invalid ESPN summary JSON")
    picks = data.get("pickcenter")
    if isinstance(picks, (dict,list)) and picks:
        return picks if isinstance(picks,list) else [picks]
    header = data.get("header") or {}
    competitions = header.get("competitions") or [] if isinstance(header,dict) else []
    if isinstance(competitions,list) and competitions and isinstance(competitions[0],dict):
        prices = competitions[0].get("odds") or []
        return prices if isinstance(prices,list) else [prices]
    return []


def game_key(game):
    try:
        kickoff = int(game.get("kickoff_unix") or 0)
    except (ValueError, TypeError):
        return None
    h, a = normalized_team(game.get("home")), normalized_team(game.get("away"))
    return (h, a, kickoff) if h and a and kickoff else None


def add_fixture(archive, code, league, event, observed):
    """Associa por ambos os times e horário sem associar pares ambíguos."""
    day = datetime.fromtimestamp(event["ts"], ZONE).date().isoformat()
    doc = archive.setdefault(day, {"schema": 1, "day": day, "games": {}})
    records = doc["games"]
    candidates = []
    for key, game in records.items():
        match = game_key(game)
        if not match:
            continue
        if (match[0] == normalized_team(event["home"]) and
                match[1] == normalized_team(event["away"]) and
                abs(match[2] - event["ts"]) <= MATCH_WINDOW_SECONDS):
            candidates.append(key)
    if len(candidates) > 1:
        # Preferir o registro NEXUS do jogo pelo id canônico, sem duplicar preços.
        candidates.sort(key=lambda x: (0 if str(x).startswith("fotmob-") else 1, str(x)))
    eid = "espn-" + code + "-" + event["espn_id"]
    key = candidates[0] if candidates else eid
    if key not in records:
        records[key] = {"id": key, "home": event["home"], "away": event["away"],
                        "league": league, "league_code": code,
                        "day": day, "source": ["ESPN"],
                        "kickoff_unix": event["ts"], "observations": []}
        created = True
    else:
        created = False
    game = records[key]
    # Provenance: retain the ESPN ID for the SAME two teams and kickoff.
    # This allows low-cost public boxscore lookup for corners/cards/shots,
    # independently of prices. Never associate IDs from league mismatches.
    if (not game.get("league_code") or game.get("league_code") == code):
        game["espn_event_id"] = event["espn_id"]
        game["espn_league_code"] = code
    if not game.get("league_code") and str(key).startswith("espn-" + code + "-"):
        game["league_code"] = code
    previous = game.get("observations") or []
    if previous:
        last = previous[-1]
        phase = last.get("phase")
        # Never overwrite a finished game with a stale upstream scoreboard.
        if phase == "finished" and event["phase"] != "finished":
            return created, 0, key, False
    current = dict(previous[-1]) if previous else {
        "phase": event["phase"], "minute": 0, "score": event["score"],
        "stats": {}, "liquidity": {"status": "unknown", "minimum_brl": 3000},
        "settlement": {}}
    if not previous:
        current["recorded_at"] = observed
    if event["phase"] == "finished" and event["score"]:
        if not previous or current.get("phase") != "finished":
            current["phase"] = "finished"
            current["score"] = event["score"]
            current["settlement"] = settle_markets({"phase": "finished", "score": event["score"],
                                                    "stats": current.get("stats") or {}})
    quoted = valid_odds(event["odds"], datetime.fromisoformat(observed).timestamp(), event["ts"],
                        source=event.get("price_feed","ESPN public scoreboard")) if event["phase"] == "scheduled" else []
    prev_quotes = current.get("odds") or []
    if quoted:
        # Multiple bookmakers, each with a self-contained and timestamped trio.
        signatures = {(q.get("market"), q.get("selection"), q.get("bookmaker"),
                       q.get("captured_at"), q.get("odds")) for q in prev_quotes}
        fresh = [q for q in quoted if (q["market"], q["selection"], q["bookmaker"],
                  q["captured_at"], q["odds"]) not in signatures]
        current["odds"] = prev_quotes + fresh
        # Preserve all previous snapshots; never update old quote timestamps.
    else:
        fresh = []
    changed = not previous or (event["phase"] == "finished" and event["score"] and
                              previous[-1].get("phase") != "finished") or bool(fresh)
    if changed:
        current["recorded_at"] = observed
        game["observations"].append(current)
    return created, len(fresh), key, bool(quoted or current.get("odds"))


def run(directory, now, board_fetcher=http_board, max_boards=MAX_BOARDS,
        summary_fetcher=http_summary, max_summaries=MAX_SUMMARIES):
    """Never throw away existing data if a public endpoint fails."""
    directory = Path(directory)
    archive = {}
    tz_today = now.astimezone(ZONE).date()
    for i in (-1, 0, 1, 2):
        day = (tz_today + timedelta(days=i)).isoformat()
        file = directory / (day + ".json")
        if file.is_file():
            doc = json.loads(file.read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or not isinstance(doc.get("games"), dict):
                raise ValueError("Existing market archive corrupted: " + day)
            archive[day] = doc
    groups = choose_boards(now, archive, max_boards)
    report = {"schema": 1, "checked_at": now.isoformat(),
              "boards_requested": len(groups), "boards_ok": 0,
              "priority_fixtures_seen": 0, "created_games": 0,
              "new_quotes": 0, "summary_checks": 0, "summary_with_prices": 0,
              "errors": [], "missing_quote_fixtures": [],
              "source": "ESPN public JSON scoreboard no key",
              "scope": "Independent source, no liquidity claim"}
    observed = now.astimezone(timezone.utc).isoformat()
    touched = set()
    for code, day in groups:
        try:
            events = board_fetcher(code, day)
            if not isinstance(events, list):
                raise ValueError("Invalid scoreboard events")
            report["boards_ok"] += 1
        except Exception as exc:
            if len(report["errors"]) < 8:
                report["errors"].append({"league": code, "error": type(exc).__name__})
            continue
        league = dict(PRIORITY)[code]
        for raw in events[:100]:
            match = parse_event(raw)
            if match is None:
                continue
            # Never expand other dates or older seasons from a broken response.
            match_day = datetime.fromtimestamp(match["ts"], ZONE).date().isoformat()
            if match_day != day:
                continue
            report["priority_fixtures_seen"] += 1
            # A ESPN às vezes publica 1X2 no summary, mas não no scoreboard.
            # Limite pequeno por execução e apenas pré-jogo nas próximas 8h.
            if (match["phase"] == "scheduled" and now.timestamp() < match["ts"]
                    <= now.timestamp() + SUMMARY_HORIZON_HOURS * 3600
                    and report["summary_checks"] < max_summaries
                    and not valid_odds(match["odds"], now.timestamp(), match["ts"])):
                report["summary_checks"] += 1
                try:
                    extra = summary_fetcher(code, match["espn_id"])
                    if valid_odds(extra, now.timestamp(), match["ts"],
                                  source="ESPN public summary"):
                        match["odds"] = extra
                        match["price_feed"] = "ESPN public summary"
                        report["summary_with_prices"] += 1
                except Exception as exc:
                    if len(report["errors"]) < 8:
                        report["errors"].append({"league": code,
                                                 "event": match["espn_id"],
                                                 "source": "summary",
                                                 "error": type(exc).__name__})
            created, quotes, key, has_price = add_fixture(archive, code, league, match, observed)
            report["created_games"] += created
            report["new_quotes"] += quotes
            touched.add(match_day)
            if not has_price and len(report["missing_quote_fixtures"]) < 30:
                report["missing_quote_fixtures"].append({
                    "fixture": match["home"] + " x " + match["away"],
                    "league": code, "kickoff": match["ts"],
                    "reason": "no_verified_public_1x2",
                })
    directory.mkdir(parents=True, exist_ok=True)
    for day in touched:
        target = directory / (day + ".json")
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(archive[day], ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        tmp.replace(target)
    (directory / "priority-espn-status.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default="market-history")
    args = ap.parse_args()
    try:
        result = run(Path(args.archive), datetime.now(timezone.utc))
        print(json.dumps({k: v for k, v in result.items()
                          if k not in ("missing_quote_fixtures",)}, ensure_ascii=False))
    except Exception as exc:
        print("ESPN priority fallback: " + type(exc).__name__)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
