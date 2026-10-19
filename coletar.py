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
DEADLINE=time.monotonic()+(105 if os.getenv('NEXUS_MODE','').lower()=='live' else 82)
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

def confirmed_halftime(status, active=True):
    """HT somente por status explícito do fornecedor, nunca só porque chegou aos 45'."""
    if not active or not isinstance(status,dict):
        return False
    objects=[status, status.get('liveTime') or {},status.get('reason') or {},
             status.get('type') or {}]
    raw=[]
    for obj in objects:
        if not isinstance(obj,dict):
            continue
        raw.extend(str(obj.get(key) or '').strip() for key in
                   ('short','shortDetail','description','name','detail','long','displayName','text'))
    return any(re.fullmatch(
        r'(?:STATUS[_ -]?)?(?:HT|HALF[_ -]?TIME|INTERVALO|INTERMISSION|'
        r'1ST[_ -]?HALF[_ -]?(?:ENDED|OVER)|FIRST[_ -]?HALF[_ -]?(?:ENDED|OVER))',
        item,re.I) for item in raw if item)


def canonical_league_ids(league):
    """FotMob matches[].leagues: id = edição/calendário, primaryId = campeonato.

    O endpoint /api/data/leagues?id= recebe o identificador canônico primaryId.
    Não confundir com o ID da edição, que pode mudar todo ano.
    """
    if not isinstance(league,dict):
        return '', ''
    season=str(league.get('id') or '')
    primary=str(league.get('primaryId') or '')
    if not primary.isdecimal() or int(primary)<=0:
        primary=season if season.isdecimal() and int(season)>0 else ''
    return primary, season


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
            ht=confirmed_halftime(status,live)
            found=re.search(r"(?<!\d)(\d{1,3})(?:\+\d+)?['′ ]?",clock)
            minute=int(found.group(1)) if live and found else 45 if ht else 0
            scores=[safe_int(home.get('score')),safe_int(away.get('score'))]
            canonical_id, edition_id=canonical_league_ids(league)
            out.append({'id':'fotmob-'+mid,'home':home['name'],'away':away['name'],
                'league':str(league.get('name') or ''),'minute':minute,'live':live,
                'round':str(event.get('tournamentStage') or '')[:30] if str(event.get('tournamentStage') or '').isdigit() else '',
                'phase':'finished' if finished else 'live' if live else 'scheduled',
                'halftime':ht,'status_short':'HT' if ht else '',
                'score':'-'.join(str(v) if v is not None else '?' for v in scores),
                'source':'FotMob','start_timestamp':utc_ts(status.get('utcTime') or event.get('time')),
                'home_id':str(home.get('id') or ''),'away_id':str(away.get('id') or ''),
                'league_id':canonical_id, 'league_edition_id':edition_id,
                'league_id_verified':str(league.get('primaryId') or '').isdecimal(),
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
        ht=confirmed_halftime(status,live)
        found=re.search(r'^(\d{1,3})',str(status.get('displayClock') or ''))
        minute=int(found.group(1)) if live and found else 45 if ht else 0
        out.append({'id':'espn-'+code+'-'+str(event.get('id')),
            'home':(h.get('team') or {}).get('displayName',''),
            'away':(a.get('team') or {}).get('displayName',''),
            'league':code,'minute':minute,'live':live,
            'phase':'live' if live else 'finished' if state=='post' else 'scheduled',
            'halftime':ht,'status_short':'HT' if ht else '',
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
    """Lances verificados, com autores extraídos de matchFacts e shotmap.

    Os dois feeds se complementam: shotmap pode identificar gols que não foram
    enviados no bloco matchFacts. Nunca inferir gol pelo placar nem contabilizar
    o mesmo gol duas vezes. Penaltis de desempate são excluídos.
    """
    content=detail.get('content') or {}
    general=detail.get('general') or {}
    home_id=str((general.get('homeTeam') or {}).get('id') or '')
    away_id=str((general.get('awayTeam') or {}).get('id') or '')
    found={}
    def name(value):
        if isinstance(value,dict):
            value=value.get('name') or value.get('fullName') or value.get('displayName')
        v=str(value or '').strip()[:100]
        return '' if v.casefold() in ('goal','gol','own goal','penalty','unknown','none') else v
    def insert(minute,kind,side,label,**extra):
        try:m=int(minute)
        except (ValueError,TypeError):return
        if not 0<=m<=130:return
        if side not in ('home','away'):side=''
        val=str(label or '')[:125]
        key=(m,kind,side,val)
        item={'minute':m,'type':kind,'side':side,'text':val}
        item.update({k:v for k,v in extra.items() if v is not None and v!=''})
        found[key]=item
    raw=(content.get('matchFacts') or {}).get('events') or {}
    listed=raw.get('events') if isinstance(raw,dict) else raw
    if not isinstance(listed,list):listed=[]
    for event in listed:
        if not isinstance(event,dict) or event.get('isPenaltyShootoutEvent') is True:continue
        typ=str(event.get('type') or '').lower().replace(' ','')
        card=str(event.get('card') or event.get('cardType') or '').lower()
        if 'substitution' in typ:
            swap=event.get('swap') or []
            if isinstance(swap,list) and len(swap)>=2 and all(isinstance(v,dict) for v in swap[:2]):
                entered=name(swap[0].get('name'))
                exited=name(swap[1].get('name'))
                side='home' if event.get('isHome') is True else 'away' if event.get('isHome') is False else ''
                raw_min=event.get('time')
                if entered and exited and side:
                    try:minute=int(raw_min)
                    except (ValueError,TypeError):continue
                    if 0<=minute<=130:
                        insert(minute,'substitution',side,entered+' ↔ '+exited,
                               player_in=entered,player_out=exited,source='FotMob · matchFacts')
            continue
        if 'penalty' in typ and ('miss' in typ or 'saved' in typ):kind='penalty_missed'
        elif 'goal' in typ and 'disallow' not in typ:kind='goal'
        elif 'red' in typ or 'red' in card:kind='red_card'
        elif 'yellow' in typ or 'yellow' in card:kind='yellow_card'
        else:continue
        side='home' if event.get('isHome') is True else 'away' if event.get('isHome') is False else ''
        raw_min=event.get('time') if event.get('time') is not None else event.get('timeStr')
        if isinstance(raw_min,str):
            match=re.search(r'\d{1,3}',raw_min)
            raw_min=match.group(0) if match else None
        if kind=='goal':
            player=name(event.get('player')) or name(event.get('nameStr'))
            assist=name(event.get('assist')) or name(event.get('assistPlayer'))
            own=bool(event.get('ownGoal')) or 'owngoal' in typ
            penalty='penalty' in str(event.get('goalDescription') or '').lower() or 'penalty' in typ
            insert(raw_min,kind,side,player or 'Autor não informado',
                   player=player,assist=assist,own_goal=own,penalty=penalty,
                   source='FotMob · matchFacts')
        else:
            player=name(event.get('player')) or name(event.get('nameStr'))
            insert(raw_min,kind,side,player or event.get('text') or '',
                   source='FotMob · matchFacts')
    shots=(content.get('shotmap') or {}).get('shots') or []
    for shot in shots[:200]:
        if not isinstance(shot,dict):continue
        typ=str(shot.get('eventType') or '').lower()
        tid=str(shot.get('teamId') or '')
        side='home' if tid and tid==home_id else 'away' if tid and tid==away_id else ''
        if not side:continue
        minute=shot.get('min')
        if 'goal' in typ or shot.get('isOwnGoal') is True:
            try:m=int(minute)
            except (ValueError,TypeError):continue
            player=name(shot.get('playerName'))
            own=shot.get('isOwnGoal') is True
            # FotMob atribui o teamId do chute ao time do atleta; autogol
            # credita o gol ao adversário, sem inventar autoria.
            credited='away' if own and side=='home' else 'home' if own else side
            matches=[k for k in found if k[0]==m and k[1]=='goal' and k[2]==credited]
            if matches:
                key=next((k for k in matches if found[k].get('player')),matches[0])
                existing=found[key]
                if not existing.get('player') and player:
                    # Completar autoria no mesmo gol, sem acrescentar outra ocorrência.
                    existing['text']=player
                    existing['player']=player
                    if key[3]!=player:
                        found.pop(key,None)
                        found[(m,'goal',credited,player)]=existing
                continue
            insert(m,'goal',credited,player or 'Autor não informado',
                   player=player,assist=name(shot.get('assistPlayerName')),
                   own_goal=own,penalty='penalty' in str(shot.get('situation') or '').lower(),
                   source='FotMob · shotmap')
            continue
        if shot.get('isBlocked') is True:continue
        if shot.get('isOnTarget') is True:kind='shot_on'
        elif shot.get('isOnTarget') is False and any(t in typ for t in ('miss','offtarget','wide')):
            kind='shot_off'
        else:continue
        big=shot.get('isBigChance') is True or shot.get('bigChance') is True
        if big and kind=='shot_off':kind='big_chance_missed'
        insert(minute,kind,side,name(shot.get('playerName')),source='FotMob · shotmap')
    return sorted(found.values(),key=lambda e:(e['minute'],e['type'],e['side']))[:180]


def merge_verified_events(previous,incoming):
    """Consolida gols do mesmo minuto e time sem contar duas fontes duas vezes."""
    output={}
    for e in list(previous or [])+list(incoming or []):
        if not isinstance(e,dict):continue
        minute=e.get('minute')
        try:minute=int(minute)
        except (ValueError,TypeError):continue
        if not 0<=minute<=130:continue
        kind=str(e.get('type') or '')
        side=str(e.get('side') or '')
        key=(minute,kind,side) if kind=='goal' else (
            minute,kind,side,str(e.get('text') or ''))
        old=output.get(key)
        if old is None:
            output[key]=dict(e)
            continue
        def quality(x):
            player=str(x.get('player') or '').strip()
            return (bool(player and player!='Autor não informado'),
                    bool(x.get('assist')),x.get('source')=='FotMob · matchFacts')
        if quality(e)>quality(old):
            combined={**old,**e}
            if not e.get('assist') and old.get('assist'):combined['assist']=old['assist']
            output[key]=combined
        elif not old.get('assist') and e.get('assist'):
            old['assist']=e['assist']
    return sorted(output.values(),key=lambda e:(e.get('minute') or 0,
                                                e.get('type') or '',e.get('side') or ''))[:180]


def fotmob_match_stars(detail):
    """Destaque declarado ou maior nota da partida; NÃO artilheiro da temporada."""
    c=detail.get('content') or {}
    facts=c.get('matchFacts') or {}
    general=detail.get('general') or {}
    home_id=str((general.get('homeTeam') or {}).get('id') or '')
    away_id=str((general.get('awayTeam') or {}).get('id') or '')
    answer={}
    pom=facts.get('playerOfTheMatch') or {}
    if isinstance(pom,dict):
        raw=pom.get('name')
        player=raw.get('fullName') or raw.get('name') if isinstance(raw,dict) else raw
        tid=str(pom.get('teamId') or '')
        side='home' if tid and tid==home_id else 'away' if tid and tid==away_id else None
        if side and player:
            answer[side]={'player':str(player)[:80],'kind':'player_of_match',
                          'label':'Melhor em campo (FotMob)','source':'FotMob'}
    lineup=c.get('lineup') or {}
    for side,key in (('home','homeTeam'),('away','awayTeam')):
        if side in answer:continue
        team=lineup.get(key) or {}
        if not isinstance(team,dict):continue
        candidates=[]
        for category in ('starters','subs'):
            for athlete in team.get(category) or []:
                if not isinstance(athlete,dict) or not athlete.get('name'):continue
                rating=(athlete.get('performance') or {}).get('rating')
                try:n=float(rating)
                except (TypeError,ValueError):continue
                if 0<=n<=10:candidates.append((n,str(athlete['name'])[:80]))
        if candidates:
            score,player=sorted(candidates,key=lambda x:(-x[0],x[1]))[0]
            answer[side]={'player':player,'kind':'match_rating','label':'Maior nota da partida',
                          'rating':round(score,2),'source':'FotMob'}
    return answer

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
                rating=(v.get('performance') or {}).get('rating')
                try: grade=float(rating)
                except (TypeError,ValueError): grade=None
                athlete={'name':str(v['name'])[:80],
                         'number':str(v.get('shirtNumber') or '')[:4],
                         'id':str(v.get('id') or '')[:16]}
                if grade is not None and 0<=grade<=10: athlete['rating']=round(grade,2)
                out.append(athlete)
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

def scout_priority(game,old):
    """Preferir scouts realmente observados sem inventar pressao ou ignorar jogos novos.

    Jogos que nunca foram consultados tem prioridade inicial. Fontes com scouts
    verificaveis merecem atualizacoes mais frequentes; sem dados entram no rodizio.
    """
    old=old if isinstance(old,dict) else {}
    minute=int(game.get('minute') or 0)
    diagnosis=(old.get('momentum_diagnostic') or {}).get('state')
    points=(old.get('thermometer') or {}).get('points') or []
    last_pressure=max((int(p.get('minute') or p.get('m') or 0)
                       for p in points if isinstance(p,dict)),default=0)
    observations=old.get('observations') or []
    last=str((observations[-1] or {}).get('at') or '') if observations else ''
    scouts=(old.get('stats') or {})
    measured=any(isinstance(scouts.get(side),dict) and
                 any(v is not None for v in scouts[side].values())
                 for side in ('home','away'))
    snapshots=bool(old.get('scout_snapshots'))
    if last_pressure and minute-last_pressure>=3: group=0
    elif not last:group=1
    elif measured or snapshots:group=2
    elif diagnosis=='not_provided':group=4
    else:group=3
    return (group,last,-minute)

def choose_scout_games(live,fixtures,limit):
    """Reservar vagas para rechecagem de jogos sem dados mesmo sob alta demanda.

    Nao muda nem inventa scouts: escolhe apenas quais detalhes consultar.
    """
    if limit<=0:return []
    def priority(game):
        return scout_priority(game,fixtures.get(game['id']) or {})
    ordered=sorted(live,key=priority)
    if len(ordered)<=limit:return ordered
    without=[g for g in ordered if priority(g)[0]==4]
    quota=min(len(without),max(1,limit//6))
    others=[g for g in ordered if priority(g)[0]!=4]
    picked=others[:limit-quota]+without[:quota]
    if len(picked)<limit:
        picked_ids={g['id'] for g in picked}
        picked.extend(g for g in ordered if g['id'] not in picked_ids)
    return picked[:limit]

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
    # Prioridade por qualidade dos scouts, com vagas reservadas para
    # rechecagens quando a fonte havia negado momentum anteriormente.
    chosen=choose_scout_games(live,fixtures,18 if LIVE_MODE else 12)
    details_to_check=chosen+([] if LIVE_MODE else [
        g for g in extra if g['id'] not in {x['id'] for x in chosen}])
    status['live_detail_candidates']=len(live)
    status['live_detail_selected']=len(chosen)
    status['missing_momentum_rechecks_planned']=sum(
        scout_priority(g,fixtures.get(g['id']) or {})[0]==4 for g in chosen)
    status['coverage_policy']='Priorizar scouts observados e partidas novas; reservar até 1/6 das consultas para verificar novamente fontes sem momentum. Sem interpolar pressão.'
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
            round_from_detail=str((packet.get('general') or {}).get('matchRound') or '').strip()
            if round_from_detail and not (before.get('fixture') or {}).get('round'):
                before.setdefault('fixture',{})['round']=round_from_detail[:35]
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
                before['events']=merge_verified_events(before.get('events'),new_events)
            lineups=fotmob_lineups(packet)
            if lineups:before['lineups']={**(before.get('lineups') or {}),**lineups}
            stars=fotmob_match_stars(packet)
            if stars:before['match_stars']={**(before.get('match_stars') or {}),**stars}
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
    # Qualidade REAL da coleta, denominador: detalhes que foram retornados.
    n=status['details_collected']
    status['scouts_detail_pct']=round(100*status['stats_detail_available']/n,1) if n else None
    status['source_momentum_pct']=round(100*status['momentum_status_counts'].get('observed',0)/n,1) if n else None
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
