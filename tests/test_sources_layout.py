import unittest
from datetime import datetime,timezone
import multi_source as m
import web_export as w

class SourcesTests(unittest.TestCase):
    def test_football_data_match_is_extracted_with_timezone(self):
        row={'Date':'08/10/2026','Time':'20:00','HomeTeam':'Arsenal',
             'AwayTeam':'Chelsea','FTHG':'2','FTAG':'1','HS':'16','AS':'8',
             'HST':'6','AST':'3','B365H':'2.20','B365D':'3.20','B365A':'3.80'}
        fixture=m.football_data_fixture(row,'eng.1','Europe/London')
        self.assertEqual(fixture['score'],'2-1')
        self.assertEqual(fixture['source'],'Football-Data.co.uk')
        docs={'matches':{}}
        status={'added':0,'cross_verified':0,'stats_filled':0,
                'historical_odds':0,'conflicts':0}
        m.merge_football_data('2026-10-08','E0',row,docs,status)
        game=next(iter(docs['matches'].values()))
        self.assertEqual(game['stats']['home']['shots_on'],6.)
        self.assertEqual(game['stats']['away']['shots_total'],8.)
        self.assertEqual(game['closing_odds'][0]['type'],'historical_closing')
        self.assertNotIn('odds_quotes',game)
        self.assertEqual(status['historical_odds'],3)
        public=w.public_row(game,'2026-10-08')
        self.assertEqual(len(public['closing_odds']),3)
        self.assertEqual(len(public['odds']),0)

    def test_conflict_must_not_override_score_or_stats(self):
        row={'Date':'08/10/2026','Time':'20:00','HomeTeam':'Arsenal',
             'AwayTeam':'Chelsea','FTHG':'2','FTAG':'1','HS':'16'}
        docs={'matches':{'x':{'fixture':{'home':'Arsenal','away':'Chelsea',
            'league_code':'eng.1','phase':'finished','score':'1-0',
            'start_timestamp':int(datetime(2026,10,8,19,tzinfo=timezone.utc).timestamp())}}}}
        status={'added':0,'cross_verified':0,'stats_filled':0,
                'historical_odds':0,'conflicts':0}
        m.merge_football_data('2026-10-08','E0',row,docs,status)
        self.assertEqual(status['conflicts'],1)
        self.assertNotIn('stats',docs['matches']['x'])

    def test_historical_stats_never_merge_into_live_game(self):
        raw={'Date':'08/10/2026','Time':'20:00','HomeTeam':'Arsenal',
             'AwayTeam':'Chelsea','FTHG':'2','FTAG':'1','HST':'7'}
        live={'fixture':{'home':'Arsenal','away':'Chelsea',
              'league_code':'eng.1','phase':'live','score':'0-0',
              'start_timestamp':int(datetime(2026,10,8,19,tzinfo=timezone.utc).timestamp())}}
        docs={'matches':{'live':live}}
        status={'added':0,'cross_verified':0,'stats_filled':0,
                'historical_odds':0,'conflicts':0}
        m.merge_football_data('2026-10-08','E0',raw,docs,status)
        self.assertNotIn('stats', live)
        self.assertNotIn('closing_odds', live)
        self.assertEqual(status['cross_verified'],0)

    def test_historical_stats_never_merge_wrong_day(self):
        raw={'Date':'08/10/2026','Time':'20:00','HomeTeam':'Arsenal',
             'AwayTeam':'Chelsea','FTHG':'2','FTAG':'1','HST':'7'}
        old={'fixture':{'home':'Arsenal','away':'Chelsea','league_code':'eng.1',
             'phase':'finished','score':'2-1',
             'start_timestamp':int(datetime(2026,9,20,19,tzinfo=timezone.utc).timestamp())}}
        docs={'matches':{'old':old}}
        status={'added':0,'cross_verified':0,'stats_filled':0,
                'historical_odds':0,'conflicts':0}
        m.merge_football_data('2026-10-08','E0',raw,docs,status)
        self.assertEqual(status['cross_verified'],0)
        self.assertNotIn('stats', old)

    def test_openliga_ft_and_kickoff(self):
        event={'matchID':123,'matchDateTimeUTC':'2026-10-08T17:00:00Z',
            'matchIsFinished':True,'team1':{'teamName':'Dortmund'},'team2':{'teamName':'Bremen'},
            'matchResults':[{'resultTypeID':1,'pointsTeam1':1,'pointsTeam2':0},
                            {'resultTypeID':2,'pointsTeam1':2,'pointsTeam2':1}]}
        fixture=m.openliga_fixture(event)
        self.assertEqual(fixture['score'],'2-1')
        self.assertEqual(fixture['phase'],'finished')
        self.assertEqual(fixture['league_code'],'ger.1')

    def test_games_ordered_by_day_then_earliest_kickoff(self):
        games=[{'day':'2026-10-08','start_timestamp':200},
               {'day':'2026-10-09','start_timestamp':500},
               {'day':'2026-10-09','start_timestamp':100},
               {'day':'2026-10-09','start_timestamp':300}]
        result=w.sort_games(games)
        self.assertEqual([(v['day'],v['start_timestamp']) for v in result],
             [('2026-10-09',100),('2026-10-09',300),('2026-10-09',500),('2026-10-08',200)])

    def test_safe_merge_espn_fotmob_preserves_scouts_and_logos(self):
        base={'day':'2026-10-09','start_timestamp':100000,'source':'ESPN',
             'sources':['ESPN'],'home':'Instituto (Córdoba)','away':'Boca Juniors',
             'phase':'scheduled','score':'0-0','home_logo':'https://a.espncdn.com/i/teamlogos/soccer/500/2975.png',
             'away_logo':'','pressure':[],'stats':{'home':{'shots_on':3},'away':{}},
             'form':{'home':{'available':10},'away':{'available':10}},
             'odds':[],'events':[],'signals':[]}
        extra={'day':'2026-10-09','start_timestamp':100000,'source':'FotMob',
             'sources':['FotMob'],'home':'Instituto','away':'Boca Juniors',
             'phase':'scheduled','score':'0-0','home_logo':'',
             'away_logo':'https://images.fotmob.com/image_resources/logo/teamlogo/8467.png',
             'pressure':[{'m':5,'v':3}],'stats':{'home':{},'away':{'shots_on':4}},
             'form':{'home':{'available':0},'away':{'available':0}},
             'odds':[],'events':[],'signals':[]}
        result=w.merge_verified_duplicates([extra,base])
        self.assertEqual(len(result),1)
        merged=result[0]
        self.assertEqual(set(merged['sources']),{'FotMob','ESPN'})
        self.assertEqual(merged['stats']['home']['shots_on'],3)
        self.assertEqual(merged['stats']['away']['shots_on'],4)
        self.assertEqual(len(merged['pressure']),1)
        self.assertEqual(merged['form']['home']['available'],10)

    def test_do_not_merge_same_teams_at_different_kickoffs(self):
        games=[{'day':'2026-10-09','start_timestamp':100000,'source':'ESPN',
                 'home':'A','away':'B','phase':'scheduled','score':'0-0'},
               {'day':'2026-10-09','start_timestamp':105000,'source':'FotMob',
                 'home':'A','away':'B','phase':'scheduled','score':'0-0'}]
        self.assertEqual(len(w.merge_verified_duplicates(games)),2)

    def test_logos_require_trusted_espn_domain(self):
        good='https://a.espncdn.com/i/teamlogos/soccer/500/12.png'
        self.assertEqual(w.verified_logo(good),good)
        self.assertEqual(w.verified_logo('https://example.net/i/teamlogos/foo.png'),'')
        self.assertEqual(w.verified_logo('https://a.espncdn.com.evil.test/i/teamlogos/a.png'),'')
        self.assertEqual(w.verified_logo('https://images.fotmob.com/image_resources/logo/teamlogo/8455.png'),
                         'https://images.fotmob.com/image_resources/logo/teamlogo/8455.png')

if __name__=='__main__':unittest.main()
