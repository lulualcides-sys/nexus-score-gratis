#!/usr/bin/env python3
"""Auditoria descritiva dos sinais observados pelo NEXUS Cloud.

Analisa gols depois de alertas, não apostas. Sem odds de entrada e resultado
financeiro por operação: P/L em unidades NÃO pode ser calculado aqui.
A contagem usa observações, não jogos independentes: sinais na mesma partida
podem ser correlacionados.
"""
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

BR=ZoneInfo('America/Sao_Paulo')
HORIZONS=('5','10','15','20','25','30','35','40')
HIT='gol_confirmado'
MISS='sem_gol_confirmado'
PENDING='pendente'
UNKNOWN='indeterminado'
INCOMPLETE='janela_incompleta'
VALID={HIT,MISS,PENDING,UNKNOWN,INCOMPLETE}


def minute_band(minute):
    if minute>90:return '91+′'
    lo=((minute-1)//15)*15+1
    return f'{lo}–{lo+14}′'


def _day(value):
    try:
        stamp=datetime.fromisoformat(str(value or '').replace('Z','+00:00'))
        if stamp.tzinfo:return stamp.astimezone(BR).date().isoformat()
    except (TypeError,ValueError,OverflowError):
        pass
    return None


def _entries(journal):
    seen=set()
    raw=journal.get('items') if isinstance(journal,dict) else []
    for r in raw if isinstance(raw,list) else []:
        if not isinstance(r,dict):continue
        key=r.get('id')
        if not isinstance(key,str) or not key or key in seen:continue
        day=_day(r.get('captured_at'))
        try:minute=int(r.get('minute'))
        except (ValueError,TypeError,OverflowError):continue
        if not day or not 1<=minute<=120:continue
        match=str(r.get('match_id') or '').strip()
        rule=str(r.get('rule') or '').strip()
        if not match or not rule:continue
        seen.add(key)
        values=r.get('outcomes') or {}
        if not isinstance(values,dict):values={}
        statuses={h:(values.get(h) if values.get(h) in VALID else UNKNOWN)
                  for h in HORIZONS}
        if r.get('outcome_conflict'):
            statuses={h:UNKNOWN for h in HORIZONS}
        side=r.get('team')
        team=(r.get('home') if side=='home' else r.get('away') if side=='away' else None)
        icon=str(r.get('icon') or '')
        yield {'day':day,'match_id':match,'minute':minute,
               'signal':(icon+' '+rule).strip()[:110],
               'team':str(team or 'Equipe não definida')[:100],
               'league':str(r.get('league') or 'Campeonato não informado')[:100],
               'band':minute_band(minute),'outcomes':statuses}


def _rollup(entries,horizon):
    wins=sum(e['outcomes'][horizon]==HIT for e in entries)
    losses=sum(e['outcomes'][horizon]==MISS for e in entries)
    valid=wins+losses
    return {'observations':len(entries),'matches':len({e['match_id'] for e in entries}),
            'settled':valid,'hits':wins,'misses':losses,
            'pending':sum(e['outcomes'][horizon]==PENDING for e in entries),
            'unknown':sum(e['outcomes'][horizon]==UNKNOWN for e in entries),
            'incomplete':sum(e['outcomes'][horizon]==INCOMPLETE for e in entries),
            'rate_pct':round(100*wins/valid,1) if valid else None,
            'sample_quality':'amostra_maior' if valid>=50 else
                             'em_observacao' if valid>=20 else 'amostra_pequena'}


def _groups(entries,horizon,field,limit=150):
    grouped=defaultdict(list)
    for entry in entries:grouped[entry[field]].append(entry)
    result=[{'label':key,**_rollup(values,horizon)} for key,values in grouped.items()]
    if field=='minute':
        result.sort(key=lambda r:r['label'])
        for item in result:item['label']=str(item['label'])+"'"
    elif field=='band':
        order={'1–15′':0,'16–30′':1,'31–45′':2,'46–60′':3,
               '61–75′':4,'76–90′':5,'91+′':6}
        result.sort(key=lambda r:order.get(r['label'],99))
    else:
        result.sort(key=lambda r:(-r['settled'],-r['observations'],r['label']))
    return result[:limit]


def _progress(entries,horizon):
    by_date=defaultdict(list)
    for e in entries:by_date[e['day']].append(e)
    gathered=[]
    series=[]
    for day in sorted(by_date):
        daily=by_date[day]
        gathered.extend(daily)
        stats=_rollup(gathered,horizon)
        day_stat=_rollup(daily,horizon)
        series.append({'day':day,'daily_observations':day_stat['observations'],
                       'daily_settled':day_stat['settled'],'daily_hits':day_stat['hits'],
                       'daily_rate_pct':day_stat['rate_pct'],
                       'cumulative_observations':stats['observations'],
                       'cumulative_matches':stats['matches'],
                       'cumulative_settled':stats['settled'],
                       'cumulative_hits':stats['hits'],
                       'cumulative_misses':stats['misses'],
                       'cumulative_rate_pct':stats['rate_pct']})
    return series


def evaluate(journal):
    entries=list(_entries(journal))
    horizons={h:_rollup(entries,h) for h in HORIZONS}
    views={}
    for h in HORIZONS:
        views[h]={'by_signal':_groups(entries,h,'signal'),
                  'by_team':_groups(entries,h,'team',limit=100),
                  'by_league':_groups(entries,h,'league',limit=100),
                  'by_minute':_groups(entries,h,'minute',limit=120),
                  'by_minute_band':_groups(entries,h,'band',limit=7),
                  'evolution':_progress(entries,h)}
    days=sorted({e['day'] for e in entries})
    return {'schema':1,'window_minutes':10,'summary':horizons['10'],
            'first_observed_day':days[0] if days else None,
            'last_observed_day':days[-1] if days else None,
            'days_observed':len(days),
            'horizons':horizons,**views['10'],'views':views,
            'updated_at':journal.get('updated_at') if isinstance(journal,dict) else None,
            'money_status':'unavailable_without_entry_odds_and_trade_results',
            'note':'Desempenho observacional de gols após alertas; exclui pendentes, incompletos e indeterminados da taxa. Alertas do mesmo jogo são correlacionados. Sem odds de entrada e liquidação financeira não existe lucro real em unidades.'}
