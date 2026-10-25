import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from telegram_collector.priority_espn import (
    add_fixture, choose_boards, game_key, league_code, parse_event,
    run, valid_odds,
)

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
KICK = NOW + timedelta(minutes=40)


def event(*, code="123", phase="pre", time=KICK, odds=True, home="Real Madrid", away="Barcelona"):
    comp = {"competitors": [
        {"homeAway": "home", "team": {"displayName": home}, "score": "2"},
        {"homeAway": "away", "team": {"displayName": away}, "score": "1"},
    ]}
    if odds:
        comp["odds"] = [{
            "provider": {"name": "Verified Public Book"},
            "homeTeamOdds": {"decimalOdds": 2.1},
            "drawOdds": {"decimalOdds": 3.4},
            "awayTeamOdds": {"decimalOdds": 3.3}
        }]
    return {
        "id": code, "date": time.isoformat().replace("+00:00", "Z"),
        "status": {"type": {"state": phase}}, "competitions": [comp]
    }


class PriorityEspnTests(unittest.TestCase):
    def test_league_catalog_prioritizes_important(self):
        self.assertEqual(league_code("Liga MX"), "mex.1")
        self.assertEqual(league_code("Champions League"), "uefa.champions")
        self.assertEqual(league_code("Copa do Brasil"), "bra.copa_do_brazil")
        self.assertIsNone(league_code("Primera División"))  # ambiguous countries
        self.assertIsNone(league_code("Canadian Premier League"))
        self.assertIsNone(league_code("Premier League"))  # ambiguous countries
        self.assertIsNone(league_code("Copa Libertadores Femenina"))
        self.assertIsNone(league_code("Liga MX Femenil"))
        self.assertIsNone(league_code("MLS Next Pro"))
        self.assertEqual(league_code("UEFA Champions League"), "uefa.champions")
        self.assertEqual(league_code("Copa Libertadores"), "conmebol.libertadores")

    def test_strict_quotes_require_full_trio_and_named_book(self):
        sample = parse_event(event())
        self.assertEqual(len(valid_odds(sample["odds"], NOW.timestamp(), sample["ts"])), 3)
        self.assertEqual(valid_odds(sample["odds"], KICK.timestamp(), sample["ts"]), [])
        incomplete = [{"provider": {"name": "A"}, "homeTeamOdds": {"decimalOdds": 2.2}}]
        self.assertEqual(valid_odds(incomplete, NOW.timestamp(), sample["ts"]), [])
        anon = event()
        anon["competitions"][0]["odds"][0].pop("provider")
        self.assertEqual(valid_odds(parse_event(anon)["odds"], NOW.timestamp(), sample["ts"]), [])

    def test_game_key_never_crashes_on_null_timestamp(self):
        self.assertIsNone(game_key({"home": "A", "away": "B"}))
        self.assertIsNone(game_key({"home": "A", "away": "B", "kickoff_unix": "oops"}))

    def test_prioritized_board_selection_is_bounded(self):
        boards = choose_boards(NOW, {}, max_boards=8)
        self.assertEqual(len(boards), 8)
        self.assertEqual(len(set(boards)), 8)
        self.assertTrue(all(x[0] for x in boards))

    def test_adds_imported_odds_but_never_overwrites_old_quotes(self):
        archive = {}
        sample = parse_event(event())
        created, n, key, priced = add_fixture(archive, "esp.1", "La Liga", sample, NOW.isoformat())
        self.assertTrue(created)
        self.assertEqual(n, 3)
        self.assertTrue(priced)
        day = "2026-10-25"
        stored = archive[day]["games"][key]["observations"]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["odds"][0]["bookmaker"], "Verified Public Book")
        _, n2, _, _ = add_fixture(archive, "esp.1", "La Liga", sample, NOW.isoformat())
        self.assertEqual(n2, 0)
        self.assertEqual(len(stored), 1)
        # Prices with later observed-at are separate snapshots, not overwritten.
        later = NOW + timedelta(minutes=5)
        _, n3, _, _ = add_fixture(archive, "esp.1", "La Liga", sample, later.isoformat())
        self.assertEqual(n3, 3)
        self.assertEqual(len(stored), 2)

    def test_finished_match_has_only_real_score_no_retroactive_prices(self):
        archive = {}
        match = parse_event(event(phase="post", odds=True))
        _, new, key, has_prices = add_fixture(
            archive, "esp.1", "La Liga", match, (KICK + timedelta(hours=2)).isoformat())
        self.assertEqual(new, 0)
        self.assertFalse(has_prices)
        rec = archive["2026-10-25"]["games"][key]["observations"][0]
        self.assertEqual(rec["phase"], "finished")
        self.assertEqual(rec["settlement"]["match_odds"], "home")
        self.assertEqual(rec["odds"] if "odds" in rec else [], [])

    def test_network_is_fake_but_archive_roundtrip_is_real(self):
        def fake_fetch(code, day):
            if code == "esp.1" and day == "2026-10-25":
                return [event()]
            return []
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            a = run(p, NOW, board_fetcher=fake_fetch, max_boards=35)
            self.assertGreaterEqual(a["priority_fixtures_seen"], 1)
            self.assertEqual(a["new_quotes"], 3)
            b = run(p, NOW, board_fetcher=fake_fetch, max_boards=35)
            self.assertEqual(b["new_quotes"], 0)
            doc = json.loads((p / "2026-10-25.json").read_text(encoding="utf-8"))
            self.assertEqual(len(doc["games"]), 1)
            self.assertEqual(len(next(iter(doc["games"].values()))["observations"]), 1)

    def test_espn_summary_fallback_only_for_pregame_and_bounded(self):
        from telegram_collector.priority_espn import PRIORITY
        seen = []
        no_board_odds = event(odds=False)
        full = event()["competitions"][0]["odds"]
        def fetch_board(code, day):
            if code == "esp.1" and day == "2026-10-25":
                return [no_board_odds]
            return []
        def fetch_summary(code, event_id):
            seen.append((code,event_id))
            return full
        with TemporaryDirectory() as tmp:
            report = run(Path(tmp), NOW, board_fetcher=fetch_board,
                         summary_fetcher=fetch_summary, max_boards=35, max_summaries=1)
            self.assertEqual(report["summary_checks"], 1)
            self.assertEqual(report["summary_with_prices"], 1)
            self.assertEqual(report["new_quotes"], 3)
            self.assertEqual(len(seen), 1)
            rec = json.loads((Path(tmp) / "2026-10-25.json").read_text())
            saved = next(iter(rec["games"].values()))
            self.assertEqual(saved["observations"][0]["odds"][0]["source"], "ESPN public summary")

    def test_espn_summary_does_not_backfill_after_kickoff(self):
        def fetch_board(code, day):
            return [event(phase="post", odds=False)] if code == "esp.1" and day == "2026-10-25" else []
        called = []
        with TemporaryDirectory() as tmp:
            report = run(Path(tmp), NOW, board_fetcher=fetch_board,
                         summary_fetcher=lambda *args: called.append(args), max_boards=35)
            self.assertEqual(report["summary_checks"], 0)
            self.assertFalse(called)

    def test_fetch_failure_does_not_destroy_archive(self):
        def broken(code, day):
            raise TimeoutError("provider went away")
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            archive = p / "2026-10-25.json"
            archive.write_text(json.dumps({"schema": 1, "day": "2026-10-25", "games": {}}))
            report = run(p, NOW, board_fetcher=broken, max_boards=2)
            self.assertEqual(report["boards_ok"], 0)
            self.assertEqual(len(report["errors"]), 2)
            self.assertEqual(json.loads(archive.read_text())["games"], {})


if __name__ == "__main__":
    unittest.main()
