"""Relatorio esportivo de calibracao; nao libera EV+ automaticamente."""
import math
import re
from collections import defaultdict
from datetime import datetime
SCORE=re.compile(r'^(\d{1,2})-(\d{1,2})$')
MIN_SAMPLE=200


def chronological_audit(scored,minimum_prior=25):
    """Baseline de mercado neutro calculada SOMENTE de jogos encerrados anteriormente.

    Folds do mesmo horario nao veem o resultado um do outro.
    Nao valida o modelo, nao inventa odds, nao calcula EV.
    """
    by_kickoff={}
    for row in scored:
        if not isinstance(row.get('kickoff'),(int,float)):continue
        by_kickoff.setdefault(row['kickoff'],[]).append(row)
    histories={}
    pending=[]
    checked=[]
    for kickoff in sorted(by_kickoff):
        # Resultado so integra a referencia depois de um periodo
        # conservador de 3h apos o inicio (nao vazar jogos sobrepostos).
        finished=[x for x in pending if x['kickoff']+3*3600<=kickoff]
        pending=[x for x in pending if x['kickoff']+3*3600>kickoff]
        for past in finished:
            histories.setdefault(past['league'],[]).append(past['actual'])
        group=by_kickoff[kickoff]
        for item in group:
            league=item['league']
            previous=histories.get(league,[])
            if len(previous)<minimum_prior:continue
            # Laplace/Dirichlet: class count +1, protege contra p=0.
            frequencies=[(previous.count(side)+1)/(len(previous)+3) for side in range(3)]
            actual=item['actual']
            pred=item['probabilities']
            brier=sum((pred[i]-(1 if i==actual else 0))**2 for i in range(3))
            reference=sum((frequencies[i]-(1 if i==actual else 0))**2 for i in range(3))
            checked.append({'league':league,'brier':brier,'reference':reference,
                            'model_logloss':-math.log(pred[actual]),
                            'reference_logloss':-math.log(frequencies[actual])})
        # Sem acesso ao resultado antes de tempo plausivel do apito final.
        pending.extend(group)
    n=len(checked)
    mean=lambda key:round(sum(x[key] for x in checked)/n,4) if n else None
    return {'status':'observed_comparison' if n else 'insufficient_prior_games',
            'evaluated':n,'minimum_prior_league_results':minimum_prior,'conservative_result_delay_hours':3,
            'model_brier':mean('brier'),
            'prior_results_baseline_brier':mean('reference'),
            'model_log_loss':mean('model_logloss'),
            'prior_results_baseline_log_loss':mean('reference_logloss'),
            'beats_prior_results_baseline':(mean('brier')<mean('reference')) if n else None,
            'scope':'chronological_sports_only_no_ev',
            'note':'Comparacao cronologica, usando apenas placares anteriores de cada liga. Nao valida apostas nem EV+.'}

from binary_market_validation import binary_market_report

def validation_report(archive):
    scored=[]
    leagues=defaultdict(list)
    seen=set()
    for row in archive if isinstance(archive,list) else []:
        if not isinstance(row,dict) or row.get('result_conflict') is True or row.get('phase')!='finished':continue
        match=SCORE.fullmatch(str(row.get('score') or ''))
        if not match:continue
        kickoff=row.get('start_timestamp')
        if not isinstance(kickoff,(float,int)):continue
        league=str(row.get('league') or 'Nao informado')
        # Dados esportivos repetidos nao contam duas vezes no backtest.
        home=str(row.get('home') or '')
        away=str(row.get('away') or '')
        unique=(league,kickoff,home.casefold(),away.casefold()) if home and away else (league,kickoff,str(row.get('id')))
        if unique in seen:continue
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
        item['kickoff']=kickoff
        item['league']=league
        item['probabilities']=probs
        seen.add(unique)
        scored.append(item);leagues[league].append(item)
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
            'binary_markets':binary_market_report(archive),
            'chronological':chronological_audit(scored),
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
