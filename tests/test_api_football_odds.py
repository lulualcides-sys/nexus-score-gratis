import unittest
from datetime import datetime,timezone,timedelta
from api_football_odds import collect_odds,match_fixture,odds_trio
from pregame_audit import odds_snapshot


class APIFootballFreeOddsTests(unittest.TestCase):
 def fixtures(self):
  now=int(datetime(2026,10,18,0,3,tzinfo=timezone.utc).timestamp())
  kickoff=now+20*60
  row={'fixture':{'id':'fotmob-500','home':'Vélez Sarsfield','away':'Gimnasia Mendoza',
                  'phase':'scheduled','start_timestamp':kickoff}}
  events=[{'fixture':{'id':101,'timestamp':kickoff},
           'teams':{'home':{'name':'Velez Sarsfield'},
                    'away':{'name':'Gimnasia Mendoza'}}}]
  quotes=[{'fixture':{'id':101},'update':datetime.fromtimestamp(now-60,timezone.utc).isoformat(),
    'bookmakers':[{'name':'Casa verificada','bets':[{'id':1,'name':'Match Winner',
      'values':[{'value':'Home','odd':'1.76'},{'value':'Draw','odd':'3.65'},
                {'value':'Away','odd':'4.70'}]}]}]}]
  return now, row,events,quotes

 def test_strict_identity_and_source_update_time(self):
  now,row,events,quotes=self.fixtures()
  self.assertEqual(match_fixture(row['fixture'],events),101)
  triple=odds_trio({'response':quotes},101,now)
  self.assertEqual(triple[0],{'home':1.76,'draw':3.65,'away':4.7})
  self.assertLess(triple[2],now)
  docs={'2026-10-18':{'matches':{'fotmob-500':row}}}
  calls=[]
  def fake(url,key):
   self.assertEqual(key,'private-from-runner')
   calls.append(url)
   return {'response':events if '/fixtures?' in url else quotes}
  report=collect_odds(docs,[('2026-10-18','fotmob-500',1200)],now,
                      key='private-from-runner',fetcher=fake)
  self.assertEqual(report['status'],'checked')
  self.assertEqual(report['quotes_added'],3)
  self.assertEqual(report['requests'],2)
  self.assertEqual(len(calls),2)
  self.assertNotIn('private-from-runner',str(report))
  saved=odds_snapshot(row,now,row['fixture']['start_timestamp'])
  self.assertEqual(saved['prices']['away'],4.70)
  self.assertEqual(saved['source'],'API-Football')
  self.assertTrue(saved['recent_at_check'])
  self.assertEqual(saved['captured_at'],datetime.fromtimestamp(now-60,timezone.utc).isoformat())

 def test_reject_wrong_team_and_ambiguous_event(self):
  now,row,events,quotes=self.fixtures()
  wrong=[{**events[0],'teams':{
      'home':{'name':'Outro Vélez'},'away':{'name':'Gimnasia Mendoza'}}}]
  self.assertIsNone(match_fixture(row['fixture'],wrong))
  self.assertIsNone(match_fixture(row['fixture'],events*2))
  self.assertIsNone(odds_trio({'response':[{
       **quotes[0],'bookmakers':[{'name':'Casa','bets':[{'id':1,
        'name':'Match Winner','values':[{'value':'Home','odd':'2.1'}]}]}]}]},101,now))

 def test_disabled_without_key_and_skip_extra_calls(self):
  now,row,events,quotes=self.fixtures()
  docs={'2026-10-18':{'matches':{'fotmob-500':row}}}
  def forbid(*args):raise AssertionError('Nunca chamar API sem autorização')
  self.assertEqual(collect_odds(docs,[('2026-10-18','fotmob-500',1200)],now,
                                key='',fetcher=forbid)['status'],'not_configured')
  self.assertEqual(collect_odds(docs,[('2026-10-18','fotmob-500',1200)],now+900,
                                key='configured',fetcher=forbid)['status'],'waiting_budget_slot')
  self.assertFalse(row.get('odds_quotes'))

if __name__=='__main__':
 unittest.main()
