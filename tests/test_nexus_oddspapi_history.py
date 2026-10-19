import unittest
from datetime import datetime,timezone
from oddspapi_history import summarize_history,collect
NOW=int(datetime(2026,10,19,12,0,tzinfo=timezone.utc).timestamp())
def stamp(ts):return datetime.fromtimestamp(ts,timezone.utc).isoformat()
class HistoricalOddsTests(unittest.TestCase):
 def test_only_real_pre_kickoff_snapshots(self):
  data={'fixtureId':'id123','bookmakers':{'pinnacle':{'markets':{'101':{
    'outcomes':{k:{'players':{'0':[{'createdAt':stamp(NOW-500),'price':1.9},
                               {'createdAt':stamp(NOW-30),'price':2.1},
                               {'createdAt':stamp(NOW+10),'price':9}]}}
                for k in ('101','102','103')}}}}}}
  output=summarize_history(data,'id123',NOW)
  self.assertEqual(len(output),1)
  self.assertEqual(output[0]['prices']['home']['opening'],1.9)
  self.assertEqual(output[0]['prices']['home']['closing'],2.1)
  self.assertEqual(summarize_history(data,'id456',NOW),[])
  del data['bookmakers']['pinnacle']['markets']['101']['outcomes']['103']
  self.assertEqual(summarize_history(data,'id123',NOW),[])
 def test_no_id_no_request(self):
  doc={'2026-10-19':{'matches':{'f1':{'fixture':{
    'phase':'finished','start_timestamp':NOW-120}}}}}
  called=[]
  out=collect(doc,NOW,key='mock',fetcher=lambda *x:called.append(x))
  self.assertEqual(out['checked'],0)
  self.assertEqual(called,[])
 def test_finished_id_recorded_at_most_once(self):
  doc={'2026-10-19':{'matches':{'f1':{'fixture':{
    'phase':'finished','start_timestamp':NOW-120},'oddspapi_fixture_id':'id123'}}}}
  def fetch(fid,key):
   return {'fixtureId':fid,'bookmakers':{'pinnacle':{'markets':{
    '101':{'outcomes':{k:{'players':{'0':[{
      'createdAt':stamp(NOW-240),'price':1.8}]}} for k in ('101','102','103')}}}}}}
  self.assertEqual(collect(doc,NOW,key='mock',fetcher=fetch)['stored'],1)
  self.assertEqual(collect(doc,NOW,key='mock',fetcher=fetch)['checked'],0)
  self.assertEqual(doc['2026-10-19']['matches']['f1']['oddspapi_history']['scope'],'historical_only')
if __name__=='__main__':unittest.main()
