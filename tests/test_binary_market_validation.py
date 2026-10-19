import unittest
from datetime import datetime,timezone
from binary_market_validation import binary_market_report,audit_binary,frozen_binary_samples

T=int(datetime(2026,10,10,12,tzinfo=timezone.utc).timestamp())
def game(i,score='2-1',over=65,btts=55,ts=None,phase='finished',league='Serie A'):
    kickoff=T+4*3600*i if ts is None else ts
    return {'id':str(i),'home':'Mandante '+str(i),'away':'Visitante '+str(i),
            'league':league,'start_timestamp':kickoff,'phase':phase,
            'score':score,'variants':[{'pregame_baseline':{
              'captured_at':datetime.fromtimestamp(kickoff-900,timezone.utc).isoformat(),
              'model_status':'experimental_uncalibrated',
              'forecast':{'one_x_two':{'home':50,'draw':30,'away':20},
                          'over_2_5_pct':over,'btts_yes_pct':btts}}}]}

class BinaryMarketValidation(unittest.TestCase):
 def test_frozen_prediction_and_real_result_only(self):
    out=binary_market_report([game(1)])
    a,b=out['markets']
    self.assertEqual((a['n'],b['n']),(1,1))
    self.assertEqual(a['hit_rate_pct'],100.0)
    self.assertEqual(b['hit_rate_pct'],100.0)
    self.assertFalse(a['validated'])
    self.assertEqual(a['chronological']['evaluated'],0)
 def test_no_duplicate_or_conflict_or_future_capture(self):
    g=game(1)
    conflict={**game(2),'result_conflict':True}
    late=game(3)
    late['variants'][0]['pregame_baseline']['captured_at']=datetime.fromtimestamp(
      late['start_timestamp']+1,timezone.utc).isoformat()
    row=frozen_binary_samples([g,g,conflict,late])
    self.assertEqual(len(row['btts']),1)
 def test_only_one_market_when_other_is_invalid(self):
    g=game(1,over=-5)
    report=binary_market_report([g])
    self.assertEqual([r['n'] for r in report['markets']],[0,1])
    self.assertEqual(report['markets'][0]['calibration_error_pct'],None)
 def test_chronological_never_uses_same_time_or_overlapping_score(self):
    samples=[{'league':'L','kickoff':T,'probability':.6,'actual':1}
             for i in range(30)]
    current={'league':'L','kickoff':T+3600,'probability':.8,'actual':1}
    self.assertEqual(audit_binary(samples+[current])['chronological']['evaluated'],0)
    current['kickoff']=T+4*3600
    self.assertEqual(audit_binary(samples+[current])['chronological']['evaluated'],1)
 def test_rolling_prior_same_league_and_input_order_irrelevant(self):
    games=[game(i,score=('2-0' if i%2 else '0-1'),over=65,btts=55) for i in range(45)]
    a=binary_market_report(games)['markets']
    b=binary_market_report(list(reversed(games)))['markets']
    self.assertEqual([x['chronological']['evaluated'] for x in a],[20,20])
    self.assertEqual(a[0]['chronological'],b[0]['chronological'])
    self.assertFalse(a[0]['validated'])
 def test_zero_and_one_probability_avoid_log_infinity(self):
    report=audit_binary([{'league':'L','kickoff':T,'probability':0.0,'actual':1},
                          {'league':'L','kickoff':T+50000,'probability':1.0,'actual':0}])
    self.assertTrue(report['log_loss']>1)
    self.assertEqual(report['brier'],1)
if __name__=='__main__':unittest.main()
