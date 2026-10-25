import unittest
from datetime import datetime,timedelta,timezone
from telegram_collector.market_depth import summarize

NOW = datetime(2026,10,25,17,0,tzinfo=timezone.utc)
START = (NOW+timedelta(hours=2)).isoformat()

def q(key, market, sel, price, t=NOW):
    return {
        "market_family":market,"raw_market_key":key,"selection":sel,
        "odds_decimal":price,"line":2.5,"period":0,
        "bookmaker":"Pinnacle","observed_at":t.isoformat()
    }

def doc(odds, stamp=NOW):
    return {"schema":1,"checked_at":stamp.isoformat(),
            "matches":{"a":{"home":"A","away":"B","kickoff_utc":START,"odds":odds}}}

class QualityTests(unittest.TestCase):
    def test_complete_book_overround_and_no_fantasy_odds(self):
        data=doc([q("s;0;m","match_odds","home",2.4),
                  q("s;0;m","match_odds","draw",3.5),
                  q("s;0;m","match_odds","away",3.5),
                  q("s;0;ou;2.5","total_goals","over",1.8),
                  q("s;0;ou;2.5","total_goals","under",2.05)])
        out=summarize(data,NOW)
        self.assertEqual(out["matches_with_priced_markets"],1)
        self.assertEqual(out["odds_eligible_for_quality"],5)
        self.assertEqual(out["complete_market_lines"],2)
        self.assertEqual(out["incomplete_market_lines"],0)
        self.assertAlmostEqual(out["families"]["match_odds"]["median_overround_pct"],-1.19,delta=.08)
        self.assertNotIn("roi",out)

    def test_asian_handicap_opposite_price_points_form_one_market(self):
        first=q("s;0;s;-0.5","asian_handicap","home",2.46)
        second=q("s;0;s;-0.5","asian_handicap","away",1.5587)
        first["line"]=-0.5
        second["line"]=0.5
        out=summarize(doc([first,second]),NOW)
        self.assertEqual(out["complete_market_lines"],1)
        self.assertEqual(out["families"]["asian_handicap"]["complete_lines"],1)

    def test_one_sided_market_is_not_complete(self):
        d=doc([q("s;0;m","match_odds","home",1.7)])
        out=summarize(d,NOW)
        self.assertEqual(out["complete_market_lines"],0)
        self.assertEqual(out["incomplete_market_lines"],1)
        self.assertIsNone(out["families"]["match_odds"]["median_overround_pct"])

    def test_pregame_and_freshness_strict(self):
        d=doc([q("s;0;m","match_odds","home",2.4, NOW+timedelta(hours=3)),
               q("s;0;m","match_odds","draw",3.5),
               q("s;0;m","match_odds","away",3.5)])
        out=summarize(d,NOW)
        self.assertEqual(out["invalid_quote_records"],1)
        self.assertEqual(out["complete_market_lines"],0)
        with self.assertRaises(ValueError):
            summarize(doc([],stamp=NOW-timedelta(hours=5)),NOW)

if __name__=="__main__":
    unittest.main()
