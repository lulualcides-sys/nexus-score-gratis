"""Auditoria de probabilidades congeladas em mercados binarios; NAO libera EV.

Over/Under 2,5 e ambas marcam: resultado verificado e previsao gerada antes
do kickoff. Comparacao cronologica com frequencia passada da MESMA liga.
"""
import math
import re
from datetime import datetime
from collections import defaultdict

SCORE=re.compile(r'^(\d{1,2})-(\d{1,2})$')
MARKETS={'over_under_25':('over_2_5_pct','Mais de 2,5 gols'),
         'btts':('btts_yes_pct','Ambas marcam · Sim')}
MIN_HISTORY=25
MIN_REVIEW=200
RESULT_DELAY=3*3600

def frozen_binary_samples(archive):
    samples={name:[] for name in MARKETS}
    seen=set()
    for row in archive if isinstance(archive,list) else []:
        if not isinstance(row,dict) or row.get('phase')!='finished' or row.get('result_conflict') is True:continue
        result=SCORE.fullmatch(str(row.get('score') or ''))
        if not result:continue
        start=row.get('start_timestamp')
        if not isinstance(start,(int,float)) or isinstance(start,bool) or not math.isfinite(start):continue
        league=str(row.get('league') or 'Não informado')
        home=str(row.get('home') or '').casefold()
        away=str(row.get('away') or '').casefold()
        unique=(league,start,home,away) if home and away else (league,start,str(row.get('id') or ''))
        if unique in seen:continue
        variants=row.get('variants') or []
        if not isinstance(variants,list):continue
        snapshots=[v.get('pregame_baseline') for v in variants if isinstance(v,dict) and isinstance(v.get('pregame_baseline'),dict)]
        if not snapshots:continue
        # Mais antigo registrado primeiro, sem recalcular depois do jogo.
        baseline=min(snapshots,key=lambda v:str(v.get('captured_at') or ''))
        if baseline.get('model_status')!='experimental_uncalibrated':continue
        try:
            stamp=datetime.fromisoformat(str(baseline['captured_at']).replace('Z','+00:00'))
            if stamp.tzinfo is None:continue
            ts=stamp.timestamp()
        except (KeyError,ValueError,TypeError,OverflowError):continue
        if not 0<ts<start:continue
        prediction=baseline.get('forecast') or {}
        if not isinstance(prediction,dict):continue
        h,a=map(int,result.groups())
        truth={'over_under_25':int(h+a>2),'btts':int(h>0 and a>0)}
        captured=False
        for name,(key,label) in MARKETS.items():
            raw=prediction.get(key)
            if isinstance(raw,bool) or raw is None:continue
            try:prob=float(raw)/100
            except (ValueError,TypeError,OverflowError):continue
            if not math.isfinite(prob) or not 0<=prob<=1:continue
            samples[name].append({'league':league,'kickoff':start,
                                  'probability':prob,'actual':truth[name]})
            captured=True
        if captured:seen.add(unique)
    return samples

def audit_binary(samples):
    n=len(samples)
    if not n:return {'n':0,'brier':None,'log_loss':None,
                     'hit_rate_pct':None,'calibration_error_pct':None,
                     'chronological':{'evaluated':0,'brier':None,
                                      'baseline_brier':None,'beats_prior_baseline':None}}
    mean=lambda values:round(sum(values)/len(values),4) if values else None
    brier=lambda row:(row['probability']-row['actual'])**2
    losses=lambda row:-math.log(max(1e-12,min(1-1e-12,row['probability'] if row['actual'] else 1-row['probability'])))
    bins=[]
    for i in range(5):
        lo=i/5
        hi=(i+1)/5
        items=[r for r in samples if lo<=r['probability']<(hi if i<4 else 1.0000001)]
        if not items:continue
        p=sum(r['probability'] for r in items)/len(items)
        observed=sum(r['actual'] for r in items)/len(items)
        bins.append({'range_pct':[int(100*lo),int(100*hi)],'n':len(items),
                     'forecast_yes_pct':round(100*p,1),
                     'actual_yes_pct':round(100*observed,1),
                     'absolute_error_pct':round(100*abs(p-observed),1)})
    expected_error=sum(b['n']/n*b['absolute_error_pct'] for b in bins)
    groups={}
    for row in samples:
        groups.setdefault(row['kickoff'],[]).append(row)
    prior=defaultdict(list)
    pending=[]
    pairs=[]
    for kickoff in sorted(groups):
        cleared=[item for item in pending if item['kickoff']+RESULT_DELAY<=kickoff]
        pending=[item for item in pending if item['kickoff']+RESULT_DELAY>kickoff]
        for old in cleared:prior[old['league']].append(old['actual'])
        current=groups[kickoff]
        for row in current:
            past=prior[row['league']]
            if len(past)<MIN_HISTORY:continue
            # Laplace smoothing: somente jogos passados da mesma liga.
            reference=(sum(past)+1)/(len(past)+2)
            pairs.append((brier(row),(reference-row['actual'])**2))
        pending.extend(current)
    mb=mean([x[0] for x in pairs])
    ref=mean([x[1] for x in pairs])
    return {'n':n,'brier':mean([brier(x) for x in samples]),
            'log_loss':mean([losses(x) for x in samples]),
            'hit_rate_pct':round(100*sum((r['probability']>=.5)==bool(r['actual']) for r in samples)/n,1),
            'calibration_error_pct':round(expected_error,2),
            'calibration_bins':bins,
            'chronological':{'evaluated':len(pairs),'brier':mb,
                             'baseline_brier':ref,
                             'beats_prior_baseline':mb<ref if pairs else None,
                             'result_delay_hours':3,'minimum_prior_league_games':MIN_HISTORY}}

def binary_market_report(archive):
    grouped=frozen_binary_samples(archive)
    results=[]
    for name,(key,label) in MARKETS.items():
        rows=grouped[name]
        leagues=defaultdict(list)
        for r in rows:leagues[r['league']].append(r)
        results.append({'market':name,'label':label,**audit_binary(rows),
                        'by_league':[{'league':league,**audit_binary(items)}
                            for league,items in sorted(leagues.items(),key=lambda x:-len(x[1]))[:8]
                            if len(items)>=5],
                        'validated':False,'minimum_sample_for_review':MIN_REVIEW})
    return {'scope':'frozen_pregame_binary_markets_no_ev',
            'status':'experimental_uncalibrated',
            'markets':results,
            'note':'Somente probabilidades congeladas antes do jogo e placares finais sem conflito. Comparacao cronologica sem resultado antecipado; nao comprova EV nem rentabilidade.'}
