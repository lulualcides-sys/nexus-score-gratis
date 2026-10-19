"""Relatorio esportivo de calibracao; nao libera EV+ automaticamente."""
import math
import re
from collections import defaultdict
from datetime import datetime
SCORE=re.compile(r'^(\d{1,2})-(\d{1,2})$')
MIN_SAMPLE=200

def validation_report(archive):
    scored=[]
    leagues=defaultdict(list)
    for row in archive if isinstance(archive,list) else []:
        if not isinstance(row,dict) or row.get('result_conflict') is True or row.get('phase')!='finished':continue
        match=SCORE.fullmatch(str(row.get('score') or ''))
        if not match:continue
        kickoff=row.get('start_timestamp')
        if not isinstance(kickoff,(float,int)):continue
        variants=row.get('variants') or []
        if not isinstance(variants,list) or not variants:continue
        baseline=sorted(variants,key=lambda v:str((v.get('pregame_baseline') or {}).get('captured_at') or ''))[0].get('pregame_baseline') or {}
        if baseline.get('model_status')!='experimental_uncalibrated':continue
        try:ts=datetime.fromisoformat(baseline['captured_at'].replace('Z','+00:00')).timestamp()
        except (KeyError,ValueError,TypeError):continue
        if ts>=kickoff:continue
        distribution=(baseline.get('forecast') or {}).get('one_x_two') or {}
        try:probs=[float(distribution[k])/100 for k in ('home','draw','away')]
        except (ValueError,TypeError,KeyError):continue
        if any(not math.isfinite(p) or not 0<p<1 for p in probs):continue
        if not .98<=sum(probs)<=1.02:continue
        total=sum(probs);probs=[p/total for p in probs]
        h,a=map(int,match.groups());actual=0 if h>a else 1 if h==a else 2
        forecast=max(range(3),key=lambda k:probs[k])
        item={'brier':sum((probs[i]-(1 if i==actual else 0))**2 for i in range(3)),
              'loss':-math.log(probs[actual]),'hit':int(actual==forecast),
              'confidence':probs[forecast]}
        item['actual']=actual
        scored.append(item);leagues[str(row.get('league') or 'Nao informado')].append(item)
    def describe(items):
        n=len(items)
        if not n:return {'n':0,'brier':None,'log_loss':None,
                          'top_pick_accuracy_pct':None,'uniform_baseline_brier':None,
                          'skill_vs_uniform':None}
        brier=sum(x['brier'] for x in items)/n
        uniform=2/3
        return {'n':n,'brier':round(brier,4),
                'log_loss':round(sum(x['loss'] for x in items)/n,4),
                'top_pick_accuracy_pct':round(100*sum(x['hit'] for x in items)/n,1),
                'uniform_baseline_brier':round(uniform,4),
                'skill_vs_uniform':round(1-brier/uniform,4)}
    bins=[]
    for low,high in [(0,.4),(.4,.5),(.5,.6),(.6,.7),(.7,1.01)]:
        items=[x for x in scored if low<=x['confidence']<high]
        if items:bins.append({'range_pct':[round(100*low),min(100,round(100*high))],
                              'n':len(items),
                              'average_confidence_pct':round(100*sum(x['confidence'] for x in items)/len(items),1),
                              'observed_hit_pct':round(100*sum(x['hit'] for x in items)/len(items),1)})
    return {'status':'experimental_uncalibrated','eligible':len(scored),'minimum_for_review':MIN_SAMPLE,
            'sample_sufficient_for_review':len(scored)>=MIN_SAMPLE,'overall':describe(scored),
            'by_league':[{'league':k,**describe(v)} for k,v in
                         sorted(leagues.items(),key=lambda x:-len(x[1]))[:20]],
            'confidence_bins':bins,'validated':False,
            'calibration_error_pct':round(sum(
                 len([x for x in scored if low<=x['confidence']<high])/len(scored)*
                 abs(sum(x['confidence'] for x in scored if low<=x['confidence']<high)/
                 len([x for x in scored if low<=x['confidence']<high])-
                 sum(x['hit'] for x in scored if low<=x['confidence']<high)/
                 len([x for x in scored if low<=x['confidence']<high]))
                 for low,high in [(0,.4),(.4,.5),(.5,.6),(.6,.7),(.7,1.01)]
                 if any(low<=x['confidence']<high for x in scored)
                )*100,2) if scored else None,
            'note':'Previsoes congeladas e placares verificados, sem recalibracao retroativa. EV+ segue indisponivel.'}
