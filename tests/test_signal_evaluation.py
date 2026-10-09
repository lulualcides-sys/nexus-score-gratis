import unittest
from signal_evaluation import evaluate, minute_band

class SignalEvaluationTests(unittest.TestCase):
    def make(self, key, captured, result='gol_confirmado', rule='pressao_forte_10min',
             league='Serie A', home='Casa', away='Fora', side='home', minute=36, match=None):
        return {'id':key,'captured_at':captured,'match_id':match or key,'home':home,
                'away':away,'team':side,'league':league,'minute':minute,
                'icon':'🔥','rule':rule,'basis':'pressure_window',
                'outcomes':{'5':'sem_gol_confirmado','10':result,'15':'gol_confirmado'}}

    def test_groups_and_sample_evolution_from_verified_only(self):
        doc={'items':[
            self.make('a','2026-10-08T02:00:00Z','gol_confirmado',match='game-1',minute=33),
            self.make('b','2026-10-09T04:00:00Z','sem_gol_confirmado',match='game-2',minute=43),
            self.make('c','2026-10-09T05:00:00Z','pendente',match='game-3',side='away',minute=71),
            self.make('d','2026-10-09T06:00:00Z','indeterminado',match='game-4',minute=75),
            self.make('e','2026-10-09T06:10:00Z','janela_incompleta',match='game-5',minute=89),
        ]}
        result=evaluate(doc)
        self.assertEqual(result['summary']['observations'],5)
        self.assertEqual(result['summary']['settled'],2)
        self.assertEqual(result['summary']['hits'],1)
        self.assertEqual(result['summary']['misses'],1)
        self.assertEqual(result['summary']['rate_pct'],50.0)
        self.assertEqual(result['summary']['pending'],1)
        self.assertEqual(result['summary']['unknown'],1)
        self.assertEqual(result['summary']['incomplete'],1)
        self.assertEqual(result['summary']['matches'],5)
        self.assertEqual(result['money_status'],'unavailable_without_entry_odds_and_trade_results')
        self.assertNotIn('profit_u',str(result))
        self.assertEqual(len(result['by_signal']),1)
        self.assertEqual({r['label'] for r in result['by_team']},{'Casa','Fora'})
        self.assertEqual({r['label'] for r in result['by_league']},{'Serie A'})
        self.assertEqual(result['by_minute'][0]['label'],"33'")
        self.assertEqual({r['label'] for r in result['by_minute_band']},
                         {'31–45′','61–75′','76–90′'})
        # Registro 02:00Z ainda e dia anterior no Brasil.
        self.assertEqual(result['evolution'][0]['day'],'2026-10-07')
        self.assertEqual(result['evolution'][0]['cumulative_settled'],1)
        self.assertEqual(result['evolution'][-1]['cumulative_settled'],2)
        self.assertEqual(result['evolution'][-1]['cumulative_rate_pct'],50.0)

    def test_no_records_returns_null_rate_not_zero(self):
        x=evaluate({'items':[]})
        self.assertIsNone(x['summary']['rate_pct'])
        self.assertEqual(x['evolution'],[])

    def test_duplicates_invalid_outcomes_and_conflict_not_counted_as_success(self):
        hit=self.make('same','2026-10-09T20:00:00Z')
        conflicting={**self.make('b','2026-10-09T20:10:00Z'),'outcome_conflict':True}
        broken=self.make('c','not-a-date',minute=300)
        x=evaluate({'items':[hit,hit,conflicting,broken]})
        self.assertEqual(x['summary']['observations'],2)
        self.assertEqual(x['summary']['settled'],1)
        self.assertEqual(x['summary']['unknown'],1)
        self.assertEqual(len(x['evolution']),1)

    def test_all_horizons_independent_and_nontrading(self):
        item=self.make('a','2026-10-09T10:00:00Z')
        x=evaluate({'items':[item]})
        self.assertEqual(x['horizons']['5']['misses'],1)
        self.assertEqual(x['horizons']['10']['hits'],1)
        self.assertEqual(x['horizons']['15']['hits'],1)
        self.assertEqual(x['summary']['sample_quality'],'amostra_pequena')
        self.assertEqual(minute_band(120),'91+′')


if __name__=='__main__':unittest.main()
