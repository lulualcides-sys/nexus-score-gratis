import unittest
from datetime import datetime,timedelta,timezone
from scout_snapshots import snapshot_deltas
NOW=datetime(2026,10,19,15,0,tzinfo=timezone.utc)
def item(minutes,stats,src='FotMob'):
 return {'at':(NOW+timedelta(minutes=minutes)).isoformat(),'minute':30+minutes,
         'source':src,'stats':stats}
class RealScoutChangeTests(unittest.TestCase):
 def test_only_real_differences_and_no_timeline_minutes(self):
  s=[item(0,{'home':{'shots_on':2,'corners':1,'xg':0.5},
               'away':{'shots_on':0,'corners':1}}),
     item(10,{'home':{'shots_on':4,'corners':2,'xg':0.9},
                'away':{'shots_on':1,'corners':1}})]
  t=snapshot_deltas(s)
  self.assertEqual(t['status'],'observed_delta')
  self.assertEqual(t['changes']['home']['shots_on'],2)
  self.assertEqual(t['changes']['away']['corners'],0)
  self.assertNotIn('minute',t)
  self.assertEqual(t['elapsed_minutes'],10)
 def test_counter_decrease_cannot_create_an_event(self):
  s=[item(0,{'home':{'shots_on':5,'corners':2}}),
     item(4,{'home':{'shots_on':3,'corners':4}})]
  result=snapshot_deltas(s)
  self.assertEqual(result['changes']['home'],{'corners':2})
 def test_different_source_and_gaps_fail_closed(self):
  s=[item(0,{'home':{'shots_on':1}}),
     item(5,{'home':{'shots_on':3}},'ESPN')]
  self.assertEqual(snapshot_deltas(s)['status'],'insufficient')
  s=[item(0,{'home':{'shots_on':1}}),
     item(50,{'home':{'shots_on':3}})]
  self.assertEqual(snapshot_deltas(s)['status'],'insufficient')
if __name__=='__main__':unittest.main()
