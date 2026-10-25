#!/usr/bin/env python3
"""NEXUS: public no-key football odds feed from TipsAudit's documented free API.

Only calls the explicitly documented public JSON endpoint, max once per run.
Bookmaker prices are labelled indicative: the API publishes the feed time, but
not necessarily the bookmaker's own update timestamp. Fair odds are modelled
prices, never bookmaker quotes. No bookmaker-site scraping or bypassing.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE = "https://tipsaudit.com/api/v1/predictions"
ATTRIBUTION = "https://tipsaudit.com/"
MAX_BYTES = 5_000_000
MAX_MATCHES = 4000


def iso_timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def price(value):
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
        if math.isfinite(x) and 1.01 < x < 1000:
            return round(x, 4)
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def parse(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("predictions"), list):
        raise ValueError("Incorrect public data feed schema")
    generated = iso_timestamp(payload.get("generated_at"))
    if not generated:
        raise ValueError("Public feed has no validated generation timestamp")
    out = []
    for item in payload["predictions"][:MAX_MATCHES]:
        if not isinstance(item, dict):
            continue
        kickoff = iso_timestamp(item.get("kickoff_utc"))
        home, away = str(item.get("home") or "").strip(), str(item.get("away") or "").strip()
        if not kickoff or not home or not away or not item.get("id"):
            continue
        fair = item.get("fair_odds") or {}
        if not isinstance(fair, dict):
            fair = {}
        derived = {side: price(fair.get(side)) for side in ("home", "draw", "away")}
        derived = {k: v for k, v in derived.items() if v is not None}
        soft = item.get("value") or {}
        quote = None
        if isinstance(soft, dict):
            best = price(soft.get("best_soft_odds"))
            book = str(soft.get("bookmaker") or "").strip()
            selection = str(soft.get("selection") or "").strip()
            # A seleção pode ser 1/X/2 ou home/draw/away.
            selection = {"1": "home", "X": "draw", "2": "away"}.get(selection.upper(), selection.lower())
            if best and book and selection in ("home", "draw", "away"):
                quote = {
                    "market": "1x2", "selection": selection,
                    "price": best, "bookmaker": book[:80],
                    "source": "TipsAudit public API",
                    "price_source_updated_at": None,
                    "feed_generated_at": generated,
                    "verification": "indicative_feed_quote_unconfirmed_source_time",
                }
        if not quote and not derived:
            continue
        out.append({
            "provider_match_id": str(item["id"])[:80],
            "league": str(item.get("league") or "")[:120],
            "home": home[:120], "away": away[:120],
            "kickoff_utc": kickoff,
            "benchmark_fair_odds": derived,
            "benchmark_is_bookmaker_price": False,
            "best_soft_bookmaker_quote": quote,
            "benchmark_read_at": iso_timestamp(item.get("fair_read_at")),
            "source_url": str(item.get("url") or "")[:350],
        })
    return {
        "schema": 1,
        "source": "TipsAudit free public API",
        "source_endpoint": SOURCE,
        "attribution_required": ATTRIBUTION,
        "generated_at": generated,
        "bookmaker_quote_scope": "indicative_1x2_only_not_order_book",
        "not_supported": "No confirmed matched volume, source quote timestamp or all bookmaker markets",
        "matches": out,
    }


def fetch(fetcher=urlopen):
    req = Request(SOURCE, headers={"Accept": "application/json",
                                  "User-Agent": "NEXUS-Research/1.0 (+https://github.com/lulualcides-sys/nexus-score-gratis)"})
    with fetcher(req, timeout=25) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Free feed exceeded safe payload size")
    return json.loads(raw)


def archive_changes(parsed, directory):
    """Persist changes in bookmaker price and fair benchmark by day, without repeat spam."""
    day = parsed["generated_at"][:10]
    target = Path(directory) / ("tipsaudit-" + day + ".json")
    try:
        existing = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
        if not isinstance(existing, dict):
            raise ValueError("Invalid previous public-source archive")
    except (ValueError, OSError) as exc:
        raise ValueError("Previous public-source archive cannot be read safely") from exc
    if not existing:
        existing = {"schema": 1, "day": day, "attribution_required": ATTRIBUTION, "matches": {}}
    changes = 0
    for item in parsed["matches"]:
        ident = item["provider_match_id"]
        key = ident + "|" + item["kickoff_utc"]
        rec = existing["matches"].setdefault(key, {
            "id": ident,
            "home": item["home"], "away": item["away"],
            "league": item["league"], "kickoff_utc": item["kickoff_utc"],
            "snapshots": [],
        })
        snap = {
            "fair_odds_modelled_not_bookmaker": item["benchmark_fair_odds"],
            "bookmaker_quote_indicative": item["best_soft_bookmaker_quote"],
            "benchmark_read_at": item["benchmark_read_at"],
        }
        if not rec["snapshots"] or any(
            rec["snapshots"][-1].get(k) != v for k, v in snap.items()
        ):
            rec["snapshots"].append({"observed_in_feed_at": parsed["generated_at"], **snap})
            changes += 1
    if changes:
        target.write_text(json.dumps(existing, separators=(",", ":"), ensure_ascii=False) + "\n",
                          encoding="utf-8")
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default="market-history")
    args = ap.parse_args()
    archive = Path(args.archive) / "public-no-key"
    archive.mkdir(parents=True, exist_ok=True)
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        data = parse(fetch())
        output = archive / "tipsaudit-latest.json"
        output.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        changes = archive_changes(data, archive)
        summary = {
            "checked_at": checked, "source": SOURCE, "status": "ok",
            "matches": len(data["matches"]), "history_changes": changes,
            "quotes_indicative": sum(x["best_soft_bookmaker_quote"] is not None for x in data["matches"]),
            "not_verified_as_tradable": True,
        }
        (archive / "status.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False))
    except Exception as exc:
        # This supplementary feed must not compromise the primary NEXUS.
        # Preserve last successful data; report unavailability without secrets.
        summary = {"checked_at": checked, "source": SOURCE, "status": "unavailable",
                   "reason": type(exc).__name__}
        (archive / "status.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
