import unittest
from datetime import date,datetime,timezone
import json
import tempfile
from pathlib import Path
from nexus_intelligence_v6 import evaluate_v6,_markets,_wilson_lower,read_finished_archive

class NexusIntelligenceV6Tests(unittest.TestCase):
    def signal(self,i,day,fixture,hit=True,rule='pressao'):
        return {'id':str(i),'match_id':fixture,'captured_at':day+'T15:00:00Z',
                'minute':35,'rule':rule,'icon':'🔥','team':'home','home':'Casa',
                'away':'Fora','league':'Liga','outcomes':{'40':'gol_confirmado' if hit else 'sem_gol_confirmado'}}
    def game(self,key,score,phase='finished'):
        return {'id':key,'score':score,'phase':phase,
                'start_timestamp':int(datetime(2026,10,12,tzinfo=timezone.utc).timestamp())}
    def test_markets_verified_and_unverified_never_invent_odds(self):
        games=[self.game('a','1-1'),self.game('b','3-0'),self.game('c','0-0'),
               self.game('d','2-1'),self.game('e','2-2','live'),self.game('f','?')]
        x=_markets(games,'2026-07-01')
        self.assertEqual(x['distinct_verified_games'],4)
        d={m['market']:m for m in x['markets']}
        self.assertEqual(d['over_15']['hits'],3)
        self.assertEqual(d['over_25']['hits'],2)
        self.assertEqual(d['btts']['hits'],2)
        self.assertEqual(d['lay_goleada']['hits'],3)
        self.assertFalse(d['over_15']['has_real_entry_odds'])
    def test_conflicting_finished_scores_excluded(self):
        x=_markets([self.game('a','1-1'),self.game('a','2-1')],'2026-07-01')
        self.assertEqual(x['distinct_verified_games'],0)
        self.assertEqual(x['conflicting_games_excluded'],1)
    def test_first_alert_dedup_ranking_and_split(self):
        days=[f'2026-10-{d:02d}' for d in range(1,11)]
        raw=[]
        for i in range(30):
            day=days[i%len(days)]
            raw.append(self.signal(i,day,'m'+str(i),hit=i%3!=0))
        raw.append(self.signal(99,days[9],'m0',False))
        result=evaluate_v6({'items':raw},[],as_of=date(2026,10,18))
        self.assertEqual(result['distinct_matches'],30)
        group=result['signal_ranking'][0]
        self.assertEqual(group['settled'],30)
        self.assertIsNotNone(group['quality_index'])
        self.assertTrue(result['split_date'])
        self.assertEqual(result['model_status'],'descriptive_not_calibrated')
        self.assertNotIn('profit',str(result))
    def test_holdout_outcomes_cannot_change_training_rank_score(self):
        raw=[]
        for i in range(30):
            day=f'2026-10-{(i%10)+1:02d}'
            raw.append(self.signal(i,day,'fixture'+str(i),hit=i%2==0))
        before=evaluate_v6({'items':raw},[],as_of=date(2026,10,18))
        score_before=before['signal_ranking'][0]['quality_index']
        cutoff=before['split_date']
        altered=[{**r,'outcomes':{'40':'gol_confirmado'}}
                 if r['captured_at'][:10]>=cutoff else r for r in raw]
        after=evaluate_v6({'items':altered},[],as_of=date(2026,10,18))
        self.assertEqual(score_before,after['signal_ranking'][0]['quality_index'])
        self.assertEqual(after['signal_ranking'][0]['quality_basis'],'development_only')

    def test_90day_archived_market_history_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist=Path(tmp)
            source=hist/'2026-10-09.json'
            doc={'matches':{'old_a':{'fixture':self.game('a','1-1')},
                            'old_b':{'fixture':self.game('b','3-0')},
                            'ongoing':{'fixture':self.game('c','2-2','live')}}}
            original=json.dumps(doc)
            source.write_text(original,encoding='utf-8')
            (hist/'2026-01-01.json').write_text('{"matches":{}}',encoding='utf-8')
            archive=read_finished_archive(hist,as_of=date(2026,10,18))
            self.assertEqual(archive['files_seen'],1)
            self.assertEqual(archive['files_read'],1)
            report=evaluate_v6({'items':[]},[],as_of=date(2026,10,18),historical_archive=archive)
            self.assertEqual(report['markets']['distinct_verified_games'],2)
            self.assertEqual(report['markets']['coverage']['files_read'],1)
            self.assertEqual(source.read_text(encoding='utf-8'),original)
    def test_horizon_comparison_independent_first_match(self):
        signal=self.signal(1,'2026-10-01','match-A')
        signal['outcomes'].update({'10':'sem_gol_confirmado','20':'gol_confirmado',
                                   '30':'gol_confirmado','40':'gol_confirmado'})
        repeated=self.signal(2,'2026-10-01','match-A')
        repeated['minute']=43
        report=evaluate_v6({'items':[signal,repeated]},[],as_of=date(2026,10,18))
        self.assertEqual([v['minutes'] for v in report['horizon_comparison']],[10,20,30,40])
        self.assertEqual(report['horizon_comparison'][0]['misses'],1)
        self.assertEqual(report['horizon_comparison'][-1]['hits'],1)
        self.assertEqual(report['distinct_matches'],1)
    def test_context_measured_not_invented(self):
        signal=self.signal(1,'2026-10-01','match-A')
        signal['pressure10']={'score':70,'level':'FORTE'}
        signal['shots_on']=5
        report=evaluate_v6({'items':[signal]},[],as_of=date(2026,10,18))
        item=report['signal_ranking'][0]
        self.assertEqual(item['median_pressure10'],70.0)
        self.assertEqual(item['median_shots_on'],5.0)
        self.assertIsNone(item['median_big_chances'])

    def test_low_sample_does_not_claim_score(self):
        report=evaluate_v6({'items':[self.signal(1,'2026-10-01','a')]},[],as_of=date(2026,10,18))
        self.assertIsNone(report['signal_ranking'][0]['quality_index'])
        self.assertIsNone(report['split_date'])
        self.assertIsNone(_wilson_lower(0,0))
    def test_history_preserved_but_90day_query_filters(self):
        old=self.signal(1,'2026-01-01','old')
        new=self.signal(2,'2026-10-10','recent')
        allitems=[old,new]
        r=evaluate_v6({'items':allitems},[],as_of=date(2026,10,18))
        self.assertEqual(len(allitems),2)
        self.assertEqual(r['distinct_matches'],1)
        self.assertTrue(r['original_alerts_untouched'])
if __name__=='__main__':unittest.main()
