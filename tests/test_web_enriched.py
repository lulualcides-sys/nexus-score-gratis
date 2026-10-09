import unittest
from web_export import historical_h2h,merge_verified_duplicates

class EnrichedHistoryTests(unittest.TestCase):
    def test_h2h_uses_only_previous_verified_matches(self):
        target=1800000000
        row={'fixture':{'home':'Fluminense','away':'Coritiba','home_id':'9863',
               'away_id':'9767','start_timestamp':target,'league':'bra.1'}}
        cache={'9863':{'games':[
            {'ts':target-86400*30,'opponent':'Coritiba','venue':'Casa','gf':2,'ga':1,'day':'2026-09-09','league':'Série A'},
            {'ts':target-86400*80,'opponent':'Coritiba','venue':'Fora','gf':1,'ga':1,'day':'2026-08-09','league':'Série A'},
            {'ts':target+86400,'opponent':'Coritiba','venue':'Casa','gf':5,'ga':0,'day':'2026-10-10','league':'Série A'},
            {'ts':target-86400,'opponent':'Palmeiras','venue':'Casa','gf':1,'ga':0,'day':'2026-10-08'}]}}
        matches=historical_h2h(row,cache)
        self.assertEqual(len(matches),2)
        self.assertEqual(matches[0]['score'],'2-1')
        self.assertEqual(matches[1]['home'],'Coritiba')
        self.assertEqual(matches[1]['score'],'1-1')


    def test_espn_schedule_cache_produces_real_h2h_without_duplicates(self):
        target=1800000000
        row={'fixture':{'id':'espn-arg.1-55','home':'Gimnasia LP',
                'away':'Atlético Tucumán','home_id':'113','away_id':'422',
                'league_code':'arg.1','start_timestamp':target}}
        old={'id':'espn-arg.1-18','home':'Gimnasia LP','away':'Atlético Tucumán',
             'home_id':'113','away_id':'422','league':'arg.1',
             'phase':'finished','score':'2-1','start_timestamp':target-900000}
        cache={'schedules':{'arg.1/113':{'games':[old]},
                            'arg.1/422':{'games':[old]}}}
        records=historical_h2h(row,{},cache)
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['score'],'2-1')
        self.assertEqual(records[0]['source'],'ESPN')

    def test_no_h2h_from_wrong_team_id_or_future_fixture(self):
        target=1800000000
        row={'fixture':{'id':'espn-arg.1-55','home':'Gimnasia LP',
                'away':'Atlético Tucumán','home_id':'113','away_id':'422',
                'league_code':'arg.1','start_timestamp':target}}
        wrong={'id':'espn-arg.1-20','home':'Gimnasia LP','away':'Atlético Tucumán',
               'home_id':'113','away_id':'999','phase':'finished',
               'score':'1-0','start_timestamp':target-500000}
        future={'id':'espn-arg.1-21','home':'Gimnasia LP','away':'Atlético Tucumán',
               'home_id':'113','away_id':'422','phase':'finished',
               'score':'1-0','start_timestamp':target+900000}
        self.assertEqual(historical_h2h(row,{}, {'schedules':{'arg.1/113':{
            'games':[wrong,future]}}}),[])

    def test_espn_and_fotmob_h2h_same_result_only_once(self):
        target=1800000000
        row={'fixture':{'id':'espn-arg.1-55','home':'Gimnasia LP',
                'away':'Atlético Tucumán','home_id':'113','away_id':'422',
                'league_code':'arg.1','start_timestamp':target},
             'h2h_verified':[{'home':'Atlético Tucumán','away':'Gimnasia LP',
                 'score':'0-1','at':target-900000,'source':'FotMob'}]}
        old={'id':'espn-arg.1-18','home':'Atlético Tucumán','away':'Gimnasia LP',
             'home_id':'422','away_id':'113','league':'arg.1',
             'phase':'finished','score':'0-1','start_timestamp':target-900000}
        records=historical_h2h(row,{}, {'schedules':{'arg.1/113':{'games':[old]}}})
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['source'],'FotMob')

    def test_fotmob_badge_preferred_when_merging_equivalent_matches(self):
        base={'day':'2026-10-08','source':'ESPN','sources':['ESPN'],
              'home':'Fluminense','away':'Coritiba','start_timestamp':1791505800,
              'phase':'finished','score':'4-0','stats':{'home':{},'away':{}},
              'home_logo':'https://a.espncdn.com/i/teamlogos/soccer/500/3445.png',
              'away_logo':'https://a.espncdn.com/i/teamlogos/soccer/500/3456.png'}
        extra={'day':'2026-10-08','source':'FotMob','sources':['FotMob'],
              'home':'Fluminense','away':'Coritiba','start_timestamp':1791505800,
              'phase':'finished','score':'4-0','stats':{'home':{},'away':{}},
              'home_logo':'https://images.fotmob.com/image_resources/logo/teamlogo/9863.png',
              'away_logo':'https://images.fotmob.com/image_resources/logo/teamlogo/9767.png'}
        merged=merge_verified_duplicates([base,extra])
        self.assertEqual(len(merged),1)
        self.assertIn('images.fotmob.com',merged[0]['home_logo'])
        self.assertIn('images.fotmob.com',merged[0]['away_logo'])

if __name__=='__main__':
    unittest.main()
