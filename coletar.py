#!/usr/bin/env python3
"""Coletor público e periódico para GitHub Actions; sem tokens ou odds inventadas."""
import json, re, sys, time, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from scout_snapshots import append_snapshot
from activity_timeline import observed_activity
from live_momentum import momentum_diagnostic, momentum_shape

HOME=Path(__file__).resolve().parent
HISTORY=HOME/'history'
BR=timezone(timedelta(hours=-3))
NOW=datetime.now(timezone.utc)
DAY=NOW.astimezone(BR).date().isoformat()
DEADLINE=time.monotonic()+73
LIVE_MODE=os.getenv('NEXUS_MODE','').lower()=='live'
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
    params=urlencode({'date':day.replace('-','')})
    obj=None
    errors=[]
    # Desde 2026 o FotMob tambem usa o caminho /api/data; tentar primeiro.
    for endpoint in ('https://www.fotmob.com/api/data/matches?',
                     'https://www.fotmob.com/api/matches?'):
        try:
            obj=fetch(endpoint+params,timeout=7)
            if isinstance(obj.get('leagues'),list):break
            obj=None
        except Exception as exc:
            errors.append(type(exc).__name__+': '+str(exc)[:80])
    if obj is None:
        raise ValueError('Fontes FotMob sem JSON de partidas: '+', '.join(errors)[:160])
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
                'source':'FotMob','start_timestamp':utc_ts(status.get('utcTime') or event.get('time')),
                'home_id':str(home.get('id') or ''),'away_id':str(away.get('id') or ''),
                'league_id':str(league.get('id') or ''),
                'collected_at':NOW.isoformat(),
                'home_logo':('https://images.fotmob.com/image_resources/logo/teamlogo/'+str(home['id'])+'.png')
                    if str(home.get('id') or '').isdigit() else '',
                'away_logo':('https://images.fotmob.com/image_resources/logo/teamlogo/'+str(away['id'])+'.png')
                    if str(away.get('id') or '').isdigit() else ''})
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
    """Interface legada: retorna apenas observacoes reais do provedor."""
    return momentum_diagnostic(detail)['points']

def stats(detail):
    packet=(((detail.get('content') or {}).get('stats') or {}).get('Periods') or {}).get('All') or {}
    alias={'big chances':'big_chances','shots on target':'shots_on','shots off target':'shots_off',
           'total shots':'shots_total','shots':'shots_total','total shot':'shots_total',
           'corner kicks':'corners','corners':'corners','dangerous attacks':'dangerous_attacks',
           'ball possession':'possession','possession':'possession','expected goals (xg)':'xg',
           'expected goals':'xg','xg':'xg','fouls':'fouls','fouls committed':'fouls',
           'yellow cards':'yellow_cards','red cards':'red_cards','offsides':'offsides',
           'saves':'saves','total passes':'passes','passes':'passes','accurate passes':'accurate_passes'}
    out={'home':{},'away':{}}
    for group in packet.get('stats') or []:
        for item in group.get('stats') or []:
            title=str(item.get('title') or '').strip().lower()
            key=alias.get(title)
            values=item.get('stats')
            if key and isinstance(values,list) and len(values)==2:
                for i,side in enumerate(('home','away')):
                    try:out[side][key]=float(str(values[i]).replace('%','').replace(',','.'))
                    except (TypeError,ValueError):pass
    return out

def fotmob_events(detail):
    """Eventos realmente reportados por matchFacts e shotmap, sem inferir stats."""
    content=detail.get('content') or {}
    general=detail.get('general') or {}
    home_id=str((general.get('homeTeam') or {}).get('id') or '')
    away_id=str((general.get('awayTeam') or {}).get('id') or '')
    found={}
    def insert(minute,kind,side,text):
        try:m=int(minute)
        except (ValueError,TypeError):return
        if not 0<=m<=130:return
        if side not in ('home','away'):side=''
        label=str(text or '')[:125]
        key=(m,kind,side,label)
        found[key]={'minute':m,'type':kind,'side':side,'text':label}
    raw=(content.get('matchFacts') or {}).get('events') or {}
    listed=raw.get('events') if isinstance(raw,dict) else raw
    if not isinstance(listed,list):listed=[]
    for event in listed:
        if not isinstance(event,dict):continue
        typ=str(event.get('type') or '').lower().replace(' ','')
        card=str(event.get('card') or event.get('cardType') or '').lower()
        if 'penalty' in typ and ('miss' in typ or 'saved' in typ):kind='penalty_missed'
        elif 'goal' in typ and 'disallow' not in typ:kind='goal'
        elif 'red' in typ or 'red' in card:kind='red_card'
        elif 'yellow' in typ or 'yellow' in card:kind='yellow_card'
        else:continue
        side='home' if event.get('isHome') is True else 'away' if event.get('isHome') is False else ''
        raw_min=event.get('time') or event.get('timeStr') or ''
        if isinstance(raw_min,str):
            match=re.search(r'\d{1,3}',raw_min)
            raw_min=match.group(0) if match else None
        player=(event.get('player') or {}).get('name') if isinstance(event.get('player'),dict) else ''
        insert(raw_min,kind,side,event.get('nameStr') or player or event.get('text') or '')
    shots=(content.get('shotmap') or {}).get('shots') or []
    for shot in shots[:140]:
        if not isinstance(shot,dict):continue
        event_type=str(shot.get('eventType') or '').lower()
        if 'goal' in event_type or shot.get('isOwnGoal'):continue
        if shot.get('isBlocked') is True:continue
        if shot.get('isOnTarget') is True:kind='shot_on'
        elif shot.get('isOnTarget') is False and any(
                name in event_type for name in ('miss','offtarget','offtarget','wide')):
            kind='shot_off'
        else:continue
        tid=str(shot.get('teamId') or '')
        side='home' if tid and tid==home_id else 'away' if tid and tid==away_id else ''
        # Nunca atribuir lance ao mandante quando a equipe não foi confirmada.
        if not side:continue
        # A grande chance desperdiçada é um único chute, não dois ícones.
        big=shot.get('isBigChance') is True or shot.get('bigChance') is True
        if big and kind=='shot_off':kind='big_chance_missed'
        insert(shot.get('min'),kind,side,shot.get('playerName') or '')
    return sorted(found.values(),key=lambda e:(e['minute'],e['type']))[:150]

def fotmob_lineups(detail):
    content=detail.get('content') or {}
    raw=content.get('lineup') or {}
    if not isinstance(raw,dict):return {}
    output={}
    lineup_type=str(raw.get('lineupType') or '').strip().lower()
    confirmed=lineup_type in ('standard','confirmed','official','actual','starting')
    for side,key in (('home','homeTeam'),('away','awayTeam')):
        team=raw.get(key) or {}
        if not isinstance(team,dict):continue
        def players(items):
            if not isinstance(items,list):return []
            out=[]
            for v in items[:25]:
                if not isinstance(v,dict) or not v.get('name'):continue
                out.append({'name':str(v['name'])[:80],
                            'number':str(v.get('shirtNumber') or '')[:4]})
            return out
        starters=players(team.get('starters'))
        subs=players(team.get('subs'))
        if starters or subs:
            output[side]={'formation':str(team.get('formation') or '')[:25],
                          'starters':starters,'subs':subs,'source':'FotMob',
                          'lineup_type':str(raw.get('lineupType') or '')[:25],
                          'status':'confirmed' if confirmed else 'predicted',
                          'updated_at':NOW.isoformat()}
    return output

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
            'live_found':0,'details_collected':0,'thermometers_saved':0,
            'scout_snapshots_saved':0,'momentum_unavailable':0,
            'momentum_status_counts':{},'momentum_shape_counts':{},
            'stats_detail_available':0,'activity_games':0,'activity_events':0,'errors':[]}
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
    # Completa eventos de jogos recentes que ja tiveram termometro registrado,
    # mesmo se a partida terminou entre duas coletas horarias.
    recent_with_pressure=[g for g in games if g.get('phase')=='finished' and
        (fixtures.get(g['id']) or {}).get('thermometer',{}).get('points') and
        not (fixtures.get(g['id']) or {}).get('events')]
    extra=sorted(recent_with_pressure,key=lambda g:g.get('start_timestamp') or 0,reverse=True)[:2]
    # Coleta de scouts em ciclos de dez minutos: alterna jogos por hora
    # da última verificação; não deixa os mesmos três fixos para sempre.
    def last_capture(game):
        old=fixtures.get(game['id']) or {}
        obs=old.get('observations') or []
        return str((obs[-1] or {}).get('at') or '') if obs else ''
    rotating=sorted(live,key=lambda g:(last_capture(g),-int(g.get('minute') or 0)))
    chosen=rotating[:(10 if LIVE_MODE else 6)]
    details_to_check=chosen+([] if LIVE_MODE else [
        g for g in extra if g['id'] not in {x['id'] for x in chosen}])
    status['live_detail_candidates']=len(live)
    status['live_detail_selected']=len(chosen)
    for match in details_to_check:
        if time.monotonic()>DEADLINE:break
        if not match['id'].startswith('fotmob-'):continue
        try:
            mid=match['id'].split('-',1)[1]
            # FotoMob mudou a rota de detalhes para /api/data/matchDetails.
            # Preserva fallback para o endpoint anterior, sem dados inventados.
            packet=None
            for url in ('https://www.fotmob.com/api/data/matchDetails?',
                        'https://www.fotmob.com/api/matchDetails?'):
                try:
                    packet=fetch(url+urlencode({'matchId':mid}),timeout=7)
                    break
                except Exception:
                    continue
            if packet is None:raise ValueError('FotMob detalhes indisponiveis')
            before=fixtures.get(match['id']) or {}
            diagnosis=momentum_diagnostic(packet)
            points=diagnosis['points']
            status['momentum_status_counts'][diagnosis['state']]=(
                status['momentum_status_counts'].get(diagnosis['state'],0)+1)
            if not points:status['momentum_unavailable']+=1
            if diagnosis['state']=='unsupported_shape':
                signature=momentum_shape(packet)
                status['momentum_shape_counts'][signature]=(
                    status['momentum_shape_counts'].get(signature,0)+1)
            before['momentum_diagnostic']={'state':diagnosis['state'],
                'source_path':diagnosis['source_path'], 'checked_at':NOW.isoformat()}
            before['thermometer']={'points':merge((before.get('thermometer') or {}).get('points') or [],points)}
            if points:before['pressure_updated_at']=NOW.isoformat()
            current_stats=stats(packet)
            if any(current_stats.values()):status['stats_detail_available']+=1
            if match.get('phase')=='live':
                before['scout_snapshots']=append_snapshot(
                    before.get('scout_snapshots'),current_stats,
                    match.get('minute'),NOW.isoformat(),'FotMob')
            if any(current_stats.values()):
                old_stats=before.get('stats') or {}
                before['stats']={side:{**(old_stats.get(side) or {}),
                    **(current_stats.get(side) or {})} for side in ('home','away')}
                before['stats_updated_at']=NOW.isoformat()
                before['stats_source']='FotMob'
            new_events=fotmob_events(packet)
            if new_events:
                prior=before.get('events') or []
                unique={(e['minute'],e['type'],e.get('side',''),e.get('text','')):e
                        for e in prior+new_events if isinstance(e,dict) and e.get('minute') is not None}
                before['events']=sorted(unique.values(),key=lambda e:e['minute'])[-150:]
            lineups=fotmob_lineups(packet)
            if lineups:before['lineups']={**(before.get('lineups') or {}),**lineups}
            observations=before.get('observations') or []
            observations.append({'at':NOW.isoformat(),'minute':match['minute'],'score':match['score'],'samples':len(points)})
            before['observations']=observations[-72:]
            fixtures[match['id']]=before
            status['details_collected']+=1
            if before['thermometer']['points']:status['thermometers_saved']+=1
            if before.get('scout_snapshots'):status['scout_snapshots_saved']+=1
            activity=observed_activity(before.get('events'))
            if activity['total_events']:
                status['activity_games']+=1
                status['activity_events']+=activity['total_events']
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
