import unittest
from scout_snapshots import append_snapshot, public_snapshots

AT='2026-10-10T04:00:00+00:00'


class ScoutSnapshotTests(unittest.TestCase):
    def test_preserves_real_counts_and_time_without_fabricating_other_team(self):
        rows=append_snapshot([],{'home':{'shots_on':3,'xg':0.51},'away':{}},37,AT)
        self.assertEqual(rows[0]['minute'],37)
        self.assertEqual(rows[0]['stats']['home']['shots_on'],3)
        self.assertNotIn('shots_on',rows[0]['stats']['away'])
        self.assertEqual(len(public_snapshots(rows)),1)

    def test_deduplicates_same_minute_latest_capture_only(self):
        prev=append_snapshot([],{'home':{'shots_on':2}},20,AT)
        next_rows=append_snapshot(prev,{'home':{'shots_on':3}},20,'2026-10-10T04:00:04+00:00')
        self.assertEqual(len(next_rows),1)
        self.assertEqual(next_rows[0]['stats']['home']['shots_on'],3)
        self.assertEqual(append_snapshot(next_rows,{'home':{'shots_on':0}},20,AT),next_rows)

    def test_rejects_invalid_minute_and_unobserved_numbers(self):
        self.assertEqual(append_snapshot([],{'home':{'shots_on':5}},None,AT),[])
        self.assertEqual(append_snapshot([],{'home':{'shots_on':5}},0,AT),[])
        self.assertEqual(append_snapshot([],{'home':{'shots_on':5}},20,'invalid'),[])
        self.assertEqual(append_snapshot([],{'home':{'shots_on':float('nan'),
            'xg':-2,'corners':2.5}},20,AT),[])

    def test_history_is_bounded_without_spoofing_a_shot_event(self):
        rows=[]
        for minute in range(1,110):
            rows=append_snapshot(rows,{'away':{'shots_on':minute//5}},minute,
                                 f'2026-10-10T04:{minute%60:02d}:00+00:00')
        self.assertLessEqual(len(rows),72)
        self.assertTrue(all('event_type' not in x for x in rows))
        self.assertTrue(all('at' in x and 'minute' in x for x in rows))


if __name__=='__main__':
    unittest.main()
