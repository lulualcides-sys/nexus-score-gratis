import unittest
from datetime import timedelta
from fotmob_form import team_id, match_from_fotmob, team_matches, recent_games, roster
from coletar import NOW

def when(days):
    return (NOW+timedelta(days=days)).isoformat()

class FotmobFormTests(unittest.TestCase):
    def match(self,ago=7):
        return {'id':55,'home':{'id':101,'name':'Casa','score':2},
                'away':{'id':202,'name':'Fora','score':1},
                'status':{'finished':True,'utcTime':when(-ago),'scoreStr':'2 - 1'}}

    def test_last_games_use_timestamp_prior_to_fixture(self):
        sample={'fixtures':{'allFixtures':{'fixtures':[self.match(7),self.match(-1)]}}}
        games=team_matches(sample,'101')
        self.assertEqual(len(games),1)
        self.assertEqual(games[0]['gf'],2)
        self.assertEqual(games[0]['ga'],1)
        self.assertEqual(len(recent_games(games,int(NOW.timestamp())-8*86400)),0)

    def test_away_side_goals_and_result(self):
        game=match_from_fotmob(self.match(),'202')
        self.assertEqual(game['gf'],1)
        self.assertEqual(game['ga'],2)
        self.assertEqual(game['result'],'D')
        self.assertEqual(game['venue'],'Fora')

    def test_overview_form_is_counted_only_when_completed(self):
        match={'home':{'id':101,'name':'Casa','isOurTeam':True},
            'away':{'id':202,'name':'Fora'},'resultString':'W',
            'score':'3 - 0','date':{'utcTime':when(-9)}}
        result=match_from_fotmob(match,'101')
        self.assertIsNotNone(result)
        self.assertEqual(result['gf'],3)
        self.assertEqual(result['result'],'V')

    def test_team_id_fallback_from_verified_cdn(self):
        fixture={'home_logo':'https://images.fotmob.com/image_resources/logo/teamlogo/421346.png'}
        self.assertEqual(team_id(fixture,'home'),'421346')

    def test_roster_names_public_not_lineup(self):
        doc={'squad':{'squad':[{'title':'Defenders','members':[
            {'name':'João','shirtNumber':'3'},{'name':'Bruno','shirtNumber':'5'}]}]}}
        groups=roster(doc)
        self.assertEqual(groups[0]['section'],'Defenders')
        self.assertEqual(groups[0]['players'][0]['name'],'João')

if __name__=='__main__':unittest.main()
