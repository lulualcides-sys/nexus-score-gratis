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
