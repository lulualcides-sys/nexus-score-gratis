#!/usr/bin/env python3
"""Odds públicas da API 'guest' da Pinnacle, documentada no sportsdata-mcp.

Sem conta, chave pessoal, proxy ou tentativa de passar por bloqueios 401/403/429.
Usa a chave PÚBLICA do cliente web Pinnacle que consta em
DanielTomaro13/sportsdata-mcp (pinnacle.yaml) e limita o número de requisições.
Conserva linhas e market keys originais; nunca chama uma probabilidade de odd.
"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from zoneinfo import ZoneInfo

API = "https://guest.api.arcadia.pinnacle.com/0.1"
PUBLIC_WEB_CLIENT_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
REFERENCE = "https://github.com/DanielTomaro13/sportsdata-mcp/blob/main/src/sportsdata_mcp/specs/pinnacle.yaml"
SOCCER_SPORT_ID = 29
MAX_MATCHUPS = 12
MAX_PRICE_ITEMS = 240
MAX_BYTES = 6_000_000
LOCAL = ZoneInfo("America/Sao_Paulo")
IMPORTANT_TOKENS = (
    "champions league", "libertadores", "premier league", "serie a", "bundesliga",
    "la liga", "ligue 1", "liga mx", "brasileir", "europa league", "copa do brasil",
    "argentina", "eredivisie", "primeira liga", "liga portugal"
)


def decimal_american(value):
    """Odds US ±100 até ±100000; números decimais ou strings vazias rejeitados."""
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if not math.isfinite(n) or not 100 <= abs(n) <= 100000:
        return None
    return round(1 + (n / 100 if n > 0 else 100 / abs(n)), 4)


def timestamp(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def get_json(path, getter=urlopen):
    if not path.startswith("/") or "//" in path or "?" in path:
        raise ValueError("Invalid fixed guest feed URL")
    req = Request(API + path, headers={
        "Accept": "application/json",
        "User-Agent": "NEXUS-data-research/1.0",
        "Origin": "https://www.pinnacle.com",
        "Referer": "https://www.pinnacle.com/",
        "X-API-Key": PUBLIC_WEB_CLIENT_KEY,
    })
    # 401/403/429 always STOP. Do not retry, rotate identity, proxy or evade.
    with getter(req, timeout=12) as resp:
        payload = resp.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("Guest response exceeds 6 MiB")
    content = json.loads(payload)
    if not isinstance(content, (dict, list)):
        raise ValueError("Unexpected guest feed schema")
    return content


def parse_matchup(m, now):
    if not isinstance(m, dict) or m.get("isLive") is True:
        return None
    ident = m.get("id")
    if not isinstance(ident, int) or isinstance(ident, bool) or ident <= 0:
        return None
    start = timestamp(m.get("startTime"))
    if start is None or not now < start < now + timedelta(hours=72):
        return None
    participants = m.get("participants")
    if not isinstance(participants, list) or len(participants) < 2:
        return None
    sides = {}
    for p in participants:
        if not isinstance(p, dict):
            continue
        align = str(p.get("alignment") or "").casefold()
        label = str(p.get("name") or "").strip()
        if align in ("home", "away") and label:
            sides[align] = label
    if set(sides) != {"home", "away"}:
        return None
    l = m.get("league") or {}
    league = str(l.get("name") or "") if isinstance(l, dict) else ""
    return {
        "provider_matchup_id": ident, "home": sides["home"][:100],
        "away": sides["away"][:100], "league": league[:130],
        "kickoff_utc": start.isoformat(), "league_provider_id": l.get("id") if isinstance(l, dict) else None,
        "source": "Pinnacle public guest web feed",
    }


def classify_market(m, key):
    kind = str(m.get("type") or "").lower()
    label = str(m.get("name") or m.get("label") or "").lower()
    bits = key.lower().split(";")
    if len(bits) >= 3:
        code = bits[2]
        if code in ("m", "moneyline") and not kind:
            kind = "moneyline"
        if code in ("s", "spread") and not kind:
            kind = "spread"
        if code in ("t", "total") and not kind:
            kind = "total"
        if code in ("tt", "teamtotal") and not kind:
            kind = "teamtotal"
    combo = kind + " " + label
    if "corner" in combo:
        return "total_corners"
    if "card" in combo or "booking" in combo:
        return "total_yellow_cards"
    if "teamtotal" in combo or "team total" in combo:
        return "team_goals"
    if "spread" in combo or "handicap" in combo:
        return "asian_handicap"
    if "total" in combo or "over/under" in combo:
        return "total_goals"
    if "moneyline" in combo or "match odds" in combo:
        return "match_odds"
    return "unclassified"


def parse_markets(raw, observed):
    if isinstance(raw,dict):
        raw = next((raw[k] for k in ("markets","data","items")
                    if isinstance(raw.get(k),list)), None)
    if not isinstance(raw, list):
        return []
    quotes = []
    for market in raw[:MAX_PRICE_ITEMS]:
        if not isinstance(market, dict):
            continue
        if market.get("status") in ("suspended", "closed", "settled", "cancelled"):
            continue
        cutoff = timestamp(market.get("cutoffAt"))
        if cutoff is not None and cutoff <= observed:
            continue
        key = str(market.get("key") or "").strip()[:150]
        if not key:
            continue
        prices = market.get("prices")
        if not isinstance(prices, list):
            continue
        for price in prices[:10]:
            if not isinstance(price, dict):
                continue
            odd = decimal_american(price.get("price"))
            selection = str(price.get("designation") or "").strip().lower()
            if not odd or not selection:
                continue
            line = price.get("points")
            try:
                line = float(line) if line is not None else None
                if line is not None and not math.isfinite(line):
                    line = None
            except (ValueError, TypeError, OverflowError):
                line = None
            quotes.append({
                "raw_market_key": key,
                "market_family": classify_market(market, key),
                "period": market.get("period"),
                "selection": selection[:60],
                "line": line,
                "american_price": price["price"],
                "odds_decimal": odd,
                "bookmaker": "Pinnacle",
                "source": "Pinnacle public guest web feed",
                "observed_at": observed.isoformat(),
                "source_market_cutoff_at": cutoff.isoformat() if cutoff else None,
                "odds_kind": "guest_feed_observation_not_execution",
            })
    return quotes


def get_focus_matches(payload, now, limit=MAX_MATCHUPS):
    # Alguns endpoints guest retornam lista direta; outros encapsulam em
    # 'matchups' ou 'data'. Não tratar envelopes de erro como catálogo vazio.
    if isinstance(payload, dict):
        payload = next((payload[k] for k in ("matchups", "data", "items")
                        if isinstance(payload.get(k), list)), None)
    if not isinstance(payload, list):
        raise ValueError("Matchup listing has no supported list envelope")
    matches = [m for m in (parse_matchup(row, now) for row in payload) if m]
    def priority(m):
        league = m["league"].lower()
        priority_value = 0 if any(t in league for t in IMPORTANT_TOKENS) else 1
        return (priority_value, m["kickoff_utc"], m["provider_matchup_id"])
    return sorted(matches, key=priority)[:limit]


def run(directory, now, getter=get_json, max_games=MAX_MATCHUPS):
    directory = Path(directory) / "public-no-key"
    directory.mkdir(parents=True, exist_ok=True)
    status = {
        "checked_at": now.astimezone(timezone.utc).isoformat(),
        "source": "Pinnacle public Arcadia guest",
        "source_reference": REFERENCE,
        "status": "ok", "matches_discovered": 0,
        "matches_checked": 0, "new_price_snapshots": 0,
        "odds_observed": 0, "market_families": {}, "errors": [],
        "requires_account": False, "requires_user_api_key": False,
        "guarantees_available_to_bet": False, "liquidity_verified": False,
    }
    target = directory / "pinnacle-latest.json"
    archive = directory / ("pinnacle-" + now.astimezone(LOCAL).date().isoformat() + ".json")
    try:
        response = getter("/sports/29/matchups/highlighted")
        games = get_focus_matches(response, now, max_games)
        status["matches_discovered"] = (len(response) if isinstance(response,list) else
                                        len(next((response[k] for k in ("matchups","data","items")
                                                  if isinstance(response.get(k),list)),[])))
        result = {}
        known = {}
        if archive.exists():
            previous = json.loads(archive.read_text(encoding="utf-8"))
            if not isinstance(previous, dict) or not isinstance(previous.get("games"), dict):
                raise ValueError("Pinnacle archive malformed")
            known = previous["games"]
        for game in games:
            mid = game["provider_matchup_id"]
            try:
                markets = getter("/matchups/" + str(mid) + "/markets/related/straight")
                prices = parse_markets(markets, now)
            except (HTTPError, URLError, ValueError, TimeoutError, OSError) as e:
                code = getattr(e,"code",None)
                if len(status["errors"]) < 10:
                    status["errors"].append({"matchup_id":mid,"error":type(e).__name__,
                                             "http_status":code,
                                             "reason":str(e)[:120]})
                # Never continue cycling events if guest feed denies access or
                # imposes a rate limit. Keep earlier successful observations.
                if code in (401,403,429):
                    status["status"] = ("partial_blocked" if status["matches_checked"]
                                        else "blocked")
                    break
                continue
            status["matches_checked"] += 1
            result[str(mid)] = {**game, "odds": prices}
            status["odds_observed"] += len(prices)
            for q in prices:
                name = q["market_family"]
                status["market_families"][name] = status["market_families"].get(name,0) + 1
            if prices:
                digest = hashlib.sha256(json.dumps(
                    [(q["raw_market_key"],q["selection"],q["line"],q["odds_decimal"]) for q in prices],
                    sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
                old = known.setdefault(str(mid), {**game,"snapshots":[]})
                if not old["snapshots"] or old["snapshots"][-1]["checksum"] != digest:
                    old["snapshots"].append({
                        "observed_at": now.isoformat(),
                        "checksum": digest, "quotes": prices,
                    })
                    status["new_price_snapshots"] += 1
        if result:
            content = {"schema":1,"checked_at":now.isoformat(),
                       "source":status["source"],"matches":result}
            target.write_text(json.dumps(content,ensure_ascii=False,separators=(",",":"))+"\n",
                              encoding="utf-8")
        if status["new_price_snapshots"]:
            archive.write_text(json.dumps({
                "schema":1,"source":status["source"],
                "observed_day":now.astimezone(LOCAL).date().isoformat(),
                "games":known
            },ensure_ascii=False,separators=(",",":"))+"\n", encoding="utf-8")
    except (HTTPError, URLError, ValueError, TimeoutError, OSError) as exc:
        status["status"] = "unavailable"
        status["errors"].append({"error":type(exc).__name__,
                                 "http_status":getattr(exc,"code",None),
                                 "reason":str(exc)[:120]})
        # STOP on blocked feed. No retry, fake headers, proxies or credential guessing.
    (directory/"pinnacle-status.json").write_text(json.dumps(status,indent=2,ensure_ascii=False)+"\n",
                                                  encoding="utf-8")
    print(json.dumps(status,ensure_ascii=False))
    return status


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--archive", default="market-history")
    args = arg.parse_args()
    run(Path(args.archive), datetime.now(timezone.utc))


if __name__ == "__main__":
    main()
