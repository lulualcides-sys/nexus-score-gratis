#!/usr/bin/env python3
"""NEXUS: league-by-league descriptive FT/HT statistics from verified finished scores.

Descriptive frequencies are NOT bookmaker odds, forecasts, ROI, or executable bets.
Never counts a missing halftime score as 0-0 and never trains on ongoing fixtures.
"""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import json

from telegram_collector.model_only import historical_rows

RECENT_LIMIT = 20


def _rates(rows):
    n = len(rows)
    if not n:
        return None
    home = sum(r["ft"][0] > r["ft"][1] for r in rows)
    draws = sum(r["ft"][0] == r["ft"][1] for r in rows)
    away = n - home - draws
    ht = [r for r in rows if r.get("ht") is not None]
    nh = len(ht)
    goals = sum(sum(r["ft"]) for r in rows)
    def pct(count, count_total=n):
        return round(100 * count / count_total, 2) if count_total else None
    return {
        "matches": n,
        "ft_1x2": {"home": home, "draw": draws, "away": away,
                   "home_pct": pct(home), "draw_pct": pct(draws), "away_pct": pct(away)},
        "goals_ft": {
            "average_total": round(goals / n, 3),
            "average_home": round(sum(r["ft"][0] for r in rows) / n, 3),
            "average_away": round(sum(r["ft"][1] for r in rows) / n, 3),
            "over_0_5_pct": pct(sum(sum(r["ft"]) >= 1 for r in rows)),
            "over_1_5_pct": pct(sum(sum(r["ft"]) >= 2 for r in rows)),
            "over_2_5_pct": pct(sum(sum(r["ft"]) >= 3 for r in rows)),
            "over_3_5_pct": pct(sum(sum(r["ft"]) >= 4 for r in rows)),
        },
        "btts_ft": {"yes": sum(all(r["ft"]) for r in rows),
                    "yes_pct": pct(sum(all(r["ft"]) for r in rows))},
        "ht": {
            "available_matches": nh,
            "coverage_pct": pct(nh),
            "over_0_5_pct": pct(sum(sum(r["ht"]) >= 1 for r in ht), nh),
            "over_1_5_pct": pct(sum(sum(r["ht"]) >= 2 for r in ht), nh),
            "btts_yes_pct": pct(sum(all(r["ht"]) for r in ht), nh),
            "home_pct": pct(sum(r["ht"][0] > r["ht"][1] for r in ht), nh),
            "draw_pct": pct(sum(r["ht"][0] == r["ht"][1] for r in ht), nh),
            "away_pct": pct(sum(r["ht"][0] < r["ht"][1] for r in ht), nh),
        },
    }


def summarize(rows, as_of):
    if as_of.tzinfo is None:
        raise ValueError("as_of needs an explicit timezone")
    by_league = defaultdict(list)
    seen = set()
    for r in rows:
        if not r["date"] < as_of.date():
            continue
        unique = (r["league"], r["home"], r["away"], r["date"])
        if unique in seen:
            continue
        seen.add(unique)
        if r.get("ht") is not None:
            h, a = r["ht"]
            fh, fa = r["ft"]
            if h < 0 or a < 0 or h > fh or a > fa:
                raise ValueError("Unreliable half-time score")
        by_league[r["league"]].append(r)
    league_results = []
    for league, entries in by_league.items():
        ordered = sorted(entries, key=lambda r: (r["date"], r["home"], r["away"]))
        stats = _rates(ordered)
        recent = _rates(ordered[-RECENT_LIMIT:]) if len(ordered) >= 10 else None
        league_results.append({
            "league": league, "first_match_date": ordered[0]["date"].isoformat(),
            "last_match_date": ordered[-1]["date"].isoformat(),
            "all": stats, "recent": recent,
            "recent_note": ("Últimos até 20 jogos encerrados; janela curta, não previsão."
                            if recent else "Menos de 10 jogos: tendência indisponível."),
        })
    league_results.sort(key=lambda x: (-x["all"]["matches"], x["league"]))
    total = [r for entries in by_league.values() for r in entries]
    return {
        "schema": 1,
        "generated_at": as_of.isoformat(),
        "source": "Finished NEXUS / CC0 historical scores, deduplicated by league/teams/day",
        "status": "descriptive_only",
        "leagues": league_results,
        "league_count": len(league_results),
        "unique_finished_matches": len(total),
        "half_time_available": sum(r.get("ht") is not None for r in total),
        "overall": _rates(total),
        "limitations": [
            "Amostra contém somente partidas com placar final verificável e código de liga.",
            "Percentuais observados não são probabilidades calibradas, odds executáveis nem lucro.",
            "HT ausente fica indisponível e não é preenchido com 0-0.",
            "Exclui jogos do próprio dia para evitar contaminação com partidas ainda em andamento.",
            "Amostra é enviesada pela cobertura das fontes e pode não representar todas as ligas.",
        ],
    }


def run(history, archive, now):
    result = summarize(historical_rows(history, now), now)
    folder = Path(archive) / "model-only"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "league-stats-latest.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in
                      ("league_count", "unique_finished_matches", "half_time_available")},
                     ensure_ascii=False))
    return result


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--history-dir", default="history")
    p.add_argument("--archive", default="market-history")
    args = p.parse_args()
    run(args.history_dir, args.archive, datetime.now(timezone.utc))


if __name__ == "__main__":
    main()
