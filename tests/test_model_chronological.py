import unittest
from datetime import datetime,timezone,timedelta
from model_validation import chronological_audit,validation_report

def make(p,observed,league='Premier League',start=None,identifier='i'):
    when=int((datetime(2026,10,10,tzinfo=timezone.utc)).timestamp()) if start is None else start
    return {'id':identifier,'league':league,'home':'Home'+identifier,'away':'Away'+identifier,
      'phase':'finished','score':('1-0' if observed==0 else '0-0' if observed==1 else '0-1'),
      'start_timestamp':when,
      'variants':[{'pregame_baseline':{
        'captured_at':datetime.fromtimestamp(when-1800,timezone.utc).isoformat(),
        'model_status':'experimental_uncalibrated',
        'forecast':{'one_x_two':dict(zip(('home','draw','away'),[x*100 for x in p]))}}}]}

class ChronologicalValidationTests(unittest.TestCase):
 def test_same_kickoff_does_not_leak_other_outcomes(self):
    rows=[{'kickoff':20,'league':'L','actual':0,'probabilities':[.5,.3,.2]} for _ in range(26)]
    self.assertEqual(chronological_audit(rows)['evaluated'],0)
    rows.append({'kickoff':4*3600,'league':'L','actual':1,'probabilities':[.5,.3,.2]})
    self.assertEqual(chronological_audit(rows)['evaluated'],1)
 def test_unsorted_input_independent_of_order(self):
    p=[.5,.3,.2]
    rows=[{'kickoff':n*4*3600,'league':'L','actual':n%3,'probabilities':p} for n in range(40)]
    a=chronological_audit(rows)
    b=chronological_audit(list(reversed(rows)))
    self.assertEqual(a['model_brier'],b['model_brier'])
    self.assertEqual(a['evaluated'],15)
    self.assertEqual(a['scope'],'chronological_sports_only_no_ev')
 def test_no_ev_unlock_and_duplicate_match_once(self):
    start=int(datetime(2026,10,10,tzinfo=timezone.utc).timestamp())
    one=make([.5,.3,.2],0,start=start,identifier='1')
    res=validation_report([one,one])
    self.assertFalse(res['validated'])
    self.assertEqual(res['eligible'],1)
    self.assertEqual(res['chronological']['evaluated'],0)
 def test_postkickoff_forecast_rejected(self):
    now=int(datetime(2026,10,10,tzinfo=timezone.utc).timestamp())
    g=make([.5,.3,.2],0,start=now,identifier='1')
    g['variants'][0]['pregame_baseline']['captured_at']=datetime.fromtimestamp(now+30,timezone.utc).isoformat()
    self.assertEqual(validation_report([g])['eligible'],0)

 def test_overlapping_fixtures_cannot_use_unfinished_results(self):
    p=[.5,.3,.2]
    history=[{'kickoff':0,'league':'L','actual':n%3,'probabilities':p} for n in range(26)]
    next_game={'kickoff':90*60,'league':'L','actual':0,'probabilities':p}
    self.assertEqual(chronological_audit(history+[next_game])['evaluated'],0)
    next_game['kickoff']=4*3600
    self.assertEqual(chronological_audit(history+[next_game])['evaluated'],1)
if __name__=='__main__':unittest.main()
