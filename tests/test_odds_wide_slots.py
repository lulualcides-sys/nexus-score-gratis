"""Regressão: GitHub Free roda o cron de 5 min só a cada 3-9 h. Com registro de
cota, cada fonte consulta na PRIMEIRA execução de cada bloco (não só nos 5
primeiros minutos de horários exatos) e nunca duas vezes no mesmo bloco."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import the_odds_api_source as toa
import api_football_odds as apf
import oddspapi_odds as opa
from odds_slots import block_slot


def ts(h, m, day=18):
    return int(datetime(2026, 11, day, h, m, tzinfo=timezone.utc).timestamp())


def docs_with(kick):
    row = {"fixture": {"home": "Lexington SC", "away": "FC Tulsa", "phase": "scheduled",
                       "start_timestamp": kick, "league": "USL Championship"}}
    return {"2026-11-18": {"matches": {"fotmob-1": row}}}, [("2026-11-18", "fotmob-1", 3600)]


class BlockSlotTests(unittest.TestCase):
    def test_block_ids(self):
        t = datetime(2026, 11, 18, 7, 14, tzinfo=timezone.utc)
        self.assertEqual(block_slot(t, 12), "2026-11-18T00")
        self.assertEqual(block_slot(t, 3), "2026-11-18T06")
        self.assertRaises(ValueError, block_slot, t, 5)


class TheOddsApiWideSlot(unittest.TestCase):
    def test_off_minute_run_uses_block_once(self):
        now = ts(7, 14)
        docs, cands = docs_with(now + 3600)
        calls = []

        def fetch(url):
            calls.append(url)
            return [{"key": "soccer_usa_usl", "group": "Soccer", "title": "USL Championship"}] if "/sports/?" in url else []
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "u.json"
            first = toa.collect_odds(docs, cands, now, key="k", fetcher=fetch, ledger_path=ledger)
            self.assertNotEqual(first["status"], "waiting_free_slot")
            self.assertTrue(calls)
            n = len(calls)
            again = toa.collect_odds(docs, cands, now + 1800, key="k", fetcher=fetch, ledger_path=ledger)
            self.assertEqual(again["status"], "already_checked")
            self.assertEqual(len(calls), n)
            usage = json.loads(ledger.read_text())
            self.assertIn("2026-11-18T00", usage["slots"])
            self.assertLessEqual(usage["credits"], toa.MONTHLY_CREDITS)

    def test_monthly_cap(self):
        now = ts(13, 40)
        docs, cands = docs_with(now + 3600)
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "u.json"
            ledger.write_text(json.dumps({"month": "2026-11", "credits": toa.MONTHLY_CREDITS, "slots": {}}))
            out = toa.collect_odds(docs, cands, now, key="k",
                                   fetcher=lambda u: self.fail("sem cota"), ledger_path=ledger)
            self.assertEqual(out["status"], "free_budget_exhausted")


class ApiFootballWideSlot(unittest.TestCase):
    def test_off_minute_run_uses_block_and_daily_cap(self):
        now = ts(7, 14)
        docs, cands = docs_with(now + 3600)
        calls = []

        def fetch(url, key):
            calls.append(url)
            return {"response": []}
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "a.json"
            first = apf.collect_odds(docs, cands, now, key="k", fetcher=fetch, ledger_path=ledger)
            self.assertNotEqual(first["status"], "waiting_budget_slot")
            self.assertEqual(len(calls), 1)
            again = apf.collect_odds(docs, cands, now + 600, key="k", fetcher=fetch, ledger_path=ledger)
            self.assertEqual(again["status"], "already_checked")
            usage = json.loads(ledger.read_text())
            self.assertEqual(usage["days"]["2026-11-18"], 1)
            # Teto diário respeitado mesmo em bloco novo.
            usage["days"]["2026-11-18"] = apf.DAILY_REQUESTS
            ledger.write_text(json.dumps(usage))
            capped = apf.collect_odds(docs, cands, ts(10, 5), key="k",
                                      fetcher=lambda *a: self.fail("sem cota"), ledger_path=ledger)
            self.assertEqual(capped["status"], "daily_budget_exhausted")


class OddsPapiWideSlot(unittest.TestCase):
    def test_off_window_run_with_ledger_is_allowed(self):
        now = ts(7, 14)
        docs, cands = docs_with(now + 3600)
        calls = []

        def fetch(url):
            calls.append(url)
            return []
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "p.json"
            out = opa.collect_odds(docs, cands, now, key="k", fetcher=fetch,
                                   ledger_path=ledger, sleep_fn=lambda s: None)
            self.assertNotEqual(out["status"], "waiting_free_slot")
            self.assertIn("2026-11-18T00", json.loads(ledger.read_text())["slots"])


if __name__ == "__main__":
    unittest.main()
