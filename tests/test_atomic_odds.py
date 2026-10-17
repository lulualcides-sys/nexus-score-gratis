import unittest
from datetime import datetime,timezone
from pregame_refresh_quotes import append_trio
from pregame_audit import odds_snapshot


class AtomicOddsTests(unittest.TestCase):
    def test_complete_trio_keeps_one_capture_when_one_selection_changes(self):
        now=1792000000
        row={'fixture':{'phase':'scheduled','start_timestamp':now+2400}}
        self.assertEqual(append_trio(row,{'home':2.2,'draw':3.2,'away':3.8},
                         'Casa A','ESPN',now),3)
        self.assertEqual(append_trio(row,{'home':2.2,'draw':3.2,'away':3.8},
                         'Casa A','ESPN',now+60),0)
        self.assertEqual(append_trio(row,{'home':2.1,'draw':3.2,'away':3.8},
                         'Casa A','ESPN',now+120),3)
        self.assertEqual(len(row['odds_quotes']),6)
        latest=odds_snapshot(row,now+120,now+2400)
        self.assertEqual(latest['prices'],{'home':2.1,'draw':3.2,'away':3.8})
        self.assertEqual(latest['source'],'ESPN')
        self.assertEqual(latest['bookmaker'],'Casa A')

    def test_no_partial_or_after_kickoff(self):
        now=1792000000
        row={'fixture':{'phase':'scheduled','start_timestamp':now+10}}
        self.assertEqual(append_trio(row,{'home':2.2,'draw':3.2},'Casa','ESPN',now),0)
        self.assertEqual(append_trio(row,{'home':2.2,'draw':3.2,'away':3.8},
                         'Casa','ESPN',now+10),0)
        self.assertFalse(row.get('odds_quotes'))


if __name__=='__main__':
    unittest.main()
