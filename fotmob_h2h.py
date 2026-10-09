#!/usr/bin/env python3
"""FotMob H2H direto do jogo + cache, com checagem de identidades e fim de jogo.

Fontes: content.h2h.matches de matchDetails. Não cria confrontos por
semelhança de apelidos, nem mistura calendários ESPN/FotMob por ID.
"""
import json
import re
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlencode
from coletar import HISTORY,DAY,NOW,fetch,read,write,utc_ts

CACHE=HISTORY/'fotmob_h2h_cache.json'
STATUS=HISTORY/'fotmob_h2h_status.json'
MAX_FETCH=36

def valid_id(value):
    return str(value or '') if re.fullmatch(r'[1-9]\d{0,11}',str(value or '')) else ''

def match_score(row):
    status=row.get('status') or {}
    if not isinstance(status,dict):return None
    raw=status.get('scoreStr') or row.get('score')
    m=re.fullmatch(r'\s*(\d{1,2})\s*[-–:]\s*(\d{1,2})\s*',str(raw or ''))
    if m:return int(m.group(1)),int(m.group(2))
    h=row.get('home') or {};a=row.get('away') or {}
    try:
        scores=int(h.get('score')),int(a.get('score'))
        return scores if all(0<=n<=50 for n in scores) else None
    except (TypeError,ValueError):return None

def parse_h2h(doc,fixture):
    """Retorna somente resultados FT cuja identidade coincide com o duelo."""
    if not isinstance(doc,dict):return []
    general=doc.get('general') or {}
    h=general.get('homeTeam') or {};a=general.get('awayTeam') or {}
    required={valid_id(fixture.get('home_id')),valid_id(fixture.get('away_id'))}
    if '' in required or len(required)!=2:return []
    if {valid_id(h.get('id')),valid_id(a.get('id'))}!=required:return []
    cutoff=fixture.get('start_timestamp')
    try:cutoff=int(cutoff)
    except (ValueError,TypeError):return []
    matchdata=((doc.get('content') or {}).get('h2h') or {}).get('matches') or []
    if not isinstance(matchdata,list):return []
    found={}
    for row in matchdata[:50]:
        if not isinstance(row,dict):continue
        hs=row.get('home') or {};aw=row.get('away') or {}
        if {valid_id(hs.get('id')),valid_id(aw.get('id'))}!=required:continue
        status=row.get('status') or {}
        if not (row.get('finished') is True or status.get('finished') is True):continue
        tm=row.get('time') or {};when=tm.get('utcTime') if isinstance(tm,dict) else None
        ts=utc_ts(when or status.get('utcTime'))
        if not ts or ts>=cutoff:continue
        score=match_score(row)
        if not score:continue
        hn,an=str(hs.get('name') or ''),str(aw.get('name') or '')
        if not hn or not an:continue
        source={'at':ts,'home':hn[:105],'away':an[:105],
                'score':str(score[0])+'-'+str(score[1]),
                'competition':str(((row.get('league') or {}).get('name') or fixture.get('league') or ''))[:70],
                'source':'FotMob'}
        found[(ts,tuple(sorted(required)))]=source
    return sorted(found.values(),key=lambda g:g['at'],reverse=True)[:15]

def get_h2h(mid,fixture):
    url='https://www.fotmob.com/api/data/matchDetails?'+urlencode({'matchId':mid})
    return parse_h2h(fetch(url,timeout=8),fixture)

def main():
    day=datetime.strptime(DAY,'%Y-%m-%d').date()
    days=[(day-timedelta(days=i)).isoformat() for i in range(3)]
    docs={d:read(HISTORY/(d+'.json')) for d in days}
    raw=read(CACHE);cache=raw.get('matches') if isinstance(raw.get('matches'),dict) else {}
    targets={}
    for d,doc in docs.items():
        for key,row in (doc.get('matches') or {}).items():
            f=row.get('fixture') or {}
            m=re.fullmatch(r'fotmob-(\d{5,12})',str(f.get('id') or ''))
            if not m or not valid_id(f.get('home_id')) or not valid_id(f.get('away_id')):continue
            priority=0 if f.get('phase')=='live' else 1 if f.get('phase')=='scheduled' else 2
            targets.setdefault(m.group(1),[]).append((priority,d,key,f))
    def cache_fresh(entry):
        stamp=(entry or {}).get('updated_at')
        try:
            updated=datetime.fromisoformat(str(stamp).replace('Z','+00:00'))
            return updated.tzinfo is not None and (NOW-updated).total_seconds()<60*60*36
        except ValueError:return False
    ordered=sorted(targets,key=lambda mid:(min(x[0] for x in targets[mid]),mid))
    pending=[mid for mid in ordered if not cache_fresh(cache.get(mid))][:MAX_FETCH]
    stats={'checked_at':NOW.isoformat(),'matches_candidates':len(targets),
           'requests':len(pending),'requests_ok':0,'h2h_matches_verified':0,
           'games_with_h2h':0,'errors':[]}
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs={pool.submit(get_h2h,mid,targets[mid][0][3]):mid for mid in pending}
        for task in as_completed(jobs):
            mid=jobs[task]
            try:
                matches=task.result()
                cache[mid]={'updated_at':NOW.isoformat(),'matches':matches}
                stats['requests_ok']+=1
            except Exception as exc:
                if len(stats['errors'])<8:stats['errors'].append(mid+': '+str(exc)[:95])
    for mid,targets_rows in targets.items():
        entry=cache.get(mid) or {}
        for priority,d,key,fixture in targets_rows:
            matches=[m for m in (entry.get('matches') or [])
                     if isinstance(m,dict) and m.get('at') and int(m['at'])<int(fixture.get('start_timestamp') or 0)]
            if matches:
                docs[d]['matches'][key]['h2h_verified']=matches
                stats['h2h_matches_verified']+=len(matches)
                stats['games_with_h2h']+=1
    for d,doc in docs.items():
        if doc:write(HISTORY/(d+'.json'),doc)
    write(CACHE,{'updated_at':NOW.isoformat(),'matches':{
        k:v for k,v in cache.items() if k in set(ordered)}})
    write(STATUS,stats)
    print(json.dumps(stats,ensure_ascii=False))
if __name__=='__main__':main()
