"""Motivo da ausência na escalação: só o que o FotMob publica em
lineup.<time>.unavailable (lesão, suspensão, seleção...). Sem motivo na fonte,
fica 'não informado' — nunca inventado."""
import unittest
from coletar import fotmob_lineups, unavailable_reason
from lineup_changes import build


def packet(unavailable):
    return {"content": {"lineup": {"lineupType": "standard", "homeTeam": {
        "starters": [{"id": i, "name": f"J{i}"} for i in range(1, 12)],
        "unavailable": unavailable}, "awayTeam": {}}}}


class LineupReasonTests(unittest.TestCase):
    def test_reasons_parsed(self):
        out = fotmob_lineups(packet([
            {"id": 9, "name": "J9", "unavailability": {"type": "injury", "expectedReturn": "Early December 2026"}},
            {"id": 10, "name": "J10", "unavailability": {"type": "suspension"}},
            {"id": 12, "name": "J12", "unavailability": {"type": "weird_new_type"}},
            {"id": 13, "name": "J13"}]))
        miss = {p["id"]: p for p in out["home"]["unavailable"]}
        self.assertEqual(miss["9"]["reason"], "Lesão")
        self.assertEqual(miss["9"]["expected_return"], "Early December 2026")
        self.assertEqual(miss["10"]["reason"], "Suspenso")
        self.assertEqual(miss["12"]["reason"], "Motivo não informado")
        self.assertEqual(miss["13"]["reason"], "Motivo não informado")

    def test_reason_labels(self):
        self.assertEqual(unavailable_reason({"type": "red_card"}), "Suspenso")
        self.assertEqual(unavailable_reason({"type": "international_duty"}), "Convocado pela seleção")
        self.assertEqual(unavailable_reason(None), "Motivo não informado")

    def test_report_attaches_reason_to_missing_habitual(self):
        def xi(ids):
            return {"status": "confirmed", "starters": [{"id": str(i), "name": f"J{i}"} for i in ids]}
        rows = {}
        for n, ts in enumerate((50, 100, 200, 300)):
            rows[f"g{n}"] = {"fixture": {"start_timestamp": ts, "home_id": "7", "away_id": "8", "home": "T"},
                             "lineups": {"home": xi(range(1, 12))}}
        cur = xi([1, 2, 3, 4, 5, 6, 7, 8, 30, 31, 32])
        cur["unavailable"] = [{"id": "9", "name": "J9", "reason": "Lesão", "expected_return": "Dezembro"}]
        rows["now"] = {"fixture": {"start_timestamp": 400, "home_id": "7", "away_id": "8", "home": "T"},
                       "lineups": {"home": cur}}
        home = build({"d": {"matches": rows}})["now"]["home"]
        by = {m["name"]: m for m in home["missing_detail"]}
        self.assertEqual(by["J9"]["reason"], "Lesão")
        self.assertEqual(by["J9"]["expected_return"], "Dezembro")
        self.assertIsNone(by["J10"]["reason"], "sem dado da fonte: sem motivo")


if __name__ == "__main__":
    unittest.main()
