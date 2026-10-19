import unittest
from datetime import datetime, timezone, timedelta
from source_health import quality_report, freshness
NOW=int(datetime(2026,10,19,16,tzinfo=timezone.utc).timestamp())
def at(seconds):return datetime.fromtimestamp(NOW-seconds,timezone.utc).isoformat()
def live(match_id,age=70,scouts_age=70,pressure=True):
    return {'id':match_id,'phase':'live','observed_at':at(age),'stats_observed_at':at(scouts_age),
            'pressure_observed_at':at(scouts_age),
            'stats':{'home':{'shots_on':0},'away':{'shots_on':3}},
            'pressure':[{'m':32,'v':43}] if pressure else [],
            'live_odds_comparison':[]}
class SourceHealthTests(unittest.TestCase):
 def test_no_invention_of_missing_data(self):
    report=quality_report([],{}, {}, NOW)
    self.assertEqual(report['live_games_in_feed'],0)
    self.assertIsNone(report['pressure_pct_of_fresh_live'])
    self.assertEqual(report['collector_freshness'],'unknown')
    self.assertIn('not_ev',report['scope'])
 def test_stale_does_not_claim_recent_scouts(self):
    data=[live('a'),live('b',scouts_age=3600),
          live('c',age=3600),
          {'phase':'live','observed_at':at(60),'stats':{'home':{}}},
          {'phase':'scheduled','odds_comparison':[{'market':'btts'}]}]
    report=quality_report(data,{'updated_at':at(50),'details_collected':12,
                  'stats_detail_available':8,'momentum_status_counts':{'observed':2}},
                  {'updated_at':at(40),'errors':['SofaScore calendário HTTP 403'],
                  'odds_papi':{'status':'waiting_free_slot'},
                  'espn_fallback':{'quotes_added':3}},NOW)
    self.assertEqual(report['live_games_in_feed'],4)
    self.assertEqual(report['live_fresh'],3)
    self.assertEqual(report['fresh_live_with_recent_scouts'],1)
    self.assertEqual(report['fresh_live_with_recent_pressure'],1)
    self.assertEqual(report['collector_scout_yield_pct'],66.7)
    self.assertEqual(report['collector_pressure_yield_pct'],16.7)
    self.assertEqual(report['providers']['sofascore']['status'],'blocked_403')
    self.assertEqual(report['providers']['oddspapi']['status'],'waiting_free_slot')
    self.assertEqual(report['pregame_matches_with_price_comparison'],1)
 def test_future_and_timezone_naive_are_never_fresh(self):
    self.assertEqual(freshness('2026-10-19T16:00:00',NOW,20),'unknown')
    self.assertEqual(freshness(at(-300),NOW,20),'invalid_future')
 def test_never_treat_old_live_price_as_current_collection(self):
    old=live('a',age=3600)
    old['live_odds_comparison']=[{'market':'1x2'}]
    info=quality_report([old],{'updated_at':at(0)}, {},NOW)
    self.assertEqual(info['live_fresh'],0)
    self.assertEqual(info['live_matches_with_price_comparison'],1)
    self.assertEqual(info['fresh_live_with_recent_scouts'],0)
 def test_live_by_league_uses_only_recent_matches(self):
    good=live('one')
    good['league']='Brasileirão Série A'
    stale=live('two',scouts_age=5000)
    stale['league']='Brasileirão Série A'
    old=live('old',age=5000)
    old['league']='Liga B'
    empty={'phase':'live','league':'Liga B','observed_at':at(60),
           'stats':{'home':{},'away':{}},'pressure':[]}
    r=quality_report([good,stale,old,empty],{}, {}, NOW)
    by={item['league']:item for item in r['live_by_league']}
    self.assertEqual(by['Brasileirão Série A']['fresh_live_games'],2)
    self.assertEqual(by['Brasileirão Série A']['with_recent_scouts'],1)
    self.assertEqual(by['Brasileirão Série A']['with_recent_pressure'],1)
    self.assertEqual(by['Brasileirão Série A']['scouts_coverage_pct'],50)
    self.assertEqual(by['Liga B']['fresh_live_games'],1)
    self.assertEqual(by['Liga B']['with_recent_pressure'],0)
    self.assertEqual(sum(x['fresh_live_games'] for x in r['live_by_league']),r['live_fresh'])
if __name__=='__main__':unittest.main()
