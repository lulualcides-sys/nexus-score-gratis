#!/usr/bin/env python3
"""FotMob: forma dos 10 jogos ANTERIORES por equipe e elenco geral verificado.
Não usa jogos futuros, odds de fechamento nem calcula EV+.
Cache resumido evita repetir requests pesadas em todas as execuções.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from coletar import HISTORY, DAY, NOW, read, write, utc_ts
from team_form import summarise

LIMIT_PER_RUN = 28
TTL_HOURS = 40
CACHE_FILE = HISTORY / 'fotmob_team_cache.json'
STATUS_FILE = HISTORY / 'fotmob_form_status.json'
logo_id=re.compile(r'/teamlogo/(\d{1,12})\.png$')

def team_id(fixture,side):
    raw=str(fixture.get(side+'_id') or '')
    if re.fullmatch(r'\d{1,12}',raw):return raw
    m=logo_id.search(str(fixture.get(side+'_logo') or ''))
    return m.group(1) if m else None

def score(row):
    home=row.get('home') or {}
    away=row.get('away') or {}
    nums=[home.get('score') if isinstance(home,dict) else None,
          away.get('score') if isinstance(away,dict) else None]
    if any(v is None for v in nums):
        status=row.get('status') or {}
        raw=str(status.get('scoreStr') or row.get('score') or '')
        m=re.search(r'(\d{1,2})\s*[-–:]\s*(\d{1,2})',raw)
        nums=list(map(int,m.groups())) if m else nums
    try:
        a,b=int(nums[0]),int(nums[1])
        return (a,b) if 0<=a<=40 and 0<=b<=40 else None
    except (ValueError,TypeError):return None

def match_from_fotmob(row,tid):
    if not isinstance(row,dict):return None
    status=row.get('status') or {}
    if status.get('finished') is not True and row.get('resultString') not in ('W','D','L'):return None
    h=row.get('home') or {}
    a=row.get('away') or {}
    if not isinstance(h,dict) or not isinstance(a,dict):return None
    side=None
    if str(h.get('id'))==str(tid) or h.get('isOurTeam') is True:side='home'
    elif str(a.get('id'))==str(tid) or a.get('isOurTeam') is True:side='away'
    if not side:return None
    when=status.get('utcTime') or (row.get('date') or {}).get('utcTime') if isinstance(row.get('date'),dict) else status.get('utcTime')
    when=when or row.get('utcTime')
    start=utc_ts(when)
    if not start or start>=int(NOW.timestamp()):return None
    scores=score(row)
    if scores is None:return None
    own_home=side=='home'
    gf,ga=scores if own_home else (scores[1],scores[0])
    opp=a.get('name') if own_home else h.get('name')
    if not opp:return None
    return {'ts':start,'day':datetime.fromtimestamp(start,timezone.utc).date().isoformat(),
            'opponent':str(opp)[:90],'venue':'Casa' if own_home else 'Fora',
            'score':str(scores[0])+'-'+str(scores[1]),'gf':gf,'ga':ga,
            'result':'V' if gf>ga else 'E' if gf==ga else 'D',
            'league':str(row.get('leagueName') or row.get('tournamentName') or '')[:70]}

def team_matches(doc,tid):
    fixture=(doc.get('fixtures') or {})
    allf=(fixture.get('allFixtures') or {}) if isinstance(fixture,dict) else {}
    candidates=(allf.get('fixtures') or []) if isinstance(allf,dict) else []
    if isinstance(candidates,dict):candidates=candidates.get('fixtures') or []
    overview=doc.get('overview') or {}
    recent=overview.get('teamForm') or overview.get('form') or []
    if isinstance(recent,dict):recent=recent.get('matches') or []
    games=[]
    for raw in list(candidates)[:350]+list(recent)[:30]:
        parsed=match_from_fotmob(raw,tid)
        if parsed:games.append(parsed)
    # times jogam partidas em várias ligas; mesma partida nunca deve ser contada 2 vezes.
    unique={(p['ts'],p['opponent'],p['score']):p for p in games}
    return sorted(unique.values(),key=lambda p:p['ts'],reverse=True)[:80]

def roster(doc):
    raw=doc.get('squad') or {}
    groups=raw.get('squad') if isinstance(raw,dict) else raw
    if not isinstance(groups,list):return []
    out=[]
    for group in groups:
        if not isinstance(group,dict):continue
        label=str(group.get('title') or group.get('name') or 'Jogadores')[:45]
        players=[]
        for item in group.get('members') or []:
            if not isinstance(item,dict) or not item.get('name'):continue
            players.append({'name':str(item['name'])[:80],
              'number':str(item.get('shirtNumber') or '')[:4]})
        if players:out.append({'section':label,'players':players[:24]})
    return out[:7]

def fetch_team(tid):
    url='https://www.fotmob.com/api/data/teams?'+urlencode({'id':tid})
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; NEXUS/6.0)',
                              'Accept':'application/json','Referer':'https://www.fotmob.com/'})
    with urlopen(req,timeout=9) as res:
        raw=res.read(4_500_001)
    if len(raw)>4_500_000:raise ValueError('resposta FotMob muito grande')
    doc=json.loads(raw)
    if not isinstance(doc,dict):raise ValueError('Resposta FotMob inválida')
    return {'updated_at':NOW.isoformat(),'games':team_matches(doc,tid),'roster':roster(doc)}

def recent_games(items,start_ts):
    try:cutoff=int(start_ts)
    except (ValueError,TypeError):return []
    return [x for x in items if isinstance(x,dict) and int(x.get('ts') or 0)<cutoff][:10]

def main():
    base=datetime.strptime(DAY,'%Y-%m-%d').date()
    days=[(base-timedelta(days=i)).isoformat() for i in range(3)]
    docs={d:read(HISTORY/(d+'.json')) for d in days}
    tasks={}
    for day,doc in docs.items():
        for key,row in (doc.get('matches') or {}).items():
            fixture=row.get('fixture') or {}
            if not str(key).startswith('fotmob-'):continue
            if not fixture.get('start_timestamp'):continue
            for side in ('home','away'):
                tid=team_id(fixture,side)
                if not tid:continue
                prio=0 if fixture.get('phase')=='live' else 1 if fixture.get('phase')=='scheduled' else 2
                tasks.setdefault(tid,[]).append((prio,day,key,side))
    cache=read(CACHE_FILE).get('teams') or {}
    if not isinstance(cache,dict):cache={}
    ordered=sorted(tasks,key=lambda t:(min(x[0] for x in tasks[t]),t))
    refresh=[]
    for tid in ordered:
        entry=cache.get(tid) or {}
        updated=entry.get('updated_at')
        fresh=False
        if updated:
            try:
                dt=datetime.fromisoformat(str(updated).replace('Z','+00:00'))
                fresh=dt.tzinfo is not None and (NOW-dt).total_seconds()<TTL_HOURS*3600
            except ValueError:pass
        if not fresh:refresh.append(tid)
    refresh=refresh[:LIMIT_PER_RUN]
    status={'updated_at':NOW.isoformat(),'teams_discovered':len(tasks),
            'team_requests':len(refresh),'requests_succeeded':0,
            'games_with_form':0,'teams_with_10':0,'roster_teams':0,'errors':[]}
    with ThreadPoolExecutor(max_workers=8) as pool:
        future={pool.submit(fetch_team,tid):tid for tid in refresh}
        for done in as_completed(future):
            tid=future[done]
            try:
                value=done.result()
                cache[tid]=value
                status['requests_succeeded']+=1
            except Exception as err:
                if len(status['errors'])<12:
                    status['errors'].append(tid+': '+str(err)[:120])
    for tid,targets in tasks.items():
        entry=cache.get(tid) or {}
        games=entry.get('games') or []
        players=entry.get('roster') or []
        for prio,day,key,side in targets:
            row=(docs[day].get('matches') or {}).get(key)
            if not row:continue
            cutoff=row['fixture'].get('start_timestamp')
            result=summarise(recent_games(games,cutoff),'FotMob · resultados anteriores')
            old=(row.get('team_form') or {}).get(side) or {}
            if result['available']>int(old.get('available') or 0):
                row.setdefault('team_form',{})[side]=result
            if players:
                row.setdefault('team_roster',{})[side]=players
    for day,doc in docs.items():
        for row in (doc.get('matches') or {}).values():
            forms=row.get('team_form') or {}
            if forms.get('home',{}).get('available') or forms.get('away',{}).get('available'):
                status['games_with_form']+=1
            status['teams_with_10']+=sum((forms.get(k) or {}).get('available')==10 for k in ('home','away'))
            status['roster_teams']+=sum(bool((row.get('team_roster') or {}).get(k)) for k in ('home','away'))
        if doc:write(HISTORY/(day+'.json'),doc)
    # Cache nao carrega respostas brutas da API; apenas lista esportiva resumida.
    write(CACHE_FILE,{'updated_at':NOW.isoformat(),'teams':
        {tid:value for tid,value in cache.items() if tid in tasks}})
    write(STATUS_FILE,status)
    print(json.dumps(status,ensure_ascii=False))
if __name__=='__main__':main()
