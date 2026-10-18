#!/usr/bin/env python3
"""Complementa o NEXUS com as partidas ESPN de hoje e dos 2 dias anteriores.

Sem odds retroativas, sem pressão fabricada e sem repetições de jogos.
Os detalhes ESPN podem não conter todos os scouts/eventos; campos ausentes ficam ausentes.
"""
import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from urllib.parse import urlencode
from coletar import (HISTORY, DAY, BR, NOW, LEAGUES, fetch, read, write, safe_int, utc_ts)

DETAIL_LIMIT_SECONDS = 77
DEADLINE = time.monotonic() + DETAIL_LIMIT_SECONDS
ALIASES = {
    'shotsontarget':'shots_on', 'ontargetshots':'shots_on', 'shotsongoal':'shots_on',
    'shotsongoal':'shots_on', 'shotsongoal':'shots_on',
    'shotsofftarget':'shots_off', 'offtargetshots':'shots_off',
    'totalshots':'shots_total', 'shots':'shots_total', 'shotattempts':'shots_total',
    'cornerkicks':'corners', 'corners':'corners',
    'fouls':'fouls', 'foulscommitted':'fouls', 'yellowcards':'yellow_cards',
    'redcards':'red_cards', 'offsides':'offsides', 'saves':'saves',
    'goalkeepersaves':'saves', 'possession':'possession', 'possessionpct':'possession',
    'ballpossession':'possession', 'expectedgoals':'xg', 'xg':'xg',
    'bigchances':'big_chances', 'dangerousattacks':'dangerous_attacks',
    'passes':'passes', 'totalpasses':'passes', 'passaccuracy':'pass_accuracy',
}
def norm(s):
    return re.sub(r'[^a-z0-9]', '', str(s or '').lower())
def numeric(s):
    if s is None or s == '': return None
    try:
        if isinstance(s,dict): s=s.get('displayValue',s.get('value'))
        v=float(str(s).replace('%','').replace(',','.'))
        return v if math.isfinite(v) and abs(v)<100000 else None
    except (TypeError,ValueError,OverflowError): return None
def teams_from_comp(comp):
    pairs=comp.get('competitors') or []
    home=next((t for t in pairs if t.get('homeAway')=='home'),{})
    away=next((t for t in pairs if t.get('homeAway')=='away'),{})
    return home,away
def official_logo(team):
    """Aceita apenas logotipo explicitamente fornecido pela ESPN."""
    for item in (team.get('logos') or []):
        url=item.get('href') if isinstance(item,dict) else ''
        if isinstance(url,str) and url.startswith(('https://a.espncdn.com/','https://a1.espncdn.com/')):
            return url[:300]
    # URL oficial da ESPN baseada no ID autenticado do time; se ausente ou quebrada
    # o frontend mostra iniciais e nao inventa outro escudo.
    team_id=str(team.get('id') or '')
    if team_id.isdigit() and 1<=len(team_id)<=12:
        return 'https://a.espncdn.com/i/teamlogos/soccer/500/'+team_id+'.png'
    return ''

def parse_fixture(event,league):
    comp=(event.get('competitions') or [{}])[0]
    h,a=teams_from_comp(comp)
    hn=(h.get('team') or {}).get('displayName') or ''
    an=(a.get('team') or {}).get('displayName') or ''
    if not hn or not an: return None
    state=str(((event.get('status') or {}).get('type') or {}).get('state') or '').lower()
    if state not in ('pre','in','post','inprogress'):return None
    live=state in ('in','inprogress')
    clock=str((event.get('status') or {}).get('displayClock') or '')
    m=re.match(r'^(\d{1,3})',clock)
    stadium=(comp.get('venue') or {}).get('fullName') or ''
    rank=comp.get('round') or event.get('round') or {}
    if isinstance(rank,dict): rank=rank.get('displayValue') or rank.get('number')
    return {
        'id':'espn-'+league+'-'+str(event.get('id') or ''),'home':hn,'away':an,
        'league':str(((event.get('league') or {}).get('name')) or league),
        'league_code':league,'minute':int(m.group(1)) if live and m else 0,
        'live':live,'phase':'live' if live else 'finished' if state=='post' else 'scheduled',
        'score':str(h.get('score','?'))+'-'+str(a.get('score','?')),
        'source':'ESPN','start_timestamp':utc_ts(event.get('date')),
        'collected_at':NOW.isoformat(),'venue':str(stadium)[:120],
        'round':str(rank or '')[:80],
        'home_id':str((h.get('team') or {}).get('id') or ''),
        'away_id':str((a.get('team') or {}).get('id') or ''),
        'home_logo':official_logo(h.get('team') or {}),
        'away_logo':official_logo(a.get('team') or {})
    }
def scoreboard(league,day):
    url='https://site.api.espn.com/apis/site/v2/sports/soccer/'+league+'/scoreboard?'+urlencode({'dates':day.replace('-',''),'limit':100})
    doc=fetch(url,timeout=6)
    return [f for x in doc.get('events') or [] if (f:=parse_fixture(x,league))]
def extract_stats(packet):
    out={'home':{},'away':{}}
    box=packet.get('boxscore') or {}
    teams=box.get('teams') or []
    for i,team in enumerate(teams):
        side=team.get('homeAway')
        if side not in ('home','away'):
            side='home' if i==0 else 'away'
        entries=team.get('statistics') or team.get('stats') or []
        if isinstance(entries,dict):
            entries=[{'name':k,'displayValue':v} for k,v in entries.items()]
        for v in entries:
            if not isinstance(v,dict):continue
            key=ALIASES.get(norm(v.get('name') or v.get('label') or v.get('abbreviation')))
            number=numeric(v.get('displayValue',v.get('value')))
            if key and number is not None:out[side][key]=number
    return out
def extract_events(packet):
    # Eventos pontuais reais da ESPN; não representam pressão minuto a minuto.
    events=[]
    rows=[]
    for key in ('keyEvents','plays','scoringPlays'):
        value=packet.get(key)
        if isinstance(value,list):rows.extend(value)
    if not rows:
        box=packet.get('header') or {}
        rows=box.get('details') or []
    for e in rows:
        if not isinstance(e,dict):continue
        name=str(((e.get('type') or {}).get('text')) or e.get('type') or e.get('text') or e.get('shortText') or '').lower()
        description=str(e.get('text') or e.get('shortText') or '')[:150]
        players=e.get('participants') or []
        athlete=''
        if isinstance(players,list):
            for participant in players:
                if not isinstance(participant,dict):continue
                athlete=str((participant.get('athlete') or {}).get('displayName') or
                            (participant.get('athlete') or {}).get('fullName') or '')[:90]
                if athlete:break
        flag=norm(name+' '+description)
        if any(k in flag for k in ('missedpenalty','penaltymissed')):kind='penalty_missed'
        elif 'redcard' in flag:kind='red_card'
        elif 'yellowcard' in flag:kind='yellow_card'
        elif any(k in flag for k in ('goal','scored')) and not any(k in flag for k in ('goalkeeper','goalkick','owngoaldisallowed')):kind='goal'
        elif 'shot' in flag and any(k in flag for k in ('offtarget','wide','blocked')):kind='shot_off'
        elif 'shot' in flag and any(k in flag for k in ('ontarget','saved')):kind='shot_on'
        else:continue
        clock=e.get('clock') or {}
        minute=safe_int(clock.get('value') or str(clock.get('displayValue') or '').split(':')[0])
        if minute is None:
            match=re.search(r'(\d{1,3})[\'′]',description)
            minute=int(match.group(1)) if match else None
        if minute is None or not 0<=minute<=130:continue
        team=e.get('team') or {}
        side=e.get('homeAway')
        if side not in ('home','away'):
            side=team.get('homeAway') or ''
        events.append({'minute':minute,'type':kind,'side':side if side in ('home','away') else '',
                       'text':athlete or description,
                       'player':athlete if kind=='goal' else '',
                       'source':'ESPN'})
    # Não inferir time se informação não estiver disponível.
    unique={(e['minute'],e['type'],e['side'],e['text']):e for e in events}
    return sorted(unique.values(),key=lambda x:x['minute'])[:130]
def details(league,event_id):
    url='https://site.api.espn.com/apis/site/v2/sports/soccer/'+league+'/summary?'+urlencode({'event':event_id})
    packet=fetch(url,timeout=6)
    return extract_stats(packet),extract_events(packet)
def main():
    from datetime import date
    today=date.fromisoformat(DAY)
    days=[(today-timedelta(days=n)).isoformat() for n in range(3)]
    HISTORY.mkdir(exist_ok=True)
    documents={d:read(HISTORY/(d+'.json')) for d in days}
    sources={d:[] for d in days}
    status={'checked_at':NOW.isoformat(),'days':days,'games':0,'details':0,
            'with_stats':0,'events':0,'failed_leagues':0,'errors':[]}
    jobs=[]
    with ThreadPoolExecutor(max_workers=12) as pool:
        future={pool.submit(scoreboard,league,day):(league,day) for day in days for league in LEAGUES}
        for done in as_completed(future):
            league,day=future[done]
            try:
                sources[day].extend(done.result())
            except Exception as ex:
                status['failed_leagues']+=1
                if len(status['errors'])<8:status['errors'].append(league+'/'+day+': '+str(ex)[:100])
    for day in days:
        doc=documents[day]
        matches=doc.get('matches') if isinstance(doc.get('matches'),dict) else {}
        doc['matches']=matches
        for f in sources[day]:
            row=matches.setdefault(f['id'],{})
            before=row.get('fixture') or {}
            # Don't lose pregame quote signals or details.
            if before.get('phase')=='finished' and f['phase']!='finished':continue
            row['fixture']={**before,**f}
            has_stats=any((row.get('stats') or {}).get(k) for k in ('home','away'))
            goal_count=sum(1 for e in row.get('events') or [] if e.get('type')=='goal')
            scored=re.fullmatch(r'(\d+)\s*[-–:]\s*(\d+)',str(f.get('score') or ''))
            missing_goals=bool(scored) and int(scored[1])+int(scored[2])>goal_count
            if f['phase'] in ('finished','live') and (not has_stats or missing_goals):
                jobs.append((day,f['id'],row))
        doc['day']=day
        doc['updated_at']=NOW.isoformat()
        status['games']+=len(matches)
    # Limita chamadas e não atrasa o GitHub Actions.
    jobs.sort(key=lambda item: (0 if item[2]['fixture']['phase']=='live' else 1,
                                -int((item[2].get('fixture') or {}).get('start_timestamp') or 0)))
    jobs=jobs[:28]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={}
        for day,game_id,row in jobs:
            m=re.fullmatch(r'espn-([a-z0-9.]+)-(\d+)',game_id)
            if m:futures[pool.submit(details,m[1],m[2])]=(day,game_id)
        for done in as_completed(futures):
            if time.monotonic()>DEADLINE:break
            day,game_id=futures[done]
            try:
                stats,events=done.result()
            except Exception as ex:
                if len(status['errors'])<8:status['errors'].append('detail '+game_id+': '+str(ex)[:80])
                continue
            row=documents[day]['matches'][game_id]
            if stats.get('home') or stats.get('away'):
                old=row.get('stats') or {}
                row['stats']={key:{**(old.get(key) or {}),**stats[key]} for key in ('home','away')}
                status['with_stats']+=1
            if events:
                prior=row.get('events') or []
                combined={}
                for e in prior+events:
                    if not isinstance(e,dict):continue
                    key=(e.get('minute'),e.get('type'),e.get('side')) if e.get('type')=='goal' else (
                        e.get('minute'),e.get('type'),e.get('side'),e.get('text'))
                    previous=combined.get(key)
                    if not previous or (e.get('player') and not previous.get('player')):
                        combined[key]=e
                row['events']=sorted(combined.values(),key=lambda e:e.get('minute') or 0)[-130:]
                status['events']+=len(events)
            status['details']+=1
    for day in days:write(HISTORY/(day+'.json'),documents[day])
    write(HISTORY/'backfill_status.json',status)
    print(json.dumps(status,ensure_ascii=False))
if __name__=='__main__':main()
