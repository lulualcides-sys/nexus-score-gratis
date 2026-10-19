import unittest
from datetime import datetime,timezone,timedelta
from web_export import alerts_from,observed_milestones,recent_observation
NOW=datetime(2026,10,19,16,tzinfo=timezone.utc)
T=NOW.timestamp()
def at(minutes):return (NOW+timedelta(minutes=minutes)).isoformat()
def fixture(phase='live'):
    return {'id':'g1','day':'2026-10-19','phase':phase,'home':'Casa','away':'Fora',
      'start_timestamp':int(T-1800 if phase=='live' else T+3600),
      'observed_at':at(-2),'signals':[], 'odds':[],
      'stats':{'home':{'shots_on':4,'corners':5},
               'away':{'shots_on':3,'corners':4}},
      'scout_trend':{'status':'insufficient'},
      'scout_snapshots':[
        {'m':30,'at':at(-12),'source':'FotMob','stats':{
          'home':{'shots_on':3,'corners':4},'away':{'shots_on':3,'corners':4}}},
        {'m':38,'at':at(-2),'source':'FotMob','stats':{
          'home':{'shots_on':4,'corners':5},'away':{'shots_on':3,'corners':4}}}
       ],
      'lineups':{}}
class AlertsTest(unittest.TestCase):
 def test_only_observed_crossings(self):
    g=fixture()
    found=observed_milestones(g,T)
    self.assertEqual(len(found),2)
    self.assertEqual({x['kind'] for x in found},{'stat_milestone'})
    self.assertTrue(all('minuto exato' in x['detail'] for x in found))
    ids=[x['id'] for x in alerts_from([g],T)]
    self.assertEqual(len(ids),len(set(ids)))
 def test_old_live_game_cannot_trigger(self):
    g=fixture()
    g['observed_at']=at(-45)
    self.assertEqual(alerts_from([g],T),[])
    self.assertFalse(recent_observation(at(-45),T))
 def test_old_scout_snapshot_cannot_trigger(self):
    g=fixture()
    for record in g['scout_snapshots']:record['at']=at(-90)
    self.assertEqual(observed_milestones(g,T),[])
 def test_cumulative_totals_without_crossing_no_alert(self):
    g=fixture()
    g['scout_snapshots'][0]['stats']={'home':{'shots_on':4,'corners':5},
        'away':{'shots_on':3,'corners':4}}
    self.assertEqual(observed_milestones(g,T),[])
 def test_only_recent_pregame_data(self):
    g=fixture('scheduled')
    g['odds']=[{'sel':'home','odd':2,'at':at(-15)},
               {'sel':'draw','odd':3.1,'at':at(-15)},
               {'sel':'away','odd':3.6,'at':at(-15)}]
    alerts=alerts_from([g],T)
    self.assertEqual([a['kind'] for a in alerts],['odds_watch'])
    g['odds'][0]['at']=at(-500)
    self.assertEqual(alerts_from([g],T),[])
 def test_alerts_sorted_and_capped(self):
    many=[]
    for i in range(60):
      row=fixture('scheduled')
      row['id']=str(i)
      row['odds']=[{'sel':'home','odd':2,'at':at(-1)}]
      many.append(row)
    self.assertEqual(len(alerts_from(many,T)),35)
if __name__=='__main__':unittest.main()
