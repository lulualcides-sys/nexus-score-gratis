#!/usr/bin/env python3
"""NEXUS: checagem leve antes do apito inicial (GitHub Actions a cada 10 min).

Janela de 75 min antes até 150 min após o início; equipe oficial só quando
a fonte a identificar como confirmada. Odds 1X2 sempre registradas pela fonte,
casa, data/hora e antes do começo do jogo, nunca estimadas.
"""
import json
import re
from datetime import date, timedelta, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from coletar import (NOW, BR, HISTORY, DAY, read, write, fetch, fotmob_list,
                   fotmob_lineups, momentum, stats as fotmob_stats, fotmob_events, merge as merge_pressure)
from odds_capture import get as espn_get, threeway
from sofascore_odds import calendar as sofa_calendar, event_quotes as sofa_quotes, link_fixtures
from pregame_refresh_quotes import new_quote
from espn_scoreboard_odds import collect_odds as espn_scoreboard_odds
from the_odds_api_source import collect_odds as independent_odds

LOOKAHEAD=75*60
AFTER=150*60
MAX_DETAILS=36
MIN_WAIT=8*60
ATTEMPTS=HISTORY/'pregame_attempts.json'
STATUS=HISTORY/'pregame_refresh_status.json'

def fixture_candidates(docs,now_ts):
    choices=[]
    for day,doc in docs.items():
        for key,row in (doc.get('matches') or {}).items():
            if not isinstance(row,dict):continue
            f=row.get('fixture') or {}
            if f.get('phase') not in ('scheduled','live'):continue
            try: delta=int(f.get('start_timestamp') or 0)-now_ts
            except (ValueError,TypeError):continue
            if -AFTER<=delta<=LOOKAHEAD and delta:
                choices.append((day,key,delta))
    return choices


def espn_quotes(packet,row,now_ts):
    f=row.get('fixture') or {}
    if f.get('phase')!='scheduled':return 0
    try:
        kickoff=int(f.get('start_timestamp') or 0)
        if now_ts>=kickoff:return 0
    except (ValueError,TypeError):return 0
    comps=((packet.get('header') or {}).get('competitions') or [])
    comp=comps[0] if comps and isinstance(comps[0],dict) else {}
    offers=packet.get('pickcenter') or comp.get('odds') or []
    if isinstance(offers,dict):offers=[offers]
    if not isinstance(offers,list):return 0
    for offer in offers:
        if not isinstance(offer,dict):continue
        prices=threeway(offer)
        if not prices:continue
        provider=offer.get('provider') or {}
        bookmaker=str((provider.get('name') if isinstance(provider,dict) else '') or
            offer.get('providerName') or 'Não informada')[:55]
        return sum(new_quote(row,sel,val,bookmaker,'ESPN',NOW.isoformat())
                   for sel,val in prices.items())
    return 0

def compare_lineups(row,incoming):
    previous=row.get('lineups') or {}
    changed=0
    for side,new in incoming.items():
        old=previous.get(side) or {}
        # Não substituir escalação confirmada por estimativa mais antiga.
        if old.get('status')=='confirmed' and new.get('status')!='confirmed':continue
        left={k:v for k,v in old.items() if k!='updated_at'}
        right={k:v for k,v in new.items() if k!='updated_at'}
        if left!=right:
            previous[side]=new
            changed+=1
    if changed:row['lineups']=previous
    return changed

def update_live_details(row,packet):
    """Atualiza apenas fatos observados, nunca cria pressão/gols ausentes."""
    if (row.get('fixture') or {}).get('phase') not in ('live','finished'):
        return {'pressure_added':0,'events_added':0,'stats_added':0}
    counts={'pressure_added':0,'events_added':0,'stats_added':0}
    old=(row.get('thermometer') or {}).get('points') or []
    fresh=momentum(packet)
    if fresh:
        merged=merge_pressure(old,fresh)
        if merged!=old:
            counts['pressure_added']=len({p.get('minute') for p in merged})-len(
                {p.get('minute') for p in old})
            row['thermometer']={'points':merged}
    new_stats=fotmob_stats(packet)
    if any(new_stats.values()):
        prior=row.setdefault('stats',{})
        for side in ('home','away'):
            new=new_stats.get(side) or {}
            if not new:continue
            cur=prior.setdefault(side,{})
            for key,value in new.items():
                if value is None:continue
                if cur.get(key)!=value:
                    cur[key]=value
                    counts['stats_added']+=1
    new_events=fotmob_events(packet)
    if new_events:
        old_events=row.get('events') or []
        combined={
            (e.get('minute'),e.get('type'),e.get('side'),e.get('text')):e
            for e in old_events+new_events if isinstance(e,dict) and
               e.get('minute') is not None and e.get('type')
        }
        unique=sorted(combined.values(),key=lambda p:int(p.get('minute') or 0))[-150:]
        if unique!=old_events:
            counts['events_added']=len(unique)-len(old_events)
            row['events']=unique
    return counts

def run():
    now_ts=int(NOW.timestamp())
    today=date.fromisoformat(DAY)
    days=[today]
    local_hour=NOW.astimezone(BR).hour
    if local_hour<=3:days.append(today-timedelta(days=1))
    if local_hour>=22:days.append(today+timedelta(days=1))
    docs={d.isoformat():read(HISTORY/(d.isoformat()+'.json')) for d in days}
    # Refrescar programação de hoje e das próximas horas; evita não detectar
    # partidas adicionadas após a execução completa horária.
    failures=[]
    for day in days:
        try:
            fixtures=fotmob_list(day.isoformat())
            for fixture in fixtures:
                ts=fixture.get('start_timestamp')
                if not ts or not (-AFTER<=int(ts)-now_ts<=LOOKAHEAD):continue
                mid=str(fixture.get('id') or '')
                if not re.fullmatch(r'fotmob-\d{1,14}',mid):continue
                current=docs[day.isoformat()].setdefault('matches',{}).setdefault(mid,{})
                old=current.get('fixture') or {}
                if old.get('phase')=='finished':continue
                # Não tratar a data da consulta como uma nova atualização
                # esportiva: evita publicar commits idênticos a cada 10 min.
                clean={k:v for k,v in fixture.items() if k!='collected_at'}
                combined={**old,**clean}
                if {k:v for k,v in old.items() if k!='collected_at'} != {
                        k:v for k,v in combined.items() if k!='collected_at'}:
                    current['fixture']=combined
        except Exception as err:
            failures.append('Agenda '+day.isoformat()+': '+str(err)[:100])
    candidates=fixture_candidates(docs,now_ts)
    attempts=read(ATTEMPTS).get('matches') or {}
    due=[entry for entry in candidates if now_ts-float(attempts.get(entry[1]) or 0)>=MIN_WAIT]
    # Alternar o atendimento quando muitas partidas acontecem simultaneamente.
    due.sort(key=lambda v:(float(attempts.get(v[1]) or 0),abs(v[2]-30*60)))
    due=due[:MAX_DETAILS]
    result={'updated_at':NOW.isoformat(),'matches_in_window':len(candidates),
            'requested':len(due),'lineups_updated':0,'odds_updated':0,
            'pressure_added':0,'events_added':0,'stats_added':0,'errors':failures}
    def fetch_match(day,key):
        if key.startswith('fotmob-'):
            ident=key.split('-',1)[1]
            last_error=None
            for root in ('https://www.fotmob.com/api/data/matchDetails?',
                         'https://www.fotmob.com/api/matchDetails?'):
                try:return fetch(root+urlencode({'matchId':ident}),timeout=7)
                except Exception as exc:last_error=exc
            raise RuntimeError(str(last_error))
        m=re.fullmatch(r'espn-([a-z0-9.]{2,40})-(\d{1,16})',key)
        if m:
            return espn_get('https://site.api.espn.com/apis/site/v2/sports/soccer/'+
                            m[1]+'/summary?event='+m[2])
        return {}
    changes=False
    with ThreadPoolExecutor(max_workers=9) as pool:
        work={pool.submit(fetch_match,day,key):(day,key) for day,key,_ in due}
        for future in as_completed(work):
            day,key=work[future]
            attempts[key]=now_ts
            try:
                packet=future.result()
                row=docs[day]['matches'][key]
                if key.startswith('fotmob-'):
                    lineups=fotmob_lineups(packet)
                    result['lineups_updated']+=compare_lineups(row,lineups)
                    new_info=update_live_details(row,packet)
                    for name,value in new_info.items():result[name]+=value
                    # Apenas esquemas 1X2 explícitos são aceitos; matchDetails do
                    # FotMob não documenta odds, portanto não deduzir mercados.
                else:
                    result['odds_updated']+=espn_quotes(packet,row,now_ts)
            except Exception as e:
                if len(result['errors'])<12:result['errors'].append(key+': '+str(e)[:110])
    # Segunda fonte: apenas partidas identificadas simultaneamente pelos
    # dois clubes e pelo minuto do apito inicial. Nunca aproximar por liga.
    result['sofascore_matched']=0
    result['sofascore_checked']=0
    result['sofascore_quotes_added']=0
    try:
        schedules=[]
        for day in days:
            schedules.extend(sofa_calendar(day.isoformat()))
        selected=[(day,key,delta,(docs[day].get('matches') or {}).get(key,{}).get('fixture') or {})
                  for day,key,delta in candidates if delta>0]
        linked=link_fixtures(selected,schedules)
        result['sofascore_matched']=len(linked)
        with ThreadPoolExecutor(max_workers=6) as pool:
            future={pool.submit(sofa_quotes,sofa_id):(day,key)
                    for day,key,_,_,sofa_id in linked[:24]}
            for task in as_completed(future):
                day,key=future[task]
                result['sofascore_checked']+=1
                try:
                    offer=task.result()
                    if not offer:continue
                    prices,bookmaker=offer
                    row=docs[day]['matches'][key]
                    # Mesmo se houver odds, recusar armazenar depois do kickoff.
                    f=row.get('fixture') or {}
                    if NOW.timestamp()>=int(f.get('start_timestamp') or 0):continue
                    count=sum(new_quote(row,sel,price,bookmaker,'SofaScore',
                                        NOW.isoformat()) for sel,price in prices.items())
                    result['sofascore_quotes_added']+=count
                    result['odds_updated']+=count
                except Exception as err:
                    if len(result['errors'])<12:
                        result['errors'].append('SofaScore: '+str(err)[:110])
    except Exception as err:
        if len(result['errors'])<12:result['errors'].append(
            'SofaScore calendário indisponível: '+str(err)[:110])
    # Fonte alternativa para partidas FotMob: agenda ESPN + resumo por ID ESPN,
    # com verificação estrita de clubes e horário antes de aceitar preços.
    result['espn_fallback']=espn_scoreboard_odds(docs,candidates,now_ts)
    result['odds_updated']+=result['espn_fallback']['quotes_added']
    if result['espn_fallback']['errors']:
        result['errors'].extend(result['espn_fallback']['errors'][:4])
    # Provedor adicional 1X2 independente (chave opcional, nunca enviada ao navegador).
    # O dashboard continua funcionando quando um provedor falha ou bloqueia.
    result['the_odds_api']=independent_odds(docs,candidates,now_ts)
    result['odds_updated']+=result['the_odds_api']['quotes_added']
    if result['the_odds_api']['errors']:
        result['errors'].extend(result['the_odds_api']['errors'][:4])
    if any(result[k] for k in ('lineups_updated','odds_updated',
                              'pressure_added','events_added','stats_added')):
        changes=True
    # As atualizações de calendário também interessam, mas não gerar commit
    # apenas com resultados idênticos de uma consulta a cada 10 min.
    for day,doc in docs.items():
        p=HISTORY/(day+'.json')
        if doc and (read(p).get('matches') or {})!= (doc.get('matches') or {}):
            doc['updated_at']=NOW.isoformat()
            write(p,doc)
            changes=True
    if due:write(ATTEMPTS,{'updated_at':NOW.isoformat(),'matches':attempts})
    if changes:
        write(STATUS,result)
    print(json.dumps(result,ensure_ascii=False))
    return result

if __name__=='__main__':
    run()
