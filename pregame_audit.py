#!/usr/bin/env python3
"""NEXUS: congelamento pré-jogo auditável e verificação posterior, sem odds falsas.

Uma previsão só nasce ANTES do início, com resultados anteriores observados.
Uma vez congelada, nunca é recalculada usando o placar ou forma pós-jogo.
P/L real e registros financeiros privados não são acessados neste módulo.
"""
import math
import re
from datetime import datetime, timezone

MODEL = "NEXUS prelive Poisson v1 - experimental, sem calibracao"


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def sample(row, kickoff):
    if not isinstance(row, dict):
        return None
    games = row.get("games") or []
    valid = []
    for game in games:
        if not isinstance(game, dict):
            continue
        timestamp = number(game.get("ts"))
        gf = number(game.get("gf"))
        ga = number(game.get("ga"))
        if (timestamp is None or gf is None or ga is None or
                timestamp >= kickoff or timestamp <= 0 or gf < 0 or ga < 0 or
                gf > 20 or ga > 20):
            continue
        valid.append((timestamp, gf, ga))
    valid.sort(reverse=True)
    valid = valid[:10]
    if len(valid) < 5:
        return None
    return {"n": len(valid),
            "gf": round(sum(v[1] for v in valid) / len(valid), 3),
            "ga": round(sum(v[2] for v in valid) / len(valid), 3),
            "oldest_match_at": datetime.fromtimestamp(valid[-1][0], timezone.utc).isoformat(),
            "newest_match_at": datetime.fromtimestamp(valid[0][0], timezone.utc).isoformat()}


def prediction(row, kickoff):
    form = row.get("team_form") or {}
    home = sample(form.get("home"), kickoff)
    away = sample(form.get("away"), kickoff)
    if not home or not away:
        return None
    n_h, n_a = home["n"], away["n"]
    hf, ha, af, aa = home["gf"], home["ga"], away["gf"], away["ga"]
    weighted_hf = (hf * n_h + 1.25 * 3) / (n_h + 3)
    weighted_aa = (aa * n_a + 1.25 * 3) / (n_a + 3)
    weighted_af = (af * n_a + 1.25 * 3) / (n_a + 3)
    weighted_ha = (ha * n_h + 1.25 * 3) / (n_h + 3)
    lam_h = min(3.8, max(0.25, math.sqrt(weighted_hf * weighted_aa) * 1.10))
    lam_a = min(3.8, max(0.25, math.sqrt(weighted_af * weighted_ha) * 0.94))
    def poisson(k, lam):
        return math.exp(-lam) * lam ** k / math.factorial(k)
    grid = [(i, j, poisson(i, lam_h) * poisson(j, lam_a))
            for i in range(14) for j in range(14)]
    total = sum(v[2] for v in grid)
    grid = [(i, j, p / total) for i, j, p in grid]
    def pct(test):
        return round(sum(p for i, j, p in grid if test(i, j)) * 100, 2)
    prob = {"home": pct(lambda i, j: i > j),
            "draw": pct(lambda i, j: i == j),
            "away": pct(lambda i, j: i < j)}
    top = sorted(grid, key=lambda v: v[2], reverse=True)[:3]
    return {
        "sample": {"home": home, "away": away},
        "forecast": {
            "one_x_two": prob,
            "over_2_5_pct": pct(lambda i, j: i + j >= 3),
            "btts_yes_pct": pct(lambda i, j: i > 0 and j > 0),
            "expected_goals": {"home": round(lam_h, 2), "away": round(lam_a, 2)},
            "top_scores": [{"score": f"{i}-{j}", "probability": round(p * 100, 2)}
                           for i, j, p in top]
        }
    }


def indications(forecast):
    p = forecast["one_x_two"]
    outcomes = sorted(p, key=lambda x: p[x], reverse=True)
    double = {"1X": p["home"] + p["draw"], "X2": p["draw"] + p["away"],
              "12": p["home"] + p["away"]}
    doubled = max(double, key=double.get)
    over = forecast["over_2_5_pct"]
    btts = forecast["btts_yes_pct"]
    return [
        {"market": "1x2", "selection": outcomes[0], "probability": p[outcomes[0]]},
        {"market": "double_chance", "selection": doubled,
         "probability": round(double[doubled], 2)},
        {"market": "over_under_25", "selection": "over" if over >= 50 else "under",
         "probability": round(max(over, 100 - over), 2)},
        {"market": "btts", "selection": "yes" if btts >= 50 else "no",
         "probability": round(max(btts, 100 - btts), 2)}
    ]


def odds_snapshot(row, now, kickoff):
    """Só 1X2 simultâneo, mesma casa e fonte, antes da partida e da consulta."""
    packets = {}
    for q in row.get("odds_quotes") or []:
        if not isinstance(q, dict) or q.get("market") != "1x2":
            continue
        try:
            at = datetime.fromisoformat(str(q["captured_at"]).replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError, KeyError):
            continue
        val = number(q.get("odds"))
        if (at > now or at >= kickoff or at <= 0 or val is None or
                not 1.01 < val < 1000 or q.get("selection") not in
                ("home", "draw", "away")):
            continue
        source, bookmaker = str(q.get("source") or ""), str(q.get("bookmaker") or "")
        if not source or not bookmaker:
            continue
        key = (source, bookmaker, at)
        packets.setdefault(key, {})[q["selection"]] = round(val, 4)
    candidates = [(key, prices) for key, prices in packets.items()
                  if set(prices) == {"home", "draw", "away"}]
    if not candidates:
        return None
    (source, bookmaker, captured), prices = max(candidates, key=lambda x: x[0][2])
    age_minutes = max(0, round((now - captured) / 60))
    return {"source": source[:40], "bookmaker": bookmaker[:55],
            "captured_at": datetime.fromtimestamp(captured, timezone.utc).isoformat(),
            "prices": prices, "age_minutes_at_check": age_minutes,
            "recent_at_check": age_minutes <= 45,
            "scope": "pregame_only"}


def resolve(indication, home, away):
    market, pick = indication["market"], indication["selection"]
    if market == "1x2":
        result = "home" if home > away else "away" if away > home else "draw"
        return result == pick
    if market == "double_chance":
        winner = "1" if home > away else "2" if away > home else "X"
        return winner in pick
    if market == "over_under_25":
        return (home + away > 2) == (pick == "over")
    if market == "btts":
        return (home > 0 and away > 0) == (pick == "yes")
    return None


def update_row(row, now=None):
    """Atualiza SOMENTE campo pregame_baseline de uma partida quando cabível."""
    if now is None:
        now = datetime.now(timezone.utc)
    now_ts = now.timestamp()
    f = row.get("fixture") or {}
    kickoff = number(f.get("start_timestamp"))
    if kickoff is None or kickoff <= 0:
        return False
    baseline = row.get("pregame_baseline")
    if not isinstance(baseline, dict):
        if f.get("phase") != "scheduled" or now_ts >= kickoff:
            return False  # nunca criar previsão retrospectiva
        computed = prediction(row, kickoff)
        if not computed:
            return False
        baseline = {
            "schema": 1, "captured_at": now.isoformat(),
            "kickoff_at": datetime.fromtimestamp(kickoff, timezone.utc).isoformat(),
            "source": "historico esportivo verificado ESPN/FotMob",
            "model": MODEL, "model_status": "experimental_uncalibrated",
            "sample": computed["sample"], "forecast": computed["forecast"],
            "indications": indications(computed["forecast"]),
            "odds": None, "settlement": None
        }
        row["pregame_baseline"] = baseline
        changed = True
    else:
        changed = False

    # Apenas até kickoff: atualizar cotação prévia sem jamais mudar previsão original.
    if f.get("phase") == "scheduled" and now_ts < kickoff:
        current = odds_snapshot(row, now_ts, kickoff)
        if current and (baseline.get("odds") is None or
                        current["captured_at"] > baseline["odds"].get("captured_at", "")):
            baseline["odds"] = current
            changed = True
    # Resultado somente se final validado. Não há stakes ou lucro atribuído.
    if f.get("phase") == "finished" and baseline.get("settlement") is None:
        score = re.fullmatch(r"(\d{1,2})\s*[-–:]\s*(\d{1,2})", str(f.get("score") or ""))
        if score:
            home, away = int(score[1]), int(score[2])
            checks = [{"market": x["market"], "selection": x["selection"],
                       "probability": x["probability"],
                       "result": "hit" if resolve(x, home, away) else "miss"}
                      for x in baseline.get("indications") or []]
            baseline["settlement"] = {
                "score": f"{home}-{away}", "settled_at": now.isoformat(),
                "checks": checks,
                "hits": sum(x["result"] == "hit" for x in checks),
                "count": len(checks), "status": "sports_only_no_bet"
            }
            changed = True
    return changed


def run():
    """Roda nas rotinas GitHub. Preserva qualquer outro campo/dia."""
    from pathlib import Path
    import json
    from odds_capture import read, save, HISTORY
    now = datetime.now(timezone.utc)
    count = settled = 0
    for path in sorted(HISTORY.glob("20??-??-??.json")):
        doc = read(path)
        modified = False
        for row in (doc.get("matches") or {}).values():
            if not isinstance(row, dict):
                continue
            had = isinstance(row.get("pregame_baseline"), dict)
            if update_row(row, now):
                modified = True
                if not had:
                    count += 1
                elif row.get("pregame_baseline", {}).get("settlement"):
                    settled += 1
        if modified:
            save(path, doc)
    print(json.dumps({"frozen_new": count, "settled_new": settled,
                      "status": "experimental_sports_only"}, ensure_ascii=False))


if __name__ == "__main__":
    run()
