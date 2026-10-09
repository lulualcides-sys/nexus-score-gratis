import unittest
from experiments.multisource_trial import choose_fixtures, compare_football_data


class MultiSourceTrialTests(unittest.TestCase):
    def setUp(self):
        self.rows=[
         {'fixture':{'id':f'test-{n}','home':f'Home {n}','away':f'Away {n}',
                     'league_code':'eng.1','score':'2-1','phase':'finished',
                     'start_timestamp':1791529200},
          'stats':{'home':{'shots_on':3},'away':{}}}
         for n in range(15)]

    def test_choose_is_repeatable_limited_without_mutation(self):
        found=choose_fixtures(self.rows,limit=10,seed=11)
        self.assertEqual(len(found),10)
        self.assertEqual(found,choose_fixtures(self.rows,limit=10,seed=11))
        self.assertEqual(len(self.rows),15)
        self.assertEqual(len({x['fixture']['id'] for x in found}),10)

    def test_cross_verification_rejects_name_collision(self):
        fixture={'home':'Arsenal','away':'Chelsea','score':'2-0','phase':'finished'}
        wrong={'HomeTeam':'Arsenal','AwayTeam':'Everton','FTHG':'2','FTAG':'0',
               'Date':'09/10/2026','HST':'6','AST':'3'}
        self.assertEqual(compare_football_data(fixture,[wrong])['status'],'unmatched')

    def test_conflicting_score_is_not_verified(self):
        fixture={'home':'Arsenal','away':'Chelsea','score':'1-0','phase':'finished'}
        raw={'HomeTeam':'Arsenal','AwayTeam':'Chelsea','FTHG':'2','FTAG':'0',
             'Date':'09/10/2026','HST':'5','AST':'1'}
        outcome=compare_football_data(fixture,[raw])
        self.assertEqual(outcome['status'],'conflict')
        self.assertEqual(outcome['stats_available'],0)

    def test_confirmed_same_score_counts_retrieved_scouts(self):
        fixture={'home':'Arsenal','away':'Chelsea','score':'2-0','phase':'finished'}
        raw={'HomeTeam':'Arsenal','AwayTeam':'Chelsea','FTHG':'2','FTAG':'0',
             'Date':'09/10/2026','HST':'5','AST':'1','HS':'10'}
        outcome=compare_football_data(fixture,[raw])
        self.assertEqual(outcome['status'],'cross_verified')
        self.assertEqual(outcome['stats_available'],3)


if __name__=='__main__':
    unittest.main()
