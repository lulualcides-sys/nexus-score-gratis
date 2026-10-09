import unittest

from coletar import fotmob_events, fotmob_lineups

class FotmobEventTests(unittest.TestCase):
    def test_goals_cards_and_shots_are_actual_match_events(self):
        detail={
          'general':{'homeTeam':{'id':101},'awayTeam':{'id':202}},
          'content':{
            'matchFacts':{'events':{'events':[
                {'type':'Goal','time':23,'isHome':True,'nameStr':'Gol mandante'},
                {'type':'YellowCard','time':30,'isHome':False,'nameStr':'Amarelo fora'},
                {'type':'MissedPenalty','time':60,'isHome':False,'nameStr':'Pênalti perdido'}]}},
            'shotmap':{'shots':[
                {'eventType':'AttemptSaved','isOnTarget':True,'teamId':101,'min':15,'playerName':'Chute alvo'},
                {'eventType':'Miss','isOnTarget':False,'isBlocked':False,'teamId':202,'min':16,'playerName':'Chute fora'},
                {'eventType':'AttemptSaved','isBlocked':True,'isOnTarget':False,'teamId':202,'min':17},
                {'eventType':'Goal','isOnTarget':True,'teamId':101,'min':23}]}}}
        events=fotmob_events(detail)
        self.assertEqual({e['type'] for e in events},
                         {'goal','yellow_card','penalty_missed','shot_on','shot_off'})
        self.assertEqual(next(e for e in events if e['type']=='shot_on')['side'],'home')
        self.assertEqual(next(e for e in events if e['type']=='shot_off')['side'],'away')
        self.assertEqual(len(events),5)

    def test_big_chance_missed_has_only_verified_away_side(self):
        detail={'general':{'homeTeam':{'id':11},'awayTeam':{'id':22}},
          'content':{'shotmap':{'shots':[
            {'eventType':'Miss','isOnTarget':False,'teamId':22,'min':32,
             'isBigChance':True,'playerName':'Chance visitante'},
            {'eventType':'Miss','isOnTarget':False,'teamId':22,'min':33,
             'playerName':'Chute comum'},
            {'eventType':'Miss','isOnTarget':False,'teamId':99,'min':34,
             'isBigChance':True,'playerName':'Equipe desconhecida'}]}}}
        result=fotmob_events(detail)
        self.assertEqual([(e['minute'],e['type'],e['side']) for e in result],
                         [(32,'big_chance_missed','away'),(33,'shot_off','away')])

    def test_no_data_never_generates_fake_events(self):
        self.assertEqual(fotmob_events({'content':{}}),[])
        self.assertEqual(fotmob_events({'content':{'shotmap':{'shots':[
            {'eventType':'Blocked','isOnTarget':False,'isBlocked':True,'min':20}
        ]}}}),[])

    def test_lineups_use_actual_players_only(self):
        packet={'content':{'lineup':{'lineupType':'expected',
            'homeTeam':{'formation':'4-3-3',
                        'starters':[{'name':'A','shirtNumber':'9'}],
                        'subs':[{'name':'B','shirtNumber':'22'}]},
            'awayTeam':{'formation':'5-4-1','starters':[],'subs':[]}}}}
        result=fotmob_lineups(packet)
        self.assertEqual(result['home']['formation'],'4-3-3')
        self.assertEqual(result['home']['starters'][0]['name'],'A')
        self.assertEqual(result['home']['subs'][0]['number'],'22')
        self.assertNotIn('away',result)
        self.assertEqual(result['home']['lineup_type'],'expected')

if __name__=='__main__':unittest.main()
