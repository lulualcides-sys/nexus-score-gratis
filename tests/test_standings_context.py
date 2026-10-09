import unittest
from standings_context import league_table, team_stakes, make_context
class MustWinTests(unittest.TestCase):
 def table(self):
  rows=[{'idx':i,'id':100+i,'name':'Time'+str(i),'played':25,'pts':50-i} for i in range(1,21)]
  rows[3]['pts']=44;rows[4]['pts']=43
  rows[15]['pts']=18;rows[16]['pts']=17;rows[17]['pts']=16
  return league_table({'details':{'id':268,'name':'Brasileirão Série A','selectedSeason':'2026'},
    'table':[{'data':{'table':{'all':rows}}}]},'268')
 def test_g4(self):
  t=self.table()
  self.assertEqual(team_stakes(t,'105')['reasons'][0]['kind'],'buscar_g4')
  self.assertEqual(team_stakes(t,'104')['reasons'][0]['kind'],'defender_g4')
 def test_relegation_zone(self):
  t=self.table()
  self.assertIn('sair_z4',[x['kind'] for x in team_stakes(t,'117')['reasons']])
  self.assertIn('evitar_z4',[x['kind'] for x in team_stakes(t,'116')['reasons']])
  other={**t,'league_id':'112233','league':'Copa Grupos'}
  self.assertFalse(any(x['kind'].endswith('z4') for x in team_stakes(other,'117')['reasons']))
 def test_ignore_cup_groups(self):
  doc={'details':{'id':42},'table':[
    {'data':{'table':{'all':[{'id':i,'name':str(i),'idx':i,'pts':1,'played':3} for i in range(1,11)]}}},
    {'data':{'table':{'all':[{'id':i,'name':str(i),'idx':i,'pts':1,'played':3} for i in range(1,11)]}}}]}
  self.assertIsNone(league_table(doc,'42'))
 def test_only_exact_team_and_league(self):
  t=self.table()
  f={'league_id':'268','home_id':'104','away_id':'105'}
  c=make_context(f,t)
  self.assertEqual(c['home']['position'],4)
  self.assertEqual(c['away']['position'],5)
  self.assertIsNone(make_context({**f,'league_id':'47'},t))
  self.assertIsNone(make_context({**f,'home_id':'9999'},t))
if __name__=='__main__':unittest.main()
