#!/usr/bin/env python3
"""Coletor público e periódico para GitHub Actions; sem tokens ou odds inventadas."""
import json, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HOME=Path(__file__).resolve().parent
HISTORY=HOME/'history'
BR=timezone(timedelta(hours=-3))
NOW=datetime.now(timezone.utc)
DAY=NOW.astimezone(BR).date().isoformat()
DEADLINE=time.monotonic()+73
LEAGUES=('bra.1','bra.2','eng.1','esp.1','ita.1','ger.1','fra.1','arg.1','usa.1','col.1','uefa.champions','conmebol.libertadores')

def fetch(url,timeout=7):
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; NEXUS/5.27)','Accept':'application/json','Referer':'https://www.fotmob.com/'})
    with urlopen(req,timeout=timeout) as resp:raw=resp.read(3_000_001)
    if len(raw)>3_000_000:raise ValueError('Resposta acima do limite')
    obj=json.loads(raw)
    if not isinstance(obj,dict):raise ValueError('Resposta inválida')
    return obj

def safe_int(v):
    try:return int(v) if v is not None and v!='' else None
    except (ValueError,TypeError):return None

def utc_ts(value):
    try:
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if dt.tzinfo is not None:return int(dt.timestamp())
    except (TypeError,ValueError):pass
    return None

def fotmob_list(day):
    obj=fetch('https://www.fotmob.com/api/matches?'+urlencode({'date':day.replace('-','')}))
    out=[]
    for league in obj.get('leagues') or []:
        for event in league.get('matches') or []:
            status=event.get('status') or {}
            if status.get('cancelled'):continue
            home,away=event.get('home') or {},event.get('away') or {}
            mid=str(event.get('id') or '')
            if not mid.isdigit() or not home.get('name') or not away.get('name'):continue
            live=bool(status.get('started')) and not bool(status.get('finished'))
            finished=bool(status.get('finished'))
            clock=str((status.get('liveTime') or {}).get('short') or '')
            found=re.search(r'(?<!\d)(\d{1,3})(?:\+\d+)?[\'′ ]?',clock)
            minute=int(found.group(1)) if live and found else 0
            scores=[safe_int(home.get('score')),safe_int(away.get('score'))]
            out.append({'id':'fotmob-'+mid,'home':home['name'],'away':away['name'],
                'league':str(league.get('name') or ''),'minute':minute,'live':live,
                'phase':'finished' if finished else 'live' if live else 'scheduled',
                'score':'-'.join(str(v) if v is not None else '?' for v in scores),
                'source':'FotMob','start_timestamp':utc_ts(status.get('utcTime') or event.get('time')),'collected_at':NOW.isoformat()})
    return out

def espn_league(code):
    url='https://site.api.espn.com/apis/site/v2/sports/soccer/'+code+'/scoreboard?'+urlencode({'dates':DAY.replace('-',''),'limit':'60'})
    obj=fetch(url,timeout=5)
    out=[]
    for event in obj.get('events') or []:
        competitions=event.get('competitions') or []
        teams=(competitions[0].get('competitors') or []) if competitions else []
        h=next((t for t in teams if t.get('homeAway')=='home'),None)
        a=next((t for t in teams if t.get('homeAway')=='away'),None)
        if not h or not a:continue
        status=event.get('status') or {}
        state=str((status.get('type') or {}).get('state') or '').lower()
        live=state in ('in','inprogress')
        found=re.search(r'^(\d{1,3})',str(status.get('displayClock') or ''))
        minute=int(found.group(1)) if live and found else 0
        out.append({'id':'espn-'+code+'-'+str(event.get('id')),
            'home':(h.get('team') or {}).get('displayName',''),
            'away':(a.get('team') or {}).get('displayName',''),
            'league':code,'minute':minute,'live':live,
            'phase':'live' if live else 'finished' if state=='post' else 'scheduled',
            'score':str(h.get('score','?'))+'-'+str(a.get('score','?')),
            'source':'ESPN','start_timestamp':utc_ts(event.get('date')),'collected_at':NOW.isoformat()})
    return out

def momentum(detail):
    content=detail.get('content') or {}
    candidates=[(content.get('matchFacts') or {}).get('momentum'),content.get('momentum')]
    for item in candidates:
        if not isinstance(item,dict):continue
        main=item.get('main') or {}
        values=main.get('data') if isinstance(main,dict) else None
        if values is None:values=item.get('data')
        if not isinstance(values,list):continue
        found={}
        for p in values:
            try:
                minute=int(p['minute']);value=float(p['value'])
                if 1<=minute<=150 and -1000<=value<=1000:
                    found[minute]={'minute':minute,'value':value}
            except (TypeError,ValueError,KeyError,OverflowError):continue
        if found:return [found[k] for k in sorted(found)]
    return []

def stats(detail):
    packet=(((detail.get('content') or {}).get('stats') or {}).get('Periods') or {}).get('All') or {}
    alias={'big chances':'big_chances','shots on target':'shots_on','shots off target':'shots_off',
           'corner kicks':'corners','dangerous attacks':'dangerous_attacks'}
    out={'home':{},'away':{}}
    for group in packet.get('stats') or []:
        for item in group.get('stats') or []:
            key=alias.get(str(item.get('title') or '').lower())
            values=item.get('stats')
            if key and isinstance(values,list) and len(values)==2:
                for i,side in enumerate(('home','away')):
                    try:out[side][key]=float(str(values[i]).replace('%','').replace(',','.'))
                    except (TypeError,ValueError):pass
    return out

def read(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),sort_keys=True)+'\n',encoding='utf-8')
    temp.replace(path)

def merge(old,new):
    observed={int(p['minute']):p for p in old if isinstance(p,dict) and safe_int(p.get('minute'))}
    for p in new:
        if isinstance(p,dict) and safe_int(p.get('minute')):observed[int(p['minute'])]=p
    return [observed[k] for k in sorted(observed)]

def run():
    HISTORY.mkdir(exist_ok=True)
    file=HISTORY/(DAY+'.json')
    old=read(file)
    fixtures=old.get('matches') if isinstance(old.get('matches'),dict) else {}
    status={'updated_at':NOW.isoformat(),'day':DAY,'ok':False,'sources':[],
            'live_found':0,'details_collected':0,'thermometers_saved':0,'errors':[]}
    games=[]
    try:
        games=fotmob_list(DAY)
        status['sources'].append('FotMob')
    except Exception as exc:
        status['errors'].append('FotMob: '+str(exc)[:140])
    if not games:
        with ThreadPoolExecutor(max_workers=8) as pool:
            future=[pool.submit(espn_league,code) for code in LEAGUES]
            for result in as_completed(future):
                try:games.extend(result.result())
                except Exception:pass
        if games:status['sources'].append('ESPN')
    for game in games:
        key=game['id'];before=fixtures.get(key) or {}
        before['fixture']=game;fixtures[key]=before
    live=sorted((g for g in games if g['live']),key=lambda g:
        (0 if re.search(r'brasil|brazil|serie a|premier',str(g['league']),re.I) else 1,-g['minute']))
    status['live_found']=len(live)
    for match in live[:3]:
        if time.monotonic()>DEADLINE:break
        if not match['id'].startswith('fotmob-'):continue
        try:
            mid=match['id'].split('-',1)[1]
            packet=fetch('https://www.fotmob.com/api/matchDetails?'+urlencode({'matchId':mid}),timeout=7)
            before=fixtures.get(match['id']) or {}
            points=momentum(packet)
            before['thermometer']={'points':merge((before.get('thermometer') or {}).get('points') or [],points)}
            current_stats=stats(packet)
            if any(current_stats.values()):before['stats']=current_stats
            observations=before.get('observations') or []
            observations.append({'at':NOW.isoformat(),'minute':match['minute'],'score':match['score'],'samples':len(points)})
            before['observations']=observations[-72:]
            fixtures[match['id']]=before
            status['details_collected']+=1
            if before['thermometer']['points']:status['thermometers_saved']+=1
        except Exception as exc:
            status['errors'].append('Detalhe '+match['id']+': '+str(exc)[:130])
    write(file,{'day':DAY,'updated_at':NOW.isoformat(),'matches':fixtures})
    status['ok']=bool(status['sources'])
    for path in HISTORY.glob('20??-??-??.json'):
        try:
            if (NOW.astimezone(BR).date()-datetime.strptime(path.stem,'%Y-%m-%d').date()).days>30:
                path.unlink()
        except ValueError:pass
    write(HISTORY/'status.json',status)
    print(json.dumps(status,ensure_ascii=False,indent=2))
    return 0 if status['ok'] else 1

if __name__=='__main__':sys.exit(run())
