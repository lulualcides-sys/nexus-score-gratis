#!/usr/bin/env python3
"""Auditoria descritiva dos sinais observados pelo NEXUS Cloud.

Analisa gols depois de alertas, não apostas. Sem odds de entrada e resultado
financeiro por operação: P/L em unidades NÃO pode ser calculado aqui.
A contagem usa observações, não jogos independentes: sinais na mesma partida
podem ser correlacionados.
"""
from collections import defaultdict
import math
from datetime import datetime, timedelta
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
        # Apenas gols com minuto de evento verificado: resultado no placar, por si,
        # não permite inferir quando aconteceu o primeiro gol após o alerta.
        delays=[]
        if statuses.get('40')==HIT:
            for goal in r.get('goals_after_alert') or []:
                if not isinstance(goal,dict):continue
                try:goal_minute=int(goal.get('minute'))
                except (TypeError,ValueError,OverflowError):continue
                if minute<goal_minute<=minute+40 and goal.get('team') in ('home','away'):
                    delays.append(goal_minute-minute)
        def safe_number(value):
            try:
                v=float(value)
                return round(v,2) if math.isfinite(v) and 0<=v<=10000 else None
            except (ValueError,TypeError,OverflowError):return None
        pressure=r.get('pressure10')
        score=safe_number(pressure.get('score')) if isinstance(pressure,dict) else None
        yield {'context':{
                 'pressure10_score':score,
                 'pressure10_level':str(pressure.get('level') or '')[:20] if isinstance(pressure,dict) else '',
                 'shots_on':safe_number(r.get('shots_on')),
                 'big_chances':safe_number(r.get('big_chances')),
                 'basis':str(r.get('basis') or '')[:35],
                },
               'first_goal_delay':min(delays) if delays else None,
               'day':day,'match_id':match,'minute':minute,
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


def _goal_timing(entries):
    """Atraso até o primeiro gol, somente com minuto confirmado, após o alerta."""
    confirmed=[e for e in entries if e['outcomes']['40']==HIT]
    dated=[e for e in confirmed if isinstance(e.get('first_goal_delay'),int)
           and 1<=e['first_goal_delay']<=40]
    bins=[]
    for lo in range(1,41,5):
        hi=lo+4
        sample=[e for e in dated if lo<=e['first_goal_delay']<=hi]
        bins.append({'label':f'{lo}–{hi} min','from_min':lo,'to_min':hi,
                     'alerts':len(sample),'matches':len({e['match_id'] for e in sample})})
    delays=sorted(e['first_goal_delay'] for e in dated)
    n=len(delays)
    median=((delays[(n-1)//2]+delays[n//2])/2) if n else None
    first_per_fixture={}
    for entry in sorted(entries,key=lambda e:(e['day'],e['minute'],e['signal'])):
        first_per_fixture.setdefault(entry['match_id'],entry)
    return {'window_minutes':40,'confirmed_goal_alerts':len(confirmed),
            'minute_known_alerts':n,'minute_missing_alerts':len(confirmed)-n,
            'unique_matches_with_timed_goals':len({e['match_id'] for e in dated}),
            'mean_delay_minutes':round(sum(delays)/n,1) if n else None,
            'median_delay_minutes':median,
            'bins':bins,
            'first_alert_per_match':_rollup(list(first_per_fixture.values()),'40'),
            'note':'Tempo até o primeiro gol confirmado (minuto exato). Não é chance calibrada, nem recomendação de manter posição até o fim.'}


def _earliest_per_match(entries):
    """Primeiro sinal de cada jogo: amostra descritiva menos correlacionada."""
    seen={}
    for entry in sorted(entries,key=lambda e:(e['day'],e['minute'],e['signal'])):
        seen.setdefault(entry['match_id'],entry)
    return list(seen.values())


def evaluate(journal):
    all_entries=list(_entries(journal))
    all_days=sorted({e['day'] for e in all_entries})
    cutoff=(datetime.fromisoformat(all_days[-1]).date()-timedelta(days=89)).isoformat() if all_days else None
    entries=[e for e in all_entries if cutoff is None or e['day']>=cutoff]
    earliest=_earliest_per_match(entries)
    horizons={h:_rollup(entries,h) for h in HORIZONS}
    views={}
    for h in HORIZONS:
        views[h]={'by_signal':_groups(entries,h,'signal'),
                  'by_team':_groups(entries,h,'team',limit=100),
                  'by_league':_groups(entries,h,'league',limit=100),
                  'by_minute':_groups(entries,h,'minute',limit=120),
                  'by_minute_band':_groups(entries,h,'band',limit=7),
                  'first_match':_rollup(earliest,h),
                  'by_signal_first_match':_groups(earliest,h,'signal'),
                  'by_team_first_match':_groups(earliest,h,'team',limit=100),
                  'by_league_first_match':_groups(earliest,h,'league',limit=100),
                  'by_minute_first_match':_groups(earliest,h,'minute',limit=120),
                  'by_minute_band_first_match':_groups(earliest,h,'band',limit=7),
                  'evolution':_progress(entries,h)}
    days=sorted({e['day'] for e in entries})
    return {'schema':1,'window_minutes':10,'summary':horizons['10'],
            'goal_timing':_goal_timing(entries),
            'first_observed_day':days[0] if days else None,
            'last_observed_day':days[-1] if days else None,
            'days_observed':len(days),
            'history_window_days':90,'history_start_day':cutoff,
            'raw_observations_all_dates':len(all_entries),
            'observations_older_than_90_days':len(all_entries)-len(entries),
            'horizons':horizons,**views['10'],'views':views,
            'updated_at':journal.get('updated_at') if isinstance(journal,dict) else None,
            'money_status':'unavailable_without_entry_odds_and_trade_results',
            'note':'Desempenho observacional de gols após alertas; exclui pendentes, incompletos e indeterminados da taxa. Alertas do mesmo jogo são correlacionados. Sem odds de entrada e liquidação financeira não existe lucro real em unidades.'}
