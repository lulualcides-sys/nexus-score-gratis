#!/usr/bin/env python3
"""Enriquecimento progressivo de scouts/eventos FotMob para os 3 dias visíveis.

Consultas HTTP de partidas reais, limite por execução, armazenamento de origem.
Não calcula odds nem inventa finalizações em jogos sem scouts.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from urllib.parse import urlencode
from coletar import DAY, HISTORY, NOW, read, write, fetch, stats, momentum, fotmob_events, fotmob_lineups, merge

LIMIT = 42
RETRY_HOURS = 12
STATUS = HISTORY/'details_backfill_status.json'
TRIED = HISTORY/'details_backfill_attempts.json'
MAX_SECONDS = 85

def updated_stats(existing, verified):
    target={side:{**(existing.get(side) or {})} for side in ('home','away')}
    gained=0
    for side in ('home','away'):
        for name,value in (verified.get(side) or {}).items():
            if target[side].get(name) is None:
                target[side][name]=value
                gained+=1
    return target,gained

def run():
    today=date.fromisoformat(DAY)
    days=[(today-timedelta(days=i)).isoformat() for i in range(3)]
    docs={d:read(HISTORY/(d+'.json')) for d in days}
    attempts=read(TRIED).get('matches') or {}
    current=NOW.timestamp()
    choices=[]
    for d,doc in docs.items():
        for key,row in (doc.get('matches') or {}).items():
            if not re.fullmatch(r'fotmob-\d{1,14}',key):continue
            f=row.get('fixture') or {}
            if f.get('phase') not in ('finished','live'):continue
            last=float(attempts.get(key) or 0)
            if current-last<RETRY_HOURS*3600:continue
            s=row.get('stats') or {}
            n=len(s.get('home') or {})+len(s.get('away') or {})
            incidents=len(row.get('events') or [])
            lineup_count=len(row.get('lineups') or {})
            points=len((row.get('thermometer') or {}).get('points') or [])
            if n>=7 and incidents>=3 and lineup_count>=2:continue
            priority=(0 if points and (n<5 or incidents<3) else 1 if n<3 else 2,
                      0 if f.get('phase')=='live' else 1,
                      -int(f.get('start_timestamp') or 0))
            choices.append((priority,d,key))
    choices.sort(key=lambda t:t[0])
    choices=choices[:LIMIT]
    info={'updated_at':NOW.isoformat(),'days':days,'eligible':len(choices),
          'requests':0,'scout_fields_added':0,'matches_with_stats':0,'events_added':0,
          'lineups_added':0,'pressure_points_added':0,'errors':[]}
    begun=time.monotonic()
    def read_match(day,key):
        mid=key.split('-',1)[1]
        url='https://www.fotmob.com/api/data/matchDetails?'+urlencode({'matchId':mid})
        return fetch(url,timeout=8)
    with ThreadPoolExecutor(max_workers=9) as pool:
        futures={pool.submit(read_match,d,key):(d,key) for _,d,key in choices}
        for fut in as_completed(futures):
            d,key=futures[fut]
            attempts[key]=current
            info['requests']+=1
            try:
                packet=fut.result()
                if time.monotonic()-begun>MAX_SECONDS:break
                row=docs[d]['matches'][key]
                extracted=stats(packet)
                row['stats'],num=updated_stats(row.get('stats') or {},extracted)
                info['scout_fields_added']+=num
                if row['stats']['home'] or row['stats']['away']:info['matches_with_stats']+=1
                new_events=fotmob_events(packet)
                before=row.get('events') or []
                unique={(e.get('minute'),e.get('type'),e.get('side'),e.get('text')):e
                    for e in before+new_events if isinstance(e,dict)}
                row['events']=sorted(unique.values(),key=lambda x:(x.get('minute') or 0,x.get('type') or ''))[:180]
                info['events_added']+=len(row['events'])-len(before)
                lineups=fotmob_lineups(packet)
                if lineups:
                    old=row.get('lineups') or {}
                    row['lineups']={**old,**lineups}
                    info['lineups_added']+=len(lineups)
                if not (row.get('thermometer') or {}).get('points'):
                    pts=momentum(packet)
                    if pts:
                        row['thermometer']={'points':merge([],pts)}
                        info['pressure_points_added']+=len(pts)
                row.setdefault('sources',[])
                if 'FotMob' not in row['sources']:row['sources'].append('FotMob')
            except Exception as exc:
                if len(info['errors'])<12:
                    info['errors'].append(key+': '+str(exc)[:115])
    for d,doc in docs.items():
        if doc:write(HISTORY/(d+'.json'),doc)
    # Housekeep attempts to visible days only (avoid infinite growth).
    visible=set(key for doc in docs.values() for key in (doc.get('matches') or {}))
    write(TRIED,{'updated_at':NOW.isoformat(),'matches':
                  {k:v for k,v in attempts.items() if k in visible}})
    write(STATUS,info)
    print(json.dumps(info,ensure_ascii=False))
if __name__=='__main__':run()
