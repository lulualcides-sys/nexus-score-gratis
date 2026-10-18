import unittest
import json
from web_export import make_listing

class TestCompactFeed(unittest.TestCase):
 def make_game(self,ident,phase):
    return dict(id=ident,day='2026-10-17',home='Casa',away='Visitante',
       phase=phase,minute=60,score='0-0',league='Liga',start_timestamp=1792000000,
       observed_at='2026-10-17T20:00:00+00:00',
       pressure_observed_at='2026-10-17T20:00:00+00:00',
       pressure=[{'m':i,'v':5+i} for i in range(1,60)],
       stats={'home':{'shots_on':2},'away':{'shots_on':1}},
       odds=[{'sel':'home','odd':2.2,'source':'ESPN'}],
       signals=[{'private':'not for listing'}],
       pregame_baseline={'captured_at':'2026-10-17T18:00:00+00:00'},
       roster={'home':[{'name':'Atleta'}]},
       scout_snapshots=[{'massive':('evidence '*1000)} for _ in range(30)])

 def test_removes_heavy_fields_but_keeps_real_live_pressure(self):
    games=[self.make_game('a','live'),self.make_game('b','finished')]
    lite=make_listing(games,'2026-10-17T21:00:00Z',{'live_found':1})
    self.assertEqual(lite['schema'],3)
    self.assertEqual(lite['format'],'listing_only')
    self.assertEqual(len(lite['games']),2)
    self.assertEqual(len(lite['games'][0]['pressure']),59)
    self.assertEqual(len(lite['games'][1]['pressure']),1)
    self.assertEqual(lite['games'][0]['minute'],60)
    self.assertEqual(lite['games'][0]['stats']['home']['shots_on'],2)
    self.assertNotIn('roster',lite['games'][0])
    self.assertNotIn('scout_snapshots',lite['games'][0])
    self.assertNotIn('pregame_baseline',lite['games'][0])
    self.assertNotIn('signals',lite['games'][0])
    old=json.dumps(games,ensure_ascii=False)
    new=json.dumps(lite,ensure_ascii=False)
    self.assertLess(len(new),len(old)//3)
    self.assertEqual(len(games[0]['pressure']),59)
    self.assertEqual(len(games[0]['scout_snapshots']),30)

 def test_empty_day_and_cache_immutable(self):
    lite=make_listing([], '2026-10-17T00:00:00Z',{})
    self.assertEqual(lite['games'],[])
    self.assertEqual(lite['exported_at'],'2026-10-17T00:00:00Z')

if __name__=='__main__':unittest.main()
