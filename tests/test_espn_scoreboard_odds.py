import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from espn_scoreboard_odds import normalized_team, linked_event, collect_odds, league_code

NOW = 1791580000

def game(home="Lexington SC", away="FC Tulsa", start=NOW+1800, league="USL Championship"):
    return {"fixture":{"id":"fotmob-123","home":home,"away":away,
            "league":league,"phase":"scheduled","start_timestamp":start}}

def event(home="Lexington", away="FC Tulsa", start=NOW+1800, ident="8888", offers=None):
    return {"id":ident,"date":datetime.fromtimestamp(start,timezone.utc).isoformat(),
      "competitions":[{"competitors":[
          {"homeAway":"home","team":{"displayName":home}},
          {"homeAway":"away","team":{"displayName":away}}],
          "odds":offers if offers is not None else []}]}

def prices():
    return [{"provider":{"name":"Casa verificada"},
       "homeTeamOdds":{"decimalOdds":2.18},"drawOdds":{"decimalOdds":3.25},
       "awayTeamOdds":{"decimalOdds":3.05}}]

class ESPNFixtureOddsTests(unittest.TestCase):
    def test_usl_team_alias_and_league(self):
        self.assertEqual(normalized_team("Lexington SC"),"lexington")
        self.assertEqual(normalized_team("FC Tulsa"),"tulsa")
        self.assertEqual(league_code("USL Championship"),"usa.usl.1")
    def test_match_requires_kickoff_and_both_sides(self):
        row=game()["fixture"]
        self.assertIsNotNone(linked_event(row,[event()]))
        self.assertIsNone(linked_event(row,[event(away="Indy Eleven")]))
        self.assertIsNone(linked_event(row,[event(start=NOW+3600)]))
        self.assertIsNone(linked_event(row,[event(),event(ident="8889")]))
    def test_capture_direct_board_prices_and_source(self):
        docs={"2026-10-09":{"matches":{"fotmob-123":game()}}}
        get=Mock(return_value={"events":[event(offers=prices())]})
        status=collect_odds(docs,[("2026-10-09","fotmob-123",1800)],NOW,get)
        self.assertEqual(status["quotes_added"],3)
        self.assertEqual(status["matched"],1)
        saved=docs["2026-10-09"]["matches"]["fotmob-123"]["odds_quotes"]
        self.assertEqual({x["selection"] for x in saved},{"home","draw","away"})
        self.assertEqual({x["bookmaker"] for x in saved},{"Casa verificada"})
        self.assertTrue(all(x["source"]=="ESPN" for x in saved))
        self.assertTrue(all(x["captured_at"] for x in saved))
    def test_capture_summary_when_board_has_no_prices(self):
        docs={"2026-10-09":{"matches":{"fotmob-123":game()}}}
        def get(url):
            return {"events":[event()]} if "/scoreboard?" in url else {"pickcenter":prices()}
        status=collect_odds(docs,[("2026-10-09","fotmob-123",1800)],NOW,get)
        self.assertEqual(status["quotes_added"],3)
        self.assertEqual(status["summaries_checked"],1)
    def test_never_assign_odds_without_strict_identity_or_before_kickoff(self):
        for row,offer,delta in [(game(),event(home="Another Team",offers=prices()),1800),
                                 (game(start=NOW-10),event(start=NOW-10,offers=prices()),-10)]:
            docs={"2026-10-09":{"matches":{"fotmob-123":row}}}
            status=collect_odds(docs,[("2026-10-09","fotmob-123",delta)],NOW,
                               lambda url:{"events":[offer]})
            self.assertEqual(status["quotes_added"],0)
            self.assertFalse(row.get("odds_quotes"))
    def test_no_prices_stays_unavailable(self):
        row=game();docs={"2026-10-09":{"matches":{"fotmob-123":row}}}
        status=collect_odds(docs,[("2026-10-09","fotmob-123",1800)],NOW,
              lambda url:{"events":[event()]} if "scoreboard" in url else {"pickcenter":[]})
        self.assertEqual(status["quotes_added"],0)
        self.assertFalse(row.get("odds_quotes"))

if __name__=="__main__": unittest.main()
