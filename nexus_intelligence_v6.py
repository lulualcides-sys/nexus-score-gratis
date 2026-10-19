"""NEXUS 6.0 — evidências descritivas; nunca altera histórico ou cria odds.
Modelo histórico: um primeiro alerta por partida, 40 minutos e validação cronológica.
Resultados de mercados usam somente partidas finalizadas com placar íntegro.
"""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import math
import re
import json
from pathlib import Path
from statistics import median
from signal_evaluation import _rollup, _goal_timing
from signal_evaluation import _entries, _earliest_per_match

MARKETS=(
    ('over_15','Over 1.5 FT'),
    ('over_25','Over 2.5 FT'),
    ('btts','Ambas marcam'),
    ('lay_goleada','Lay goleada (contra margem 3+)'),
)

def _wilson_lower(hits,n):
    if not n:return None
    z=1.96
    p=hits/n
    den=1+z*z/n
    return round(max(0,100*(p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/den),1)

def _rank(rows,field,split_day):
    grouped=defaultdict(list)
    for entry in rows:
        grouped[entry[field]].append(entry)
    results=[]
    for label,group in grouped.items():
        context=group
        def midpoint(field):
            values=[e.get('context',{}).get(field) for e in context]
            clean=sorted(float(v) for v in values if isinstance(v,(int,float)) and math.isfinite(v))
            return round(median(clean),1) if clean else None
        basis={}
        for e in group:
            b=e.get('context',{}).get('basis')
            if b:basis[b]=basis.get(b,0)+1
        settled=[r for r in group if r['outcomes']['40'] in ('gol_confirmado','sem_gol_confirmado')]
        n=len(settled)
        wins=sum(r['outcomes']['40']=='gol_confirmado' for r in settled)
        after=[r for r in settled if split_day and r['day']>=split_day]
        before=[r for r in settled if split_day and r['day']<split_day]
        # A amostra posterior NÃO influencia o índice: evita vazamento do teste.
        development=before if split_day else settled
        dn=len(development)
        dw=sum(r['outcomes']['40']=='gol_confirmado' for r in development)
        value=_wilson_lower(dw,dn)
        # Índice DESCRITIVO, jamais probabilidade, odd ou EV calibrado.
        quality=round(value*0.75+min(dn,100)*0.25,1) if dn>=20 else None
        results.append({'label':label,'matches':len({r['match_id'] for r in group}),
                        'observations':len(group),'settled':n,'hits':wins,'misses':n-wins,
                        'median_pressure10':midpoint('pressure10_score'),
                        'median_shots_on':midpoint('shots_on'),
                        'median_big_chances':midpoint('big_chances'),
                        'signal_bases':basis,
                        'minute_range':f"{min(e['minute'] for e in group)}–{max(e['minute'] for e in group)}" if group else None,
                        'rate_pct':round(100*wins/n,1) if n else None,
                        'wilson_lower_pct':value,'quality_index':quality,
                        'state':'amostra_minima' if dn>=20 else 'amostra_insuficiente',
                        'quality_basis':'development_only' if split_day else 'all_observations_no_holdout',
                        'train_settled':len(before),'test_settled':len(after),
                        'train_rate_pct':round(100*sum(x['outcomes']['40']=='gol_confirmado' for x in before)/len(before),1) if before else None,
                        'test_rate_pct':round(100*sum(x['outcomes']['40']=='gol_confirmado' for x in after)/len(after),1) if after else None,
                        'test_usable':len(after)>=10 and len(before)>=20})
    return sorted(results,key=lambda x:(x['quality_index'] is None,
                                         -(x['quality_index'] or 0),-x['settled'],x['label']))[:80]

def read_finished_archive(history_dir,as_of=None):
    """Read-only archive, no files rewritten or records deleted; last 90 calendar days."""
    today=as_of.date() if isinstance(as_of,datetime) else as_of
    if today is None:today=datetime.now(timezone.utc).date()
    cutoff=(today-timedelta(days=89)).isoformat()
    rows=[]
    files_seen=files_read=errors=0
    for path in sorted(Path(history_dir).glob('20??-??-??.json')):
        if not cutoff<=path.stem<=today.isoformat():continue
        files_seen+=1
        try:
            doc=json.loads(path.read_text(encoding='utf-8'))
            collection=doc.get('matches') if isinstance(doc,dict) else {}
            if not isinstance(collection,dict):errors+=1;continue
            files_read+=1
            for key,item in collection.items():
                if not isinstance(item,dict):continue
                f=item.get('fixture')
                if not isinstance(f,dict):continue
                # fixture date, when valid, remains authoritative to avoid UTC day mismatch.
                row={'id':str(f.get('id') or key),'score':f.get('score'),
                     'phase':f.get('phase'),'start_timestamp':f.get('start_timestamp')}
                rows.append(row)
        except (OSError,ValueError,TypeError,UnicodeError):
            errors+=1
    return {'games':rows,'files_seen':files_seen,'files_read':files_read,
            'files_failed':errors,'from_day':cutoff,'to_day':today.isoformat(),
            'status':'partial' if errors else 'read_only_complete_available_files'}


def _markets(games,cutoff):
    verified={}
    conflicted=set()
    for row in games if isinstance(games,list) else []:
        if not isinstance(row,dict) or row.get('phase')!='finished':continue
        fid=str(row.get('id') or '')
        stamp=row.get('start_timestamp')
        if not fid or not isinstance(stamp,(int,float)) or stamp<=0:continue
        try:day=datetime.fromtimestamp(stamp,timezone.utc).date().isoformat()
        except (OverflowError,OSError,ValueError):continue
        if day<cutoff:continue
        text=str(row.get('score') or '')
        match=re.fullmatch(r'\s*(\d{1,2})\s*[-–:]\s*(\d{1,2})\s*',text)
        if not match:continue
        hg,ag=map(int,match.groups())
        if fid in verified and verified[fid][:2]!=(hg,ag):conflicted.add(fid)
        else:verified[fid]=(hg,ag,day)
    for fid in conflicted:verified.pop(fid,None)
    settled_days=sorted({stamp for _,_,stamp in verified.values()})
    split=settled_days[max(1,int(len(settled_days)*0.7))] if len(settled_days)>=4 else None
    out=[]
    for key,label in MARKETS:
        hits=0
        training_hits=training_n=test_hits=test_n=0
        for hg,ag,day in verified.values():
            value={'over_15':hg+ag>=2,'over_25':hg+ag>=3,
                   'btts':hg>0 and ag>0,'lay_goleada':abs(hg-ag)<3}[key]
            hits+=int(value)
            if split and day>=split:
                test_n+=1
                test_hits+=int(value)
            elif split:
                training_n+=1
                training_hits+=int(value)
        n=len(verified)
        out.append({'market':key,'label':label,'finished_verified':n,'hits':hits,'misses':n-hits,
                    'rate_pct':round(100*hits/n,1) if n else None,
                    'train_settled':training_n,'train_hits':training_hits,
                    'train_rate_pct':round(100*training_hits/training_n,1) if training_n else None,
                    'test_settled':test_n,'test_hits':test_hits,
                    'test_rate_pct':round(100*test_hits/test_n,1) if test_n else None,
                    'split_date':split,'test_usable':test_n>=10 and training_n>=20,
                    'has_real_entry_odds':False,'money_status':'unavailable_without_verified_prices'})
    return {'scope':'finished_matches_in_current_snapshot_only','distinct_verified_games':len(verified),
            'conflicting_games_excluded':len(conflicted),
            'split_date':split,'days_with_verified_results':len(settled_days),
            'prices':'not_assumed','markets':out,
            'note':'Mercados descritivos por placar final. Sem odds de entrada: não são operações liquidadas nem P/L.'}

def evaluate_v6(journal,games,as_of=None,historical_archive=None):
    today=as_of.date() if isinstance(as_of,datetime) else as_of
    if today is None:today=datetime.now(timezone.utc).date()
    cutoff=(today-timedelta(days=89)).isoformat()
    entries=[e for e in _entries(journal if isinstance(journal,dict) else {}) if cutoff<=e['day']<=today.isoformat()]
    first=_earliest_per_match(entries)
    days=sorted({x['day'] for x in first})
    # Split por DIAS, nunca embaralha registros de um mesmo dia entre treino e teste.
    cutoff_test=days[max(1,int(len(days)*0.7))] if len(days)>=4 else None
    rank_signals=_rank(first,'signal',cutoff_test)
    rank_leagues=_rank(first,'league',cutoff_test)
    horizon_comparison=[]
    for minutes in (10,20,30,40):
        summary=_rollup(first,str(minutes))
        horizon_comparison.append({'minutes':minutes,**summary})
    timed=_goal_timing(first)
    archive=historical_archive if isinstance(historical_archive,dict) else None
    market_rows=(archive.get('games') or []) if archive else games
    market_report=_markets(market_rows,cutoff)
    if archive:
        market_report['scope']='finished_matches_in_90day_archive_files'
        market_report['coverage']={key:archive.get(key) for key in
            ('files_seen','files_read','files_failed','from_day','to_day','status')}
    return {'schema':2,'name':'NEXUS 6.1','window_minutes':40,'history_days':90,
            'horizon_comparison':horizon_comparison,
            'goal_timing':timed,
            'first_day':days[0] if days else None,'last_day':days[-1] if days else None,
            'observed_days':len(days),'distinct_matches':len(first),
            'original_alerts_untouched':True,'first_alert_per_fixture':True,
            'split_date':cutoff_test,'split_rule':'70% primeiros dias / 30% últimos dias, se houver ao menos 4 dias',
            'min_ranking_settled':20,'min_test_settled':10,
            'signal_ranking':rank_signals,'league_ranking':rank_leagues,
            'markets':market_report,
            'model_status':'descriptive_not_calibrated',
            'quality_formula':'0.75 × limite inferior Wilson 95% + 0.25 × min(amostra,100)',
            'disclaimer':'Índice 0–100 não é probabilidade, odd, EV+ ou previsão de lucro. Teste fora da amostra é histórico, não prospectivo.'}
