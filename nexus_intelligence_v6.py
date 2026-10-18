"""NEXUS 6.0 — evidências descritivas; nunca altera histórico ou cria odds.
Modelo histórico: um primeiro alerta por partida, 40 minutos e validação cronológica.
Resultados de mercados usam somente partidas finalizadas com placar íntegro.
"""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import math
import re
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
        settled=[r for r in group if r['outcomes']['40'] in ('gol_confirmado','sem_gol_confirmado')]
        n=len(settled)
        wins=sum(r['outcomes']['40']=='gol_confirmado' for r in settled)
        after=[r for r in settled if split_day and r['day']>=split_day]
        before=[r for r in settled if split_day and r['day']<split_day]
        value=_wilson_lower(wins,n)
        # Índice de confiança DESCRITIVO, não probabilidade de gol nem EV.
        quality=round(value*0.75+min(n,100)*0.25,1) if n>=20 else None
        results.append({'label':label,'matches':len({r['match_id'] for r in group}),
                        'observations':len(group),'settled':n,'hits':wins,'misses':n-wins,
                        'rate_pct':round(100*wins/n,1) if n else None,
                        'wilson_lower_pct':value,'quality_index':quality,
                        'state':'amostra_minima' if n>=20 else 'amostra_insuficiente',
                        'train_settled':len(before),'test_settled':len(after),
                        'train_rate_pct':round(100*sum(x['outcomes']['40']=='gol_confirmado' for x in before)/len(before),1) if before else None,
                        'test_rate_pct':round(100*sum(x['outcomes']['40']=='gol_confirmado' for x in after)/len(after),1) if after else None,
                        'test_usable':len(after)>=10 and len(before)>=20})
    return sorted(results,key=lambda x:(x['quality_index'] is None,
                                         -(x['quality_index'] or 0),-x['settled'],x['label']))[:80]

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
        if fid in verified and verified[fid]!=(hg,ag):conflicted.add(fid)
        else:verified[fid]=(hg,ag)
    for fid in conflicted:verified.pop(fid,None)
    out=[]
    for key,label in MARKETS:
        hits=0
        for hg,ag in verified.values():
            value={'over_15':hg+ag>=2,'over_25':hg+ag>=3,
                   'btts':hg>0 and ag>0,'lay_goleada':abs(hg-ag)<3}[key]
            hits+=int(value)
        n=len(verified)
        out.append({'market':key,'label':label,'finished_verified':n,'hits':hits,'misses':n-hits,
                    'rate_pct':round(100*hits/n,1) if n else None,
                    'has_real_entry_odds':False,'money_status':'unavailable_without_verified_prices'})
    return {'scope':'finished_matches_in_current_snapshot_only','distinct_verified_games':len(verified),
            'conflicting_games_excluded':len(conflicted),
            'prices':'not_assumed','markets':out,
            'note':'Mercados descritivos por placar final. Sem odds de entrada: não são operações liquidadas nem P/L.'}

def evaluate_v6(journal,games,as_of=None):
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
    return {'schema':1,'name':'NEXUS 6.0','window_minutes':40,'history_days':90,
            'first_day':days[0] if days else None,'last_day':days[-1] if days else None,
            'observed_days':len(days),'distinct_matches':len(first),
            'original_alerts_untouched':True,'first_alert_per_fixture':True,
            'split_date':cutoff_test,'split_rule':'70% primeiros dias / 30% últimos dias, se houver ao menos 4 dias',
            'min_ranking_settled':20,'min_test_settled':10,
            'signal_ranking':rank_signals,'league_ranking':rank_leagues,
            'markets':_markets(games,cutoff),
            'model_status':'descriptive_not_calibrated',
            'quality_formula':'0.75 × limite inferior Wilson 95% + 0.25 × min(amostra,100)',
            'disclaimer':'Índice 0–100 não é probabilidade, odd, EV+ ou previsão de lucro. Teste fora da amostra é histórico, não prospectivo.'}
