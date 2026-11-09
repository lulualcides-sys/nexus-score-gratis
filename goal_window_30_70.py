#!/usr/bin/env python3
"""Pesquisa observacional de gol 30–70' usando alertas existentes do NEXUS.

Alvo: gol nos 15 minutos seguintes a um alerta ocorrido entre 30' e 70'.
Uma observação por partida, apenas resultado 15' confirmado, sem antecipação
de desfechos. Probabilidade experimental NUNCA significa EV/odd/aposta.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import math

from signal_evaluation import _entries, HIT, MISS

MINUTE_START = 30
MINUTE_END = 70
HORIZON = "15"
MAX_AGE_DAYS = 90
MIN_TRAIN = 100
MIN_TEST = 40
PRIOR_STRENGTH = 28
FEATURE_WEIGHT = 0.45
MIN_FEATURE_N = 20


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        v = float(value)
        return v if math.isfinite(v) and 0 <= v <= 10000 else None
    except (TypeError, ValueError, OverflowError):
        return None


def features(entry):
    minute = int(entry["minute"])
    context = entry.get("context") or {}
    pressure = _number(context.get("pressure10_score"))
    shots = _number(context.get("shots_on"))
    chances = _number(context.get("big_chances"))
    rule = str(entry.get("rule") or entry.get("signal") or "")
    known_rules = ("pressao_forte_10min", "pressao_total_5_10min",
                   "pressao_ofensiva_18", "chutes_no_alvo_5",
                   "escanteios_6", "grandes_chances_3",
                   "alerta_cruzado_gol")
    known = next((x for x in known_rules if x in rule), "outro")
    return {
        "minuto": ("30-39" if minute <= 39 else "40-49" if minute <= 49
                   else "50-59" if minute <= 59 else "60-70"),
        "pressao": ("indisponivel" if pressure is None else
                    "alta" if pressure >= 70 else "moderada" if pressure >= 45 else "baixa"),
        "finalizacoes_alvo": ("indisponivel" if shots is None else
                             "5+" if shots >= 5 else "2-4" if shots >= 2 else "0-1"),
        "chances_claras": ("indisponivel" if chances is None else
                          "2+" if chances >= 2 else "1" if chances >= 1 else "0"),
        "regra": known,
    }


def _safe_logit(p):
    p = max(.001, min(.999, p))
    return math.log(p / (1 - p))


def _logistic(x):
    return 1 / (1 + math.exp(-max(-18, min(18, x))))


def _date(stamp):
    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))


def _eligible(journal, as_of):
    """Deduplicate BEFORE filtering outcomes; never choose an easier known label."""
    if as_of.tzinfo is None:
        raise ValueError("Expected timezone-aware timestamp")
    cutoff = (as_of.date() - timedelta(days=MAX_AGE_DAYS-1)).isoformat()
    candidates = [r for r in _entries(journal) if MINUTE_START <= r["minute"] <= MINUTE_END
                  and cutoff <= r["day"] <= as_of.date().isoformat()]
    earliest = {}
    for r in sorted(candidates, key=lambda x: (x["day"], x["minute"], x["signal"])):
        earliest.setdefault(r["match_id"], r)
    return sorted(earliest.values(), key=lambda x:(x["day"], x["minute"], x["match_id"]))


def _fit(rows):
    successes = sum(r["outcomes"][HORIZON] == HIT for r in rows)
    n = len(rows)
    prior = (successes + 3) / (n + 6)
    groups = defaultdict(lambda: [0, 0])
    for r in rows:
        for field, key in features(r).items():
            g = groups[field+"|"+key]
            g[0] += 1
            g[1] += int(r["outcomes"][HORIZON] == HIT)
    return {"base_rate": prior, "trained": n, "hits": successes,
            "groups": {name: {"n": counts[0], "hits": counts[1]}
                       for name, counts in groups.items()}}


def _estimate(model, r):
    p = model["base_rate"]
    x = _safe_logit(p)
    effective = []
    for key, value in features(r).items():
        g = model["groups"].get(key+"|"+value)
        if not g or g["n"] < MIN_FEATURE_N:
            continue
        smoothed = (g["hits"] + PRIOR_STRENGTH*p) / (g["n"]+PRIOR_STRENGTH)
        delta = _safe_logit(smoothed)-_safe_logit(p)
        delta = max(-.40, min(.40, delta)) * FEATURE_WEIGHT
        x += delta
        effective.append({"field": key, "category": value, "training_matches": g["n"]})
    return _logistic(x), effective


def _metrics(rows, model):
    if not rows:
        return None, []
    predictions = []
    losses = []
    bins = [{"n": 0, "sum_p": 0., "hits": 0} for _ in range(5)]
    for r in rows:
        p, _ = _estimate(model, r)
        y = int(r["outcomes"][HORIZON] == HIT)
        predictions.append((p, y))
        losses.append((p-y)**2)
        bucket = bins[min(4, int(p*5))]
        bucket["n"] += 1
        bucket["sum_p"] += p
        bucket["hits"] += y
    return {"n": len(rows),
            "hits": sum(y for p,y in predictions),
            "brier": round(sum(losses)/len(losses), 5),
            "log_loss": round(-sum(y*math.log(max(.001,p)) +
                 (1-y)*math.log(max(.001,1-p)) for p,y in predictions)/len(rows), 5),
            "ece": round(sum(abs(b["sum_p"]-b["hits"]) for b in bins)/len(rows), 5),
            "bins": [{"from": i*20, "to": (i+1)*20, "n": b["n"],
                       "pred_pct": round(100*b["sum_p"]/b["n"], 1) if b["n"] else None,
                       "observed_pct": round(100*b["hits"]/b["n"], 1) if b["n"] else None}
                      for i,b in enumerate(bins)]
            }, predictions


def _baseline(rows, p):
    if not rows: return None
    return round(sum((p-int(r["outcomes"][HORIZON] == HIT))**2 for r in rows)/len(rows), 5)


def _fresh_candidate(game, raw, now):
    """No stale, already-scored or late-data alerts can generate a live forecast."""
    if game.get("phase") != "live":
        return False
    minute = game.get("minute")
    try:
        minute = int(minute)
        at = int(raw["minute"])
        timestamp = _date(raw["captured_at"])
    except (ValueError, TypeError, OverflowError, KeyError):
        return False
    if not (MINUTE_START <= minute <= MINUTE_END
            and MINUTE_START <= at <= MINUTE_END
            and 0 <= minute-at <= 3 and timestamp.tzinfo is not None
            and 0 <= (now-timestamp).total_seconds() <= 20*60):
        return False
    if str(game.get("score") or "") != str(raw.get("score_at_alert") or ""):
        return False
    if raw.get("outcome_conflict") or any(
            raw.get("outcomes",{}).get(str(h)) == HIT for h in (5,10,15)):
        return False
    # Graph-based observations require current, actually observed momentum.
    if raw.get("basis") == "pressure_window":
        try: last = int(game["pressure_last_minute"])
        except (KeyError, TypeError, ValueError): return False
        if last < minute-2: return False
    return True


def _live(model, journal, games, now, allow_percentage):
    catalog = {}
    for item in (journal.get("items") or []):
        if not isinstance(item, dict) or not item.get("match_id"): continue
        catalog.setdefault(str(item["match_id"]), []).append(item)
    active = []
    for game in games:
        match_id = str(game.get("id") or "")
        if not match_id: continue
        recent = [r for r in catalog.get(match_id, [])
                  if _fresh_candidate(game, r, now)]
        if not recent: continue
        chosen = max(recent, key=lambda r: (int(r["minute"]), str(r["captured_at"])))
        ctx = {"pressure10_score": ((chosen.get("pressure10") or {}).get("score")),
               "shots_on": chosen.get("shots_on"),
               "big_chances": chosen.get("big_chances")}
        entry = {"minute": int(chosen["minute"]), "rule": chosen.get("rule"),
                 "context": ctx}
        p, evidence = _estimate(model, entry)
        active.append({
            "match_id": match_id[:100], "home": str(game.get("home") or "")[:95],
            "away": str(game.get("away") or "")[:95], "minute": int(game["minute"]),
            "rule": str(chosen.get("rule") or "")[:50],
            "observed_at": str(chosen.get("captured_at") or "")[:45],
            "experimental_pct": round(p*100, 1) if allow_percentage else None,
            "signal_type": "estimated_observational_not_calibrated" if allow_percentage
                           else "sample_insufficient",
            "factors": evidence[:5],
        })
    return sorted(active, key=lambda x:x["minute"])[:40]


def evaluate(journal, games=(), now=None):
    now = now or datetime.now(timezone.utc)
    earliest = _eligible(journal, now)
    settled = [r for r in earliest if r["outcomes"][HORIZON] in (HIT,MISS)]
    days = sorted({r["day"] for r in settled})
    split = days[max(1, int(.7*len(days)))] if len(days) >= 6 else None
    train = [r for r in settled if split is not None and r["day"] < split]
    test = [r for r in settled if split is not None and r["day"] >= split]
    trained = _fit(train)
    test_metrics, _ = _metrics(test, trained) if train else (None, [])
    baseline_brier = _baseline(test, trained["base_rate"]) if train else None
    status = "insufficient_history"
    if (len(train) >= MIN_TRAIN and len(test) >= MIN_TEST
            and test_metrics and 5 <= test_metrics["hits"] <= len(test)-5):
        if (test_metrics["brier"] <= baseline_brier-.002
                and test_metrics["ece"] <= .10):
            status = "better_than_constant_baseline_in_historical_holdout"
        else:
            status = "no_verified_improvement_over_baseline"
    # Forecast remains flagged experimental even after apparent historical gains.
    # Do not publish a numerical estimate if the holdout fails the baseline.
    # An actual current alert can still be shown without a fabricated percentage.
    enough = (status == "better_than_constant_baseline_in_historical_holdout"
              and len(earliest) > 0 and len(settled)/len(earliest) >= .4)
    active = _live(trained, journal, games, now, allow_percentage=enough)
    return {"schema": 1, "name": "NEXUS Gol 30–70",
        "generated_at": now.isoformat(), "minute_range": [30,70],
        "goal_horizon_minutes": 15,
        "goal_window_description": "Alerta entre 30' e 70'; gol nos próximos 15 minutos, inclusive após 70'.",
        "target": "goal_in_next_15_minutes_after_first_eligible_match_alert",
        "sample": {"first_alert_per_match": len(earliest), "settled": len(settled),
                   "unknown_or_pending": len(earliest)-len(settled),
                   "train": len(train), "holdout": len(test),
                   "train_days": len({r["day"] for r in train}),
                   "holdout_days": len({r["day"] for r in test}),
                   "holdout_start_date": split,
                   "train_hits": trained["hits"] if train else 0},
        "validation": {"status": status, "min_train": MIN_TRAIN, "min_holdout": MIN_TEST,
                       "brier_model": test_metrics["brier"] if test_metrics else None,
                       "brier_constant_baseline": baseline_brier,
                       "ece_holdout": test_metrics["ece"] if test_metrics else None,
                       "reliability_bins": test_metrics["bins"] if test_metrics else [],
                       "no_forward_prospective_validation": True,
                       "no_model_promotion": True,
                       "probability_released_for_live": enough},
        "live": active,
        "active_count": len(active),
        "notes": [
            "Uma observação inicial por partida; duplicidades não contam como novos acertos.",
            "Treino e teste separados cronologicamente por dia de observação.",
            "Resultados indeterminados, pendentes e janelas incompletas não são tratados como derrotas.",
            "As amostras vêm de partidas que geraram alertas, não de todos os jogos de futebol.",
            "A previsão de 15 min iniciada aos 70' alcança o minuto 85.",
            "Não há odds, liquidez, ROI, EV comprovado ou promessa de acerto."
        ]}
