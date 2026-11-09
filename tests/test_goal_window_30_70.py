import unittest
from datetime import datetime, timezone, timedelta
from goal_window_30_70 import (
    evaluate, features, _eligible, _fit, _estimate, _fresh_candidate,
    _metrics, _baseline,
)

NOW = datetime(2026, 11, 9, 13, 0, tzinfo=timezone.utc)


def alert(key, minute=45, outcome="gol_confirmado", match=None, day=0,
          score="0-0", pressure=70, rule="pressao_forte_10min"):
    return {
        "id": key, "match_id": match or key, "minute": minute,
        "captured_at": (NOW-timedelta(days=day,minutes=2)).isoformat(),
        "home": "Casa", "away": "Fora", "league": "Liga A",
        "icon": "🔥", "rule": rule, "basis": "pressure_window",
        "score_at_alert": score, "pressure10": {"score": pressure, "level": "FORTE"},
        "shots_on": 5, "big_chances": 2,
        "outcomes": {"5": "pendente", "10": "pendente", "15": outcome},
    }


class Goal3070Tests(unittest.TestCase):
    def test_in_window_first_match_and_unknowns_not_converted_to_losses(self):
        items = [alert("too_early", 29), alert("too_late", 71),
                 alert("a", 30, "indeterminado", match="same"),
                 alert("b", 36, "gol_confirmado", match="same"),
                 alert("c", 70, "sem_gol_confirmado"),
                 alert("d", 55, "janela_incompleta")]
        x = evaluate({"items": items}, now=NOW)
        self.assertEqual(x["sample"]["first_alert_per_match"], 3)
        self.assertEqual(x["sample"]["settled"], 1)
        self.assertEqual(x["sample"]["unknown_or_pending"], 2)
        self.assertEqual(x["validation"]["status"], "insufficient_history")
        self.assertEqual(x["live"], [])

    def test_time_sorted_train_and_holdout_no_future_leak(self):
        items = []
        for j in range(250):
            day = 50 - j // 5
            items.append(alert("match-"+str(j), 30+j%40,
                               outcome="gol_confirmado" if j%3==0 else "sem_gol_confirmado",
                               day=day))
        base = evaluate({"items": items}, now=NOW)
        self.assertGreaterEqual(base["sample"]["train"], 100)
        self.assertGreaterEqual(base["sample"]["holdout"], 40)
        self.assertEqual(base["sample"]["train"] + base["sample"]["holdout"], 250)
        self.assertTrue(base["validation"]["no_model_promotion"])
        self.assertTrue(base["validation"]["no_forward_prospective_validation"])
        # Test results cannot influence fit on the earlier days.
        cut = base["sample"]["holdout_start_date"]
        initial = _eligible({"items": items}, NOW)
        train = [r for r in initial if r["day"] < cut]
        trained = _fit(train)
        later = []
        for row in items:
            cp = dict(row)
            if cp["captured_at"][:10] >= cut:
                cp["outcomes"] = {"15": "gol_confirmado"}
            later.append(cp)
        second = _eligible({"items": later}, NOW)
        retrained = _fit([r for r in second if r["day"] < cut])
        self.assertEqual(trained, retrained)

    def test_invalid_real_time_data_never_produces_live_forecast(self):
        x = alert("ok", 45)
        game = {"id": "ok", "minute": 46, "phase": "live",
                "score": "0-0", "pressure_last_minute": 46,
                "home": "Casa", "away": "Fora"}
        self.assertTrue(_fresh_candidate(game, x, NOW))
        self.assertFalse(_fresh_candidate({**game, "minute": 71}, x, NOW))
        self.assertFalse(_fresh_candidate({**game, "score": "1-0"}, x, NOW))
        self.assertFalse(_fresh_candidate({**game, "pressure_last_minute": 42}, x, NOW))
        self.assertFalse(_fresh_candidate({**game, "phase": "finished"}, x, NOW))
        stale = {**x, "captured_at": (NOW-timedelta(minutes=24)).isoformat()}
        self.assertFalse(_fresh_candidate(game, stale, NOW))
        conflict = {**x, "outcome_conflict": True}
        self.assertFalse(_fresh_candidate(game, conflict, NOW))
        scored = {**x, "outcomes": {"5": "gol_confirmado"}}
        self.assertFalse(_fresh_candidate(game, scored, NOW))

    def test_features_absence_and_valid_metrics(self):
        e = {"minute": 58, "rule": "chutes_no_alvo_5", "context": {
            "pressure10_score": None, "shots_on": 5, "big_chances": 1}}
        f = features(e)
        self.assertEqual(f["pressao"], "indisponivel")
        self.assertEqual(f["finalizacoes_alvo"], "5+")
        self.assertEqual(f["minuto"], "50-59")
        rows = list(_eligible({"items":[alert(str(i),day=i, outcome=(
            "gol_confirmado" if i%2 else "sem_gol_confirmado")) for i in range(25)]}, NOW))
        model = _fit(rows)
        p, weights = _estimate(model,rows[0])
        self.assertGreater(p,0)
        self.assertLess(p,1)
        m,_ = _metrics(rows,model)
        self.assertGreater(m["brier"],0)
        self.assertGreaterEqual(m["ece"],0)
        self.assertEqual(len(m["bins"]),5)
        self.assertIsNotNone(_baseline(rows,model["base_rate"]))


if __name__=="__main__":
    unittest.main()
