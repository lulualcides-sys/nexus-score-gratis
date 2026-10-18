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

    def test_exact_first_goal_timing_and_fixture_dedup(self):
        first=self.make('a','2026-10-09T10:00:00Z',match='m1',minute=35)
        first['outcomes']['40']='gol_confirmado'
        first['goals_after_alert']=[{'minute':47,'team':'home'},{'minute':51,'team':'away'}]
        duplicate=self.make('b','2026-10-09T10:01:00Z',match='m1',minute=36)
        duplicate['outcomes']['40']='gol_confirmado'
        duplicate['goals_after_alert']=[{'minute':47,'team':'home'}]
        unverified=self.make('c','2026-10-09T10:02:00Z',match='m2',minute=50)
        unverified['outcomes']['40']='gol_confirmado'
        unverified['goals_after_alert']=[]
        pending=self.make('d','2026-10-09T10:03:00Z',match='m3',minute=60)
        pending['outcomes']['40']='pendente'
        pending['goals_after_alert']=[{'minute':70,'team':'home'}]
        report=evaluate({'items':[first,duplicate,unverified,pending]})
        timing=report['goal_timing']
        self.assertEqual(timing['confirmed_goal_alerts'],3)
        self.assertEqual(timing['minute_known_alerts'],2)
        self.assertEqual(timing['minute_missing_alerts'],1)
        self.assertEqual(timing['unique_matches_with_timed_goals'],1)
        self.assertEqual(timing['median_delay_minutes'],11.5)
        self.assertEqual(timing['bins'][2]['alerts'],2)
        self.assertEqual(timing['first_alert_per_match']['matches'],3)
        self.assertEqual(timing['first_alert_per_match']['hits'],2)

    def test_rolling_90_days_first_alert_per_fixture(self):
        early=self.make('old','2026-05-01T10:00:00Z',match='historical')
        early['outcomes']['40']='gol_confirmado'
        initial=self.make('current-1','2026-10-09T10:00:00Z',match='fixtureA',minute=30)
        initial['outcomes']['40']='gol_confirmado'
        repeated=self.make('current-2','2026-10-09T10:05:00Z',match='fixtureA',minute=35)
        repeated['outcomes']['40']='sem_gol_confirmado'
        other=self.make('current-3','2026-10-09T11:05:00Z',match='fixtureB',minute=52)
        other['outcomes']['40']='sem_gol_confirmado'
        report=evaluate({'items':[early,initial,repeated,other]})
        self.assertEqual(report['history_window_days'],90)
        self.assertEqual(report['observations_older_than_90_days'],1)
        self.assertEqual(report['horizons']['40']['observations'],3)
        fixtures=report['views']['40']['first_match']
        self.assertEqual(fixtures['observations'],2)
        self.assertEqual(fixtures['hits'],1)
        self.assertEqual(fixtures['misses'],1)
        self.assertEqual(sum(v['observations'] for v in report['views']['40']['by_signal_first_match']),2)

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
