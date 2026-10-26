import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from telegram_collector.market_motion import normalized_price, run, summarize

NOW = datetime(2026, 10, 25, 21, 0, tzinfo=timezone.utc)
START = NOW + timedelta(hours=5)

def price(p, captured, selection="over", market="s;0;ou;2.5", family="total_goals"):
    return {"bookmaker":"Pinnacle","raw_market_key":market,
            "market_family":family,"selection":selection,
            "odds_decimal":p,"observed_at":captured.isoformat()}

def shot(at, quotations):
    return {"observed_at":at.isoformat(), "checksum":"test", "quotes":quotations}

def doc(shots, kickoff=START):
    return {"schema":1,"observed_day":"2026-10-25",
            "games":{"11":{"home":"Flamengo","away":"Corinthians","league":"Brazil Serie A",
                            "kickoff_utc":kickoff.isoformat(),
                            "snapshots":shots}}}

class MarketMotionTests(unittest.TestCase):
    def test_moving_prices_only_before_kickoff_and_never_called_profit(self):
        t1=NOW-timedelta(hours=2)
        t2=NOW-timedelta(minutes=15)
        t3=NOW+timedelta(hours=6)
        data=doc([
            shot(t2,[price(1.95,t2)]),
            shot(t1,[price(2.10,t1)]),
            shot(t3,[price(1.50,t3)])
        ])
        out=summarize(data,NOW)
        self.assertEqual(out["status"],"fresh")
        self.assertEqual(out["market_selections_with_changes"],1)
        move=out["top_changes"][0]
        self.assertEqual(move["first_odds"],2.10)
        self.assertEqual(move["last_odds"],1.95)
        self.assertAlmostEqual(move["implied_probability_change_pp"],
                               round(100*(1/1.95-1/2.1),3))
        self.assertFalse(move["betting_execution_confirmed"])
        self.assertEqual(out["snapshots_processed"],2)

    def test_unmatched_selections_never_combined(self):
        t1=NOW-timedelta(hours=1)
        t2=NOW
        s=[shot(t1,[price(2.20,t1,selection="over")]),
           shot(t2,[price(1.70,t2,selection="under")])]
        self.assertEqual(summarize(doc(s),NOW)["market_selections_with_changes"],0)

    def test_no_fake_delta_for_same_odds_and_stale_data(self):
        t1=NOW-timedelta(hours=8)
        t2=NOW-timedelta(hours=7)
        s=[shot(t1,[price(1.93,t1)]), shot(t2,[price(1.93,t2)])]
        out=summarize(doc(s),NOW)
        self.assertEqual(out["market_selections_with_changes"],0)
        self.assertEqual(out["status"],"historical_or_unavailable")

    def test_invalid_or_post_game_captured_quote_rejected(self):
        t1=NOW-timedelta(hours=1)
        t2=NOW
        s=[shot(t1,[price(2.1,NOW+timedelta(minutes=1))]),
           shot(t2,[price(1.91,t2)])]
        out=summarize(doc(s),NOW)
        self.assertEqual(out["snapshots_processed"],1)
        self.assertEqual(out["market_selections_with_changes"],0)
        self.assertGreater(out["invalid_quote_records"],0)

    def test_daily_persisted_archive_roundtrip_no_network(self):
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)/"public-no-key"
            folder.mkdir()
            t1=NOW-timedelta(hours=1)
            t2=NOW
            day=NOW.astimezone(__import__("zoneinfo").ZoneInfo("America/Sao_Paulo")).date().isoformat()
            (folder/("pinnacle-"+day+".json")).write_text(
                json.dumps(doc([shot(t1,[price(2.30,t1)]),shot(t2,[price(2.01,t2)])])))
            first=run(Path(tmp),NOW)
            self.assertEqual(first["market_selections_with_changes"],1)
            self.assertEqual(json.loads((folder/"pinnacle-motion-latest.json").read_text())["top_changes"][0]["last_odds"],2.01)
            (folder/("pinnacle-"+day+".json")).unlink()
            empty=run(Path(tmp),NOW)
            self.assertEqual(empty["status"],"unavailable")
            self.assertEqual(empty["top_changes"],[])

    def test_price_validation(self):
        self.assertIsNone(normalized_price(price(1.0,NOW)))
        self.assertIsNone(normalized_price(price(float("nan"),NOW)))
        self.assertIsNotNone(normalized_price(price(2.0,NOW)))

if __name__=="__main__":
    unittest.main()
