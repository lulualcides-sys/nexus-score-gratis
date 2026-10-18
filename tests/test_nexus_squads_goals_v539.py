import unittest
from coletar import fotmob_events, fotmob_lineups, fotmob_match_stars, merge_verified_events
from team_player_leaders import team_player_leaders
from web_export import public_row
from backfill import extract_events

class VerifiedLineupsAndGoals(unittest.TestCase):
 def test_shotmap_completes_four_missing_goals_without_duplicates(self):
  packet={'general':{'homeTeam':{'id':1},'awayTeam':{'id':2}},
   'content':{'matchFacts':{'events':{'events':[
       {'type':'Goal','time':12,'isHome':True,'player':{'name':'Harry Kane'}},
       {'type':'Goal','time':24,'isHome':False,'nameStr':'Gol'}]}},
     'shotmap':{'shots':[
       {'eventType':'Goal','teamId':1,'min':12,'playerName':'Harry Kane'},
       {'eventType':'Goal','teamId':2,'min':24,'playerName':'Visitante 9'},
       {'eventType':'Goal','teamId':1,'min':36,'playerName':'Atacante 1'},
       {'eventType':'Goal','teamId':1,'min':43,'playerName':'Atacante 2'},
       {'eventType':'Goal','teamId':1,'min':63,'playerName':'Atacante 3'},
       {'eventType':'Goal','teamId':1,'min':84,'playerName':'Atacante 4'}]}}}
  goals=[e for e in fotmob_events(packet) if e['type']=='goal']
  self.assertEqual(len(goals),6)
  self.assertEqual(len([e for e in goals if e['side']=='home']),5)
  self.assertEqual(next(g for g in goals if g['minute']==24)['player'],'Visitante 9')
  self.assertEqual(next(g for g in goals if g['minute']==12)['player'],'Harry Kane')

 def test_assist_penalty_and_own_goal_are_source_dependent(self):
  packet={'general':{'homeTeam':{'id':1},'awayTeam':{'id':2}},'content':{
    'matchFacts':{'events':{'events':[{'type':'Goal','time':19,'isHome':True,
      'player':{'name':'9 da casa'},'assist':{'name':'10 da casa'},
      'goalDescription':'Penalty'}]}},
    'shotmap':{'shots':[{'eventType':'Goal','teamId':2,'min':54,
                          'playerName':'Zagueiro visitante','isOwnGoal':True}]}}}
  g=[e for e in fotmob_events(packet) if e['type']=='goal']
  self.assertEqual(len(g),2)
  self.assertEqual(g[0]['assist'],'10 da casa')
  self.assertTrue(g[0]['penalty'])
  self.assertTrue(g[1]['own_goal'])
  self.assertEqual(g[1]['side'],'home')

 def test_existing_goal_name_gets_enriched_not_doubled(self):
  old=[{'minute':23,'type':'goal','side':'away','text':'Autor não informado'}]
  new=[{'minute':23,'type':'goal','side':'away','text':'Jogador X',
        'player':'Jogador X','assist':'Jogador Y','source':'FotMob · shotmap'}]
  result=merge_verified_events(old,new)
  self.assertEqual(len(result),1)
  self.assertEqual(result[0]['player'],'Jogador X')
  self.assertEqual(result[0]['assist'],'Jogador Y')

 def test_lineups_preserve_rating_and_match_star(self):
  packet={'general':{'homeTeam':{'id':1},'awayTeam':{'id':2}},
   'content':{'matchFacts':{'playerOfTheMatch':{'teamId':1,'name':{'fullName':'Camisa 10'}}},
    'lineup':{'lineupType':'standard','homeTeam':{
      'starters':[{'name':'Camisa 10','shirtNumber':'10','id':101,
                   'performance':{'rating':9.1}}],
      'subs':[{'name':'Reserva','shirtNumber':'19'}]},
      'awayTeam':{'starters':[{'name':'Camisa 9','shirtNumber':'9',
        'performance':{'rating':8.3}}]}}}}
  lineups=fotmob_lineups(packet)
  self.assertEqual(lineups['home']['status'],'confirmed')
  self.assertEqual(lineups['home']['starters'][0]['rating'],9.1)
  stars=fotmob_match_stars(packet)
  self.assertEqual(stars['home']['player'],'Camisa 10')
  self.assertEqual(stars['away']['player'],'Camisa 9')

 def test_only_own_club_verified_season_leader(self):
  doc={'stats':{'players':[
    {'header':'Top scorer','participant':{'name':'9 clube','teamId':123,'value':17}},
    {'header':'Assists','participant':{'name':'10 clube','teamId':123,'value':9}},
    {'header':'Rating','participant':{'name':'Craque','teamId':123,'value':7.77}}]}}
  a=team_player_leaders(doc,123)
  self.assertEqual(a['goals']['name'],'9 clube')
  self.assertEqual(a['assists']['value'],9)
  self.assertEqual(a['rating']['name'],'Craque')
  self.assertEqual(team_player_leaders(doc,99),{})
  self.assertEqual(team_player_leaders({'stats':{'players':[
    {'header':'Top scorer','topThree':[{'name':'9 clube','teamId':123,'value':17}]}]}},123),{})

 def test_public_export_keeps_scorer_assist_and_historical_quotes_separate(self):
  row={'fixture':{'id':'fotmob-100','home':'Casa','away':'Fora','score':'2-1',
         'phase':'finished','start_timestamp':1792000000},
   'events':[{'minute':12,'type':'goal','side':'home','text':'Camisa 10',
              'player':'Camisa 10','assist':'Camisa 7','source':'FotMob · matchFacts'}],
   'match_stars':{'home':{'player':'Camisa 10','label':'Melhor em campo (FotMob)',
                            'source':'FotMob'}},
   'team_leaders':{'home':{'goals':{'name':'Camisa 10','value':5,
                        'source':'FotMob · atletas da equipe'}}},
   'lineups':{'home':{'status':'confirmed','starters':[{'name':'Camisa 10',
            'number':'10','rating':8.4}],'subs':[{'name':'Reserva','number':'14'}]}},
   'closing_odds':[{'market':'1x2','sel':'home','odd':1.9,'bookmaker':'Casa',
                    'type':'historical_closing'}]}
  p=public_row(row,'2026-10-17')
  self.assertEqual(p['events'][0]['player'],'Camisa 10')
  self.assertEqual(p['events'][0]['assist'],'Camisa 7')
  self.assertEqual(p['match_stars']['home']['player'],'Camisa 10')
  self.assertEqual(p['team_leaders']['home']['goals']['value'],5.)
  self.assertEqual(p['lineups']['home']['starters'][0]['rating'],8.4)
  self.assertEqual(p['odds'],[])
  self.assertEqual(p['closing_odds'][0]['odd'],1.9)

 def test_espn_scoring_plays_adds_named_goal(self):
  packet={'scoringPlays':[{'type':{'text':'Goal'},'clock':{'displayValue':'27:00'},
   'participants':[{'athlete':{'displayName':'Atacante ESPN'}}],
   'homeAway':'home','text':'Atacante ESPN goal'}]}
  result=extract_events(packet)
  self.assertEqual(result[0]['player'],'Atacante ESPN')
  self.assertEqual(result[0]['type'],'goal')

if __name__=='__main__':unittest.main()
