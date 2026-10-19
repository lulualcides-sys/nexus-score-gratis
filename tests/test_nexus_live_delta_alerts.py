import unittest
from datetime import datetime,timezone,timedelta
from web_export import live_delta_alert
class LiveDeltaTest(unittest.TestCase):
 def build(self,now):
    return {'id':'game-1','day':'2026-10-19','home':'Casa','away':'Visitante',
      'phase':'live','scout_trend':{'status':'observed_delta','source':'FotMob',
        'elapsed_minutes':7,'to_at':datetime.fromtimestamp(now-120,timezone.utc).isoformat(),
        'changes':{'home':{'shots_on':2,'xg':0.53},'away':{'shots_on':0}}}}
 def test_real_change_creates_scoped_alert(self):
    now=datetime.now(timezone.utc).timestamp()
    item=live_delta_alert(self.build(now),now)
    self.assertEqual(item['kind'],'stat_delta')
    self.assertIn('Casa',item['title'])
    self.assertIn('desconhecido',item['detail'])
    self.assertNotIn('EV garantido',item['detail'])
 def test_no_fake_alert_with_missing_or_stale_data(self):
    now=datetime.now(timezone.utc).timestamp()
    g=self.build(now)
    g['scout_trend']['status']='insufficient'
    self.assertIsNone(live_delta_alert(g,now))
    g=self.build(now)
    g['scout_trend']['to_at']=(datetime.fromtimestamp(now-5000,timezone.utc)).isoformat()
    self.assertIsNone(live_delta_alert(g,now))
 def test_low_growth_and_wrong_phase_are_not_signals(self):
    now=datetime.now(timezone.utc).timestamp()
    g=self.build(now)
    g['scout_trend']['changes']={'home':{'shots_on':1,'xg':0.1},'away':{}}
    self.assertIsNone(live_delta_alert(g,now))
    g=self.build(now);g['phase']='finished'
    self.assertIsNone(live_delta_alert(g,now))
if __name__=='__main__':unittest.main()
