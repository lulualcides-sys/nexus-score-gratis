#!/usr/bin/env python3
"""Fonte OPCIONAL gratuita API-Football (100 requisições/dia), sem extrapolar quota.

Não roda sem NEXUS_API_FOOTBALL_KEY. Até 8 janelas de 3 horas por dia,
max. 2 listagens + 6 odds por janela = máximo de 64 requisições/dia.
As odds são APENAS pré-jogo, com hora própria da fonte preservada.
"""
import json
import math
import os
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from espn_scoreboard_odds import normalized_team
from pregame_refresh_quotes import append_trio

ROOT='https://v3.football.api-sports.io'
MAX_ODDS_PER_RUN=6

def http_json(url,key):
    req=Request(url,headers={'x-apisports-key':key,'Accept':'application/json',
                             'User-Agent':'NEXUS/verified-odds'})
    with urlopen(req,timeout=8) as resp:
        raw=resp.read(3000001)
    if len(raw)>3000000:raise ValueError('Resposta da fonte acima do limite')
    result=json.loads(raw)
    if not isinstance(result,dict) or result.get('errors'):
        raise ValueError('Fonte não entregou resposta utilizável')
    return result

def stamp(ts):
    try:
        d=datetime.fromisoformat(str(ts).replace('Z','+00:00'))
        return d.timestamp() if d.tzinfo else None
    except (TypeError,ValueError,OverflowError):
        return None

def match_fixture(fixture,events):
    """Duas equipes + apito (10 min) e somente UM jogo compatível."""
    h=normalized_team(fixture.get('home'))
    a=normalized_team(fixture.get('away'))
    start=fixture.get('start_timestamp')
    try: start=float(start)
    except (TypeError,ValueError):return None
    if not h or not a:return None
    valid=[]
    for event in events:
        if not isinstance(event,dict):continue
        meta=event.get('fixture') or {}
        teams=event.get('teams') or {}
        try:
            ident=int(meta.get('id'))
            start_away=float(meta.get('timestamp'))
        except (TypeError,ValueError):continue
        if ident<=0 or abs(start_away-start)>600:continue
        if (normalized_team((teams.get('home') or {}).get('name'))==h and
            normalized_team((teams.get('away') or {}).get('name'))==a):
            valid.append(ident)
    return valid[0] if len(valid)==1 else None

def odds_trio(packet,fixture_id,now_ts):
    entries=packet.get('response') or []
    if not isinstance(entries,list):return None
    for entry in entries:
        if not isinstance(entry,dict):continue
        event=entry.get('fixture') or {}
        if str(event.get('id'))!=str(fixture_id):continue
        source_time=stamp(entry.get('update'))
        if source_time is None or source_time>now_ts+120:
            continue  # nunca fingir que a hora da consulta é hora do preço
        for book in entry.get('bookmakers') or []:
            if not isinstance(book,dict) or not str(book.get('name') or '').strip():continue
            for bet in book.get('bets') or []:
                if not isinstance(bet,dict):continue
                if str(bet.get('name') or '').casefold()!='match winner' and str(bet.get('id') or '')!='1':
                    continue
                prices={}
                for value in bet.get('values') or []:
                    if not isinstance(value,dict):continue
                    side={'home':'home','draw':'draw','away':'away'}.get(str(value.get('value') or '').casefold().strip())
                    if not side:continue
                    try:
                        odd=float(value.get('odd'))
                    except (TypeError,ValueError):continue
                    if math.isfinite(odd) and 1.01<odd<1000:prices[side]=round(odd,4)
                if set(prices)=={'home','draw','away'}:
                    return prices,str(book['name'])[:55],source_time
    return None

def collect_odds(docs,candidates,now_ts,key=None,fetcher=http_json):
    key=os.getenv('NEXUS_API_FOOTBALL_KEY','') if key is None else key
    report={'status':'not_configured','requests':0,'matched':0,'quotes_added':0,'errors':[]}
    if not key:return report
    instant=datetime.fromtimestamp(now_ts,timezone.utc)
    # Quota MAX: 8 janelas/dia × (2 datas + 6 preços) = 64 chamadas/dia.
    # A tarefa está agendada a cada 5min, mas a API só é chamada às HH:00-04
    # quando HH for divisível por 3. Sem abuso de quota e sem ocultar o atraso.
    if instant.hour%3!=0 or instant.minute>=5:
        report['status']='waiting_budget_slot'
        return report
    relevant=[]
    for day,ident,delta in candidates:
        if not 0<delta<=6*3600:continue
        row=((docs.get(day) or {}).get('matches') or {}).get(ident) or {}
        fixture=row.get('fixture') or {}
        if fixture.get('phase')!='scheduled':continue
        try:
            if int(fixture.get('start_timestamp') or 0)<=now_ts:continue
        except (TypeError,ValueError):continue
        relevant.append((day,row,fixture))
    if not relevant:
        report['status']='no_matches_in_window'
        return report
    by_day={}
    for day,row,f in relevant:
        if len(by_day)>=2 and day not in by_day:continue
        by_day.setdefault(day,[]).append((row,f))
    found=[]
    for day,fixtures in list(by_day.items())[:2]:
        try:
            data=fetcher(ROOT+'/fixtures?'+urlencode({'date':day}),key)
            report['requests']+=1
            events=data.get('response') or []
            if not isinstance(events,list):continue
            for row,f in fixtures:
                match=match_fixture(f,events)
                if match is not None:
                    found.append((row,match))
                    report['matched']+=1
        except Exception as exc:
            # Nenhuma URL com chave e nenhum token são registrados.
            report['errors'].append(type(exc).__name__+' na listagem '+day)
    ids=set()
    for row,match in found:
        if len(ids)>=MAX_ODDS_PER_RUN:break
        if match in ids:continue
        ids.add(match)
        try:
            data=fetcher(ROOT+'/odds?'+urlencode({'fixture':match,'page':1}),key)
            report['requests']+=1
            offered=odds_trio(data,match,now_ts)
            if not offered:continue
            prices,bookmaker,source_time=offered
            report['quotes_added']+=append_trio(row,prices,bookmaker,'API-Football',now_ts,source_ts=source_time)
        except Exception as exc:
            report['errors'].append(type(exc).__name__+' na cotação')
    report['status']='partial' if report['errors'] else 'checked'
    return report
