#!/usr/bin/env python3
"""Forma esportiva real: ate 10 jogos anteriores por equipe, para cada jogo de 3 dias.

A origem e o calendario ESPN da liga do respectivo jogo. Nunca usa partidas
iniciadas depois do confronto analisado. Nao estima lucro nem EV+.
"""
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode

from coletar import HISTORY, DAY, NOW, fetch, read, write, utc_ts

LAST_N = 10
WINDOW_DAYS = 3
CACHE_TTL_HOURS = 6
CACHE = HISTORY / 'team_schedule_cache.json'
STATUS = HISTORY / 'team_form_status.json'

def valid_score(fixture):
    if not isinstance(fixture, dict) or fixture.get('phase') != 'finished':
        return None
    m = re.fullmatch(r'(\d{1,2})-(\d{1,2})',str(fixture.get('score') or ''))
    if not m:return None
    return int(m.group(1)),int(m.group(2))

def fixture_timestamp(fixture):
    try:
        t=int(fixture.get('start_timestamp'))
        return t if t>0 else None
    except (TypeError,ValueError,OverflowError):return None

def team_schedule_fixture(event,league):
    """O calendario ESPN de times omite event.status e usa score como objeto."""
    if not isinstance(event,dict):return None
    comps=event.get('competitions') or []
    comp=comps[0] if comps and isinstance(comps[0],dict) else {}
    competitors=comp.get('competitors') or []
    h=next((t for t in competitors if isinstance(t,dict) and t.get('homeAway')=='home'),None)
    a=next((t for t in competitors if isinstance(t,dict) and t.get('homeAway')=='away'),None)
    if not h or not a:return None
    def score(competitor):
        raw=competitor.get('score')
        if isinstance(raw,dict):raw=raw.get('displayValue',raw.get('value'))
        try:
            n=float(raw)
            return int(n) if n.is_integer() and 0<=n<=50 else None
        except (ValueError,TypeError):return None
    home_goals,away_goals=score(h),score(a)
    ts=utc_ts(event.get('date') or comp.get('date'))
    # Um calendario sem estado final nao prova que um jogo de agora acabou.
    # So usar jogos com placares publicados e inicio ha ao menos 4 horas.
    if home_goals is None or away_goals is None or not ts or ts>=NOW.timestamp()-4*3600:
        return None
    state=str((((comp.get('status') or event.get('status') or {}).get('type') or {}).get('state')) or '').lower()
    if state and state!='post':return None
    home_team=h.get('team') or {}
    away_team=a.get('team') or {}
    if not home_team.get('displayName') or not away_team.get('displayName'):return None
    return {
        'id':'espn-'+league+'-'+str(event.get('id') or comp.get('id') or ''),
        'home':str(home_team['displayName']),'away':str(away_team['displayName']),
        'home_id':str(home_team.get('id') or h.get('id') or ''),
        'away_id':str(away_team.get('id') or a.get('id') or ''),
        'league':league,'start_timestamp':ts,'phase':'finished',
        'score':str(home_goals)+'-'+str(away_goals)}

def schedule(league,team_id,season=None):
    query=urlencode({'limit':160,**({'season':season} if season is not None else {})})
    url='https://site.api.espn.com/apis/site/v2/sports/soccer/'+league+'/teams/'+team_id+'/schedule?'+query
    packet=fetch(url,timeout=7)
    result=[]
    for event in packet.get('events') or []:
        fixture=team_schedule_fixture(event,league)
        if fixture:result.append(fixture)
    return result

def history_before(schedule_games, fixture, team_id, limit=LAST_N):
    """Corta no instante de inicio do confronto, nunca em now()."""
    cutoff=fixture_timestamp(fixture)
    if cutoff is None:return []
    current_id=str(fixture.get('id') or '')
    found={}
    for g in schedule_games:
        if not isinstance(g,dict):continue
        ts=fixture_timestamp(g)
        result=valid_score(g)
        if ts is None or ts>=cutoff or result is None:continue
        if str(g.get('id') or '')==current_id:continue
        h,a=str(g.get('home_id') or ''),str(g.get('away_id') or '')
        if str(team_id) not in (h,a):continue
        home=bool(str(team_id)==h)
        gf,ga=result if home else result[::-1]
        opponent=g.get('away') if home else g.get('home')
        if not opponent:continue
        found[g['id']]={'day':datetime.fromtimestamp(ts,timezone.utc).date().isoformat(),
             'ts':ts,'opponent':str(opponent)[:105],'venue':'Casa' if home else 'Fora',
             'score':str(g.get('score'))[:10],
             'gf':gf,'ga':ga,'result':'V' if gf>ga else 'E' if gf==ga else 'D',
             'league':str(g.get('league') or '')[:80]}
    ordered=sorted(found.values(),key=lambda g:g['ts'],reverse=True)
    return ordered[:limit]

def summarise(games,source):
    n=len(games)
    if not n:return {'available':0,'requested':LAST_N,'games':[],'source':source,'complete':False}
    wins=sum(g['gf']>g['ga'] for g in games)
    draws=sum(g['gf']==g['ga'] for g in games)
    defeats=n-wins-draws
    gf=sum(g['gf'] for g in games);ga=sum(g['ga'] for g in games)
    over15=sum(g['gf']+g['ga']>=2 for g in games)
    over25=sum(g['gf']+g['ga']>=3 for g in games)
    btts=sum(g['gf']>0 and g['ga']>0 for g in games)
    return {'requested':LAST_N,'available':n,'complete':n==LAST_N,
        'wins':wins,'draws':draws,'losses':defeats,
        'goals_for':gf,'goals_against':ga,
        'avg_goals_for':round(gf/n,2),'avg_goals_against':round(ga/n,2),
        'over15_pct':round(over15/n*100,1),'over25_pct':round(over25/n*100,1),
        'btts_pct':round(btts/n*100,1),
        'source':source,'games':games}

def cached_schedule(key,league,team_id,cache):
    entry=cache.get(key)
    stamp=(entry or {}).get('at')
    if isinstance(entry,dict) and isinstance(entry.get('games'),list) and entry.get('games') and stamp:
        try:
            last=datetime.fromisoformat(str(stamp).replace('Z','+00:00'))
            if last.tzinfo and (NOW-last).total_seconds()<CACHE_TTL_HOURS*3600:
                return entry['games'],False,[]
        except ValueError:pass
    errors=[]
    games=[]
    try:
        games=schedule(league,team_id)
    except Exception as e:
        errors.append('current: '+str(e)[:100])
    # Tentar completar o historico com temporadas anteriores da MESMA liga.
    # Id do clube ESPN e fixo dentro da competicao; nao mistura competicoes.
    current=NOW.year
    if len({g['id'] for g in games})<LAST_N:
        for season in (current,current-1):
            try:games.extend(schedule(league,team_id,season))
            except Exception as e:errors.append(str(season)+': '+str(e)[:100])
            if len({g['id'] for g in games})>=LAST_N:break
    unique={g['id']:g for g in games if valid_score(g) and fixture_timestamp(g)}
    games=sorted(unique.values(),key=lambda g:g['start_timestamp'],reverse=True)[:85]
    return games,True,errors

def main():
    today=datetime.strptime(DAY,'%Y-%m-%d').date()
    days=[(today-timedelta(days=n)).isoformat() for n in range(WINDOW_DAYS)]
    docs={d:read(HISTORY/(d+'.json')) for d in days}
    tasks={}
    for day,doc in docs.items():
        for game_id,row in (doc.get('matches') or {}).items():
            if not isinstance(row,dict):continue
            f=row.get('fixture') or {}
            if not str(f.get('id') or '').startswith('espn-') or not fixture_timestamp(f):continue
            league=f.get('league_code')
            if not league:
                m=re.fullmatch(r'espn-([a-z0-9.]+)-(\d+)',str(f.get('id')))
                league=m.group(1) if m else None
            if not league or not re.fullmatch(r'[a-z0-9.]{2,40}',str(league)):continue
            for side in ('home','away'):
                team_id=str(f.get(side+'_id') or '')
                if not re.fullmatch(r'\d{1,12}',team_id):continue
                tasks.setdefault((league,team_id),[]).append((day,game_id,side))
    existing=read(CACHE)
    cache=existing.get('schedules') if isinstance(existing.get('schedules'),dict) else {}
    status={'checked_at':NOW.isoformat(),'days':days,'teams':len(tasks),
       'fetched':0,'games_with_form':0,'complete_team_samples':0,'errors':[]}
    with ThreadPoolExecutor(max_workers=12) as pool:
        future={pool.submit(cached_schedule,league+'/'+tid,league,tid,cache):(league,tid)
                for league,tid in tasks}
        for done in as_completed(future):
            league,tid=future[done]
            key=league+'/'+tid
            try:
                games,fetched,errors=done.result()
            except Exception as e:
                games=[];fetched=False;errors=[str(e)[:100]]
            if fetched:
                cache[key]={'at':NOW.isoformat(),'games':games}
                status['fetched']+=1
            if errors and len(status['errors'])<10:
                status['errors'].append(key+': '+', '.join(errors)[:120])
            for day,game_id,side in tasks[(league,tid)]:
                row=docs[day]['matches'][game_id]
                form=summarise(history_before(games,row['fixture'],tid),
                    'ESPN · jogos nesta competicao')
                row.setdefault('team_form',{})[side]=form
    # Reprocessa a forma para cada confronto sem reutilizar resultado futuro.
    for day,doc in docs.items():
        for row in (doc.get('matches') or {}).values():
            if not isinstance(row,dict):continue
            forms=row.get('team_form') or {}
            if forms.get('home',{}).get('available') or forms.get('away',{}).get('available'):
                status['games_with_form']+=1
            status['complete_team_samples']+=sum(
                bool(forms.get(s,{}).get('complete')) for s in ('home','away'))
        if doc:write(HISTORY/(day+'.json'),doc)
    # Cache so partidas esportivas publicas; manter apenas as equipes usadas agora.
    write(CACHE,{'updated_at':NOW.isoformat(),'schedules':
                 {k:v for k,v in cache.items() if k in {a+'/'+b for a,b in tasks}}})
    write(STATUS,status)
    print(json.dumps(status,ensure_ascii=False))
if __name__=='__main__':main()
