#!/usr/bin/env python3
"""Controle de qualidade do livro público de odds: consistência, margem e completude.

Nenhum preço é inventado. Overround é calculado somente quando TODAS as
seleções de um mesmo mercado/linha estão presentes na MESMA observação.
Não é estimativa de ROI, lucro ou liquidez e não implica execução de aposta.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path

EXPECTED = {
    "match_odds": {"home", "draw", "away"},
    "half_time": {"home", "draw", "away"},
    "total_goals": {"over", "under"},
    "first_half_goals": {"over", "under"},
    "team_goals": {"over", "under"},
    "first_half_team_goals": {"over", "under"},
    "asian_handicap": {"home", "away"},
    "first_half_handicap": {"home", "away"},
}
MAX_AGE_SECONDS = 4 * 3600


def timestamp(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.timestamp() if dt.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def summarize(document, now):
    if not isinstance(document, dict) or not isinstance(document.get("matches"), dict):
        raise ValueError("Missing bookmaker match archive")
    clock = timestamp(document.get("checked_at"))
    age = now.timestamp() - clock if clock is not None else float("inf")
    if not -120 <= age <= MAX_AGE_SECONDS:
        raise ValueError("Bookmaker quote snapshot is stale")
    families = defaultdict(lambda: {"games":set(), "raw_quotes":0, "complete_lines":0,
                                    "incomplete_lines":0, "overround_samples":[]})
    quoted_games = 0
    invalid = 0
    seen_prices = 0
    incomplete = 0
    complete = 0
    example = []
    for match_id, game in document["matches"].items():
        if not isinstance(game, dict):
            continue
        kickoff = timestamp(game.get("kickoff_utc"))
        if kickoff is None:
            continue
        grouped = defaultdict(dict)
        usable = False
        for quote in game.get("odds") or []:
            if not isinstance(quote, dict):
                invalid += 1
                continue
            observed = timestamp(quote.get("observed_at"))
            family = str(quote.get("market_family") or "")
            if not (observed is not None and observed < kickoff
                    and observed <= now.timestamp() + 120
                    and -120 <= now.timestamp()-observed <= MAX_AGE_SECONDS
                    and family in EXPECTED and
                    quote.get("bookmaker") == "Pinnacle" and quote.get("raw_market_key")):
                invalid += 1
                continue
            try:
                odd = float(quote.get("odds_decimal"))
            except (TypeError, ValueError, OverflowError):
                invalid += 1
                continue
            if not math.isfinite(odd) or not 1.01 < odd < 1000:
                invalid += 1
                continue
            selection = str(quote.get("selection") or "").lower()
            if selection not in EXPECTED[family]:
                invalid += 1
                continue
            market_key = str(quote["raw_market_key"])
            ident = (family, market_key, str(quote.get("period")), str(quote.get("line")))
            # A mesma seleção não pode ser contada duas vezes para a mesma linha.
            if selection in grouped[ident]:
                continue
            grouped[ident][selection] = odd
            families[family]["games"].add(str(match_id))
            families[family]["raw_quotes"] += 1
            seen_prices += 1
            usable = True
        if usable:
            quoted_games += 1
        for (family, key, period, line), selections in grouped.items():
            if set(selections) != EXPECTED[family]:
                incomplete += 1
                families[family]["incomplete_lines"] += 1
                continue
            margin = sum(1/v for v in selections.values())-1
            # Margens negativas podem indicar dados inconsistentes ou stale:
            # preservar para diagnóstico, sem anunciar arbitragem/greens.
            complete += 1
            families[family]["complete_lines"] += 1
            families[family]["overround_samples"].append(margin*100)
            if len(example) < 5 and family in ("match_odds","total_goals","asian_handicap"):
                example.append({
                    "fixture": str(game.get("home") or "")[:70] + " x " +
                               str(game.get("away") or "")[:70],
                    "market_family": family, "raw_market_key": key, "line": line,
                    "observed_at":document["checked_at"],
                    "selections":selections, "overround_pct":round(margin*100,2)
                })
    out_families = {}
    for family, detail in families.items():
        margins=sorted(detail["overround_samples"])
        n=len(margins)
        out_families[family]={
            "games":len(detail["games"]), "odds":detail["raw_quotes"],
            "complete_lines":detail["complete_lines"],
            "incomplete_lines":detail["incomplete_lines"],
            "median_overround_pct":round((margins[(n-1)//2]+margins[n//2])/2,2) if n else None
        }
    return {
        "schema":1, "checked_at":now.astimezone(timezone.utc).isoformat(),
        "bookmaker_snapshot_at":document["checked_at"], "status":"fresh",
        "matches_catalogued":len(document["matches"]), "matches_with_priced_markets":quoted_games,
        "odds_eligible_for_quality":seen_prices, "invalid_quote_records":invalid,
        "complete_market_lines":complete, "incomplete_market_lines":incomplete,
        "families":dict(sorted(out_families.items())),
        "examples":example,
        "limits":("Sem mercados de cartões/escanteios comprovados, sem volume de bolsa "
                  "negociado em BRL, sem margem positiva garantida e sem execução.")
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--archive",default="market-history")
    args=ap.parse_args()
    folder=Path(args.archive)/"public-no-key"
    file=folder/"pinnacle-latest.json"
    target=folder/"pinnacle-depth.json"
    now=datetime.now(timezone.utc)
    try:
        data=json.loads(file.read_text(encoding="utf-8"))
        summary=summarize(data,now)
        target.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({k:v for k,v in summary.items() if k not in ("families","examples","limits")},
                         ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Falha complementar não deve ocultar dados historicamente arquivados.
        target.write_text(json.dumps({"schema":1,"checked_at":now.isoformat(),"status":"unavailable",
                          "reason":type(exc).__name__},ensure_ascii=False,indent=2)+"\n",
                          encoding="utf-8")
        print("Pinnacle depth audit unavailable: "+type(exc).__name__)


if __name__=="__main__":
    main()
