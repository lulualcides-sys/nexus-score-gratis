import unittest

from activity_timeline import observed_activity


class ActivityTimelineTests(unittest.TestCase):
    def test_only_real_events_count_and_keep_sides(self):
        events=[
            {'minute':12,'type':'shot_on','side':'home','text':'A'},
            {'minute':12,'type':'shot_off','side':'away','text':'B'},
            {'minute':12,'type':'big_chance_missed','side':'away','text':'C'},
            {'minute':24,'type':'goal','side':'home','text':'D'},
        ]
        value=observed_activity(events)
        self.assertEqual(value['basis'],'confirmed_event_count')
        self.assertEqual(value['total_events'],4)
        self.assertEqual(value['points'],[
            {'m':12,'home':1,'away':2,'types':{'shot_on':1,'shot_off':1,'big_chance_missed':1}},
            {'m':24,'home':1,'away':0,'types':{'goal':1}}])

    def test_no_imputation_for_empty_minutes_and_no_leakage_of_fake_snapshots(self):
        value=observed_activity([
            {'minute':15,'type':'shot_on','side':'home','text':'A'},
            {'minute':17,'type':'shot_on','side':'home','text':'B'},
            {'minute':19,'type':'shots_total','side':'home'},
            {'minute':20,'type':'shot_on','side':''},
            {'minute':21,'type':'shot_on','side':'home','basis':'snapshot'},
            {'minute':22,'type':'shot_on','side':'home','basis':'calculated'}
        ])
        self.assertEqual([x['m'] for x in value['points']],[15,17])
        self.assertEqual(value['total_events'],2)

    def test_duplicate_event_rows_are_counted_once(self):
        event={'minute':55,'type':'shot_on','side':'away','text':'Person'}
        self.assertEqual(observed_activity([event,event])['total_events'],1)

    def test_finished_and_stoppage_time_not_excluded(self):
        value=observed_activity([{'minute':95,'type':'penalty_missed','side':'away','text':'P'}])
        self.assertEqual(value['points'][0]['m'],95)

    def test_invalid_events_and_injection(self):
        value=observed_activity([
            {'minute':3.5,'type':'shot_on','side':'home','text':'X'},
            {'minute':-1,'type':'goal','side':'away'},
            {'minute':140,'type':'goal','side':'home'},
            {'minute':6,'type':'goal','side':'home','text':'<script>alert(1)</script>'},
            {'minute':10,'type':'red_card','side':'home'},
        ])
        self.assertEqual(value['points'],[{'m':6,'home':1,'away':0,'types':{'goal':1}}])
        self.assertNotIn('script',str(value))

    def test_events_are_not_provider_momentum(self):
        value=observed_activity([{'minute':25,'type':'shot_on','side':'home'}])
        self.assertNotIn('pressure',value)
        self.assertNotIn('confidence',value)
        self.assertEqual(value['total_events'],1)


if __name__=='__main__':
    unittest.main()
