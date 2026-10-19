import unittest,tempfile,json
from pathlib import Path
from datetime import datetime,timezone
from oddspapi_historical import collect,historical_prices,historical_clv
KICK=int(datetime(2026,10,18,18,tzinfo=timezone.utc).timestamp())
NOW=int(datetime(2026,10,19,3,10,tzinfo=timezone.utc).timestamp())
def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
def packet():
    def entry(n,t):return {'price':n,'createdAt':iso(t),'active':False}
    return {'fixtureId':'id123456','bookmakers':{'pinnacle':{'markets':{'101':{'outcomes':{
     '101':{'players':{'0':[entry(2.2,KICK-5000),entry(2.1,KICK-100)]}},
     '102':{'players':{'0':[entry(3.1,KICK-4900),entry(3.2,KICK-90)]}},
     '103':{'players':{'0':[entry(4.2,KICK-4800),entry(4.3,KICK-80)]}}
    }}}}}}
def make_row():
    return {'oddspapi_fixture_id':'id123456','fixture':{'phase':'finished','start_timestamp':KICK},
      'odds_quotes':[{'market':'1x2','selection':'home','bookmaker':'Pinnacle',
                     'source':'OddsPapi','odds':2.4,'captured_at':iso(KICK-700)}]}
class HistTests(unittest.TestCase):
 def test_each_selection_uses_own_clock(self):
    q=historical_prices(packet(),KICK)
    self.assertEqual(len(q),3)
    self.assertEqual(next(x for x in q if x['selection']=='home')['last_odd'],2.1)
    self.assertNotEqual(q[0]['last_at'],q[1]['last_at'])
 def test_dont_accept_post_kickoff_prices(self):
    p=packet()
    p['bookmakers']['pinnacle']['markets']['101']['outcomes']['101']['players']['0'].append(
       {'price':9.7,'createdAt':iso(KICK+2)})
    self.assertEqual(next(x for x in historical_prices(p,KICK) if x['selection']=='home')['last_odd'],2.1)
 def test_cache_and_unchanged_live_quotes(self):
    doc={'2026-10-18':{'matches':{'a':make_row()}}}
    seen=[]
    def f(url):seen.append(url);return packet()
    with tempfile.TemporaryDirectory() as temp:
       path=Path(temp)/'audit.json'
       a=collect(doc,NOW,key='fake',fetcher=f,ledger_path=path)
       b=collect(doc,NOW+300,key='fake',fetcher=f,ledger_path=path)
       self.assertEqual((a['requests'],b['requests']), (1,0))
       self.assertEqual(a['prices_added'],3)
       self.assertEqual(len(seen),1)
       row=doc['2026-10-18']['matches']['a']
       self.assertEqual(len(row['odds_quotes']),1)
       self.assertNotIn('live_odds_quotes',row)
       self.assertEqual(historical_clv(row)[0]['movement_pct'],round(100*(2.4/2.1-1),2))
 def test_unknown_id_no_network(self):
    doc={'2026-10-18':{'matches':{'a':{**make_row(),'oddspapi_fixture_id':'../leak'}}}}
    with tempfile.TemporaryDirectory() as tmp:
       res=collect(doc,NOW,key='fake',ledger_path=Path(tmp)/'audit.json',
                   fetcher=lambda url:self.fail('network should not run'))
       self.assertEqual(res['requests'],0)
 def test_wrong_phase_or_time_no_network(self):
    doc={'2026-10-18':{'matches':{'a':{**make_row(),'fixture':{'phase':'scheduled','start_timestamp':KICK}}}}}
    with tempfile.TemporaryDirectory() as tmp:
       res=collect(doc,NOW,key='fake',ledger_path=Path(tmp)/'audit.json',
                   fetcher=lambda url:self.fail('network should not run'))
       self.assertEqual(res['requests'],0)
if __name__=='__main__':unittest.main()
