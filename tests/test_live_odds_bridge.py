import unittest
from odds_fixture_bridge import bridge_pregame_prices, team_key


def match(ident, home, away, stamp=1791579600, phase='live', odds=None):
    return {'id':ident,'day':'2026-10-09','start_timestamp':stamp,
            'home':home,'away':away,'phase':phase,'odds':odds or []}


def prices(stamp="2026-10-09T20:34:51+00:00",house="DraftKings"):
    return [{'sel':side,'odd':price,'source':'ESPN','bookmaker':house,'at':stamp}
            for side,price in [('home',1.91),('draw',3.4),('away',4.1)]]


class BridgeLivePricesTest(unittest.TestCase):
    def test_alias_only_for_clear_club_identity(self):
        self.assertEqual(team_key('Gimnasia LP'), team_key('Gimnasia La Plata'))
        self.assertNotEqual(team_key('Gimnasia Mendoza'), team_key('Gimnasia La Plata'))
        self.assertEqual(team_key('Atlético Tucumán'),team_key('Atletico Tucuman'))

    def test_screenshot_game_gets_verified_pregame_quotes(self):
        live=match('fotmob-1000019569','Gimnasia LP','Atlético Tucumán')
        espn=match('espn-arg.1-401841609','Gimnasia La Plata','Atlético Tucumán',odds=prices())
        data=[live,espn]
        result=bridge_pregame_prices(data)
        self.assertEqual(result['linked'],1)
        self.assertEqual([x['odd'] for x in live['odds']],[1.91,3.4,4.1])
        self.assertEqual(live['odds_scope'],'pregame')
        self.assertEqual(live['odds_source_match'],'espn-arg.1-401841609')
        self.assertEqual(live['phase'],'live')
        self.assertEqual(espn['odds'],prices())

    def test_requires_same_home_away_and_kickoff(self):
        for away,minutes in [('Independiente',0),('Atlético Tucumán',20)]:
            live=match('fotmob-1','Gimnasia LP','Atlético Tucumán')
            other=match('espn-1','Gimnasia La Plata',away,stamp=1791579600+60*minutes,odds=prices())
            self.assertEqual(bridge_pregame_prices([live,other])['linked'],0)
            self.assertEqual(live['odds'],[])

    def test_rejects_ambiguous_donors_and_late_odds(self):
        original=match('fotmob-1','Gimnasia LP','Atlético Tucumán')
        a=match('espn-1','Gimnasia La Plata','Atlético Tucumán',odds=prices())
        b=match('espn-2','Gimnasia La Plata','Atlético Tucumán',odds=prices())
        self.assertEqual(bridge_pregame_prices([original,a,b])['linked'],0)
        later=match('espn-3','Gimnasia La Plata','Atlético Tucumán',
                    odds=prices('2026-10-09T22:34:51+00:00'))
        self.assertEqual(bridge_pregame_prices([original,later])['linked'],0)

    def test_does_not_override_independent_odds(self):
        own=[{'sel': 'home','odd':2.2,'source':'SofaScore','bookmaker':'A',
              'at':'2026-10-09T20:00:00+00:00'}]
        row=match('fotmob-1','Gimnasia LP','Atlético Tucumán',odds=own.copy())
        other=match('espn-1','Gimnasia La Plata','Atlético Tucumán',odds=prices())
        bridge_pregame_prices([row,other])
        self.assertEqual(row['odds'],own)

    def test_never_substitutes_historical_closing_odds(self):
        live=match('fotmob-1','Gimnasia LP','Atlético Tucumán')
        other=match('espn-1','Gimnasia La Plata','Atlético Tucumán')
        other['closing_odds']=prices()
        self.assertEqual(bridge_pregame_prices([live,other])['linked'],0)


    def test_rejects_three_odds_observed_at_different_moments(self):
        game=match('fotmob-1','Gimnasia LP','Atlético Tucumán')
        mixed=prices()
        mixed[1]['at']='2026-10-09T20:14:51+00:00'
        donor=match('espn-1','Gimnasia La Plata','Atlético Tucumán',odds=mixed)
        self.assertEqual(bridge_pregame_prices([game,donor])['linked'],0)
        self.assertEqual(game['odds'],[])


if __name__=='__main__':
    unittest.main()
