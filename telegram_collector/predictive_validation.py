#!/usr/bin/env python3
"""Independent, leakage-safe benchmark and SHADOW challenger for the NEXUS model.

A fixed 20% league-prior blend is evaluated only; it MUST NOT silently replace
the coherent production HT/FT Poisson distribution. No bets/odds/ROI claims.
"""
from collections import Counter
import math

SHADOW_PRIOR_WEIGHT = 0.20
PRIOR_PSEUDO_1X2 = 2.0
PRIOR_PSEUDO_BINARY = 2.0
MIN_PRIOR_MATCHES = 20


def league_prior(rows, league, cutoff):
    """Only earlier fixture DATES; same-day matches cannot leak results."""
    past = [r for r in rows if r["league"] == league and r["date"] < cutoff]
    n = len(past)
    if n < MIN_PRIOR_MATCHES:
        return None
    h = sum(r["ft"][0] > r["ft"][1] for r in past)
    d = sum(r["ft"][0] == r["ft"][1] for r in past)
    a = n - h - d
    yes_over = sum(sum(r["ft"]) >= 3 for r in past)
    yes_btts = sum(all(r["ft"]) for r in past)
    p3 = PRIOR_PSEUDO_1X2
    p2 = PRIOR_PSEUDO_BINARY
    return {
        "ft": {"1": (h + p3) / (n + 3 * p3),
               "X": (d + p3) / (n + 3 * p3),
               "2": (a + p3) / (n + 3 * p3)},
        "over_2_5": (yes_over + p2) / (n + 2 * p2),
        "btts": (yes_btts + p2) / (n + 2 * p2),
        "training_games": n,
    }


def from_poisson(book):
    return {
        "ft": {k: float(book["ft_1x2"][k]["probability"]) for k in ("1", "X", "2")},
        "over_2_5": float(book["ft_total_goals"]["2.5"]["Over"]["probability"]),
        "btts": float(book["btts_ft"]["Sim"]["probability"]),
    }


def shadow(model, baseline, weight=SHADOW_PRIOR_WEIGHT):
    if not 0 <= weight <= 1:
        raise ValueError("Invalid blend weight")
    return {
        "ft": {k: (1 - weight) * model["ft"][k] + weight * baseline["ft"][k]
               for k in ("1", "X", "2")},
        "over_2_5": (1 - weight) * model["over_2_5"] + weight * baseline["over_2_5"],
        "btts": (1 - weight) * model["btts"] + weight * baseline["btts"],
    }


def score(probs, ft_score):
    h, a = ft_score
    label = "1" if h > a else ("X" if h == a else "2")
    p = probs["ft"]
    if any(not math.isfinite(float(x)) or x <= 0 or x >= 1
           for x in (*p.values(), probs["over_2_5"], probs["btts"])):
        raise ValueError("Nonfinite or invalid model probability")
    if abs(sum(p.values()) - 1) > 1e-5:
        raise ValueError("1X2 must sum to 1")
    true = {k: int(label == k) for k in ("1", "X", "2")}
    over = int(h + a >= 3)
    btts = int(h > 0 and a > 0)
    return {
        "brier_1x2": sum((p[k] - true[k]) ** 2 for k in ("1", "X", "2")),
        "rps_1x2": ((p["1"] - true["1"]) ** 2 +
                     (p["1"] + p["X"] - true["1"] - true["X"]) ** 2) / 2,
        "log_loss_1x2": -math.log(p[label]),
        "brier_over_2_5": (probs["over_2_5"] - over) ** 2,
        "brier_btts": (probs["btts"] - btts) ** 2,
    }


def reliability(items, field):
    """Five fixed bins for binary probability calibration (diagnostic only)."""
    bins = [{"n": 0, "pred_sum": 0.0, "actual_sum": 0.0} for _ in range(5)]
    for probs, actual_ft in items:
        h, a = actual_ft
        observed = int(h + a >= 3) if field == "over_2_5" else int(h > 0 and a > 0)
        p = probs[field]
        i = min(4, max(0, int(p * 5)))
        bins[i]["n"] += 1
        bins[i]["pred_sum"] += p
        bins[i]["actual_sum"] += observed
    n = len(items)
    ece = sum(abs(b["pred_sum"] - b["actual_sum"]) for b in bins) / n if n else None
    return {
        "n": n,
        "ece": round(ece, 5) if ece is not None else None,
        "bins": [
            {"range_pct": [i * 20, (i + 1) * 20], "n": b["n"],
             "predicted_pct": round(100 * b["pred_sum"] / b["n"], 2) if b["n"] else None,
             "observed_pct": round(100 * b["actual_sum"] / b["n"], 2) if b["n"] else None}
            for i, b in enumerate(bins)
        ],
    }


def report(paired):
    """Paired predictions: (league, score, production_probs, historical_prior)."""
    cases = {"poisson_original": [], "league_frequency_baseline": [],
             "league_blend_20pct_shadow": []}
    calibration = {name: [] for name in cases}
    leagues = Counter()
    for league, ft_score, poisson, prior in paired:
        if prior is None:
            continue
        challenger = shadow(poisson, prior)
        for name, probabilities in (("poisson_original", poisson),
                                    ("league_frequency_baseline", prior),
                                    ("league_blend_20pct_shadow", challenger)):
            cases[name].append(score(probabilities, ft_score))
            calibration[name].append((probabilities, ft_score))
        leagues[league] += 1
    fields = ("brier_1x2", "rps_1x2", "log_loss_1x2", "brier_over_2_5", "brier_btts")
    metrics = {
        name: {
            "n": len(values),
            **{key: round(sum(v[key] for v in values) / len(values), 5)
               if values else None for key in fields},
            "calibration_over_2_5": reliability(calibration[name], "over_2_5"),
            "calibration_btts": reliability(calibration[name], "btts"),
        }
        for name, values in cases.items()
    }
    original, contender = metrics["poisson_original"], metrics["league_blend_20pct_shadow"]
    improvement = (round(original["brier_1x2"] - contender["brier_1x2"], 5)
                   if original["n"] else None)
    return {
        "status": "diagnostic_shadow_only" if original["n"] >= 40 else "insufficient_paired_sample",
        "paired_matches": original["n"],
        "leagues": dict(sorted(leagues.items())),
        "candidate": "static 80% Poisson + 20% pre-match historical league frequencies",
        "weight_fixed_a_priori": True,
        "leakage_guard": "Every prior uses games strictly before fixture date; one paired holdout for all models",
        "score_direction": "lower_is_better",
        "metrics": metrics,
        "shadow_brier_1x2_improvement": improvement,
        "production_model_unchanged": True,
        "promotion_allowed": False,
        "explanation": (
            "Comparação retrospectiva em mesma amostra não comprova superioridade fora da amostra. "
            "O challenger é apenas diagnóstico; não gera odds publicadas nem sinais de aposta. "
            "Não existe baseline bookmaker comparável com cotações pré-jogo suficientes e pareadas."
        ),
    }
