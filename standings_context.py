#!/usr/bin/env python3
"""NEXUS: classificação validada por liga FotMob para urgência de tabela.
Regra: nunca concluir obrigação matemática de vencer; apenas contexto situacional.
Não usar classificações de copa com grupos como liga única.
"""
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
from coletar import HISTORY,DAY,NOW,fetch,read,write

CACHE=HISTORY/'standings_cache.json'
STATUS=HISTORY/'standings_status.json'
TTL_MIN=55
MAX_LEAGUES=24
MAX_TEAMS=30

def integer(v):
    try:return int(v) if v is not None and str(v).strip() else None
    except (TypeError,ValueError):return None

def league_table(doc,league_id):
    if not isinstance(doc,dict):return None
    tables=doc.get('table') or []
    if not isinstance(tables,list) or len(tables)!=1:return None
    section=tables[0].get('data') or {}
    if not isinstance(section,dict):return None
    tab=section.get('table') or {}
    rows=tab.get('all') or []
    if not isinstance(rows,list) or not 8<=len(rows)<=MAX_TEAMS:return None
    names=set();ids=set();out=[]
    for item in rows:
        if not isinstance(item,dict):return None
        rank=integer(item.get('idx'));pts=integer(item.get('pts'))
        played=integer(item.get('played'));tid=integer(item.get('id'))
        name=str(item.get('name') or '')[:80]
        if rank is None or not 1<=rank<=len(rows) or pts is None or pts<0 or (
                played is None or played<0 or tid is None or not name):return None
        if rank in names or tid in ids:return None
        names.add(rank);ids.add(tid)
        out.append({'id':tid,'name':name,'position':rank,'points':pts,'played':played,
                    'goal_diff':integer(item.get('goalConDiff'))})
    if names!=set(range(1,len(rows)+1)):return None
    out.sort(key=lambda x:x['position'])
    info=doc.get('details') or {}
    if integer(info.get('id')) not in (None,integer(league_id)):return None
    return {'league_id':str(league_id),'league':str(info.get('name') or section.get('leagueName') or '')[:80],
            'season':str(info.get('selectedSeason') or '')[:26],
            'teams':out,'updated_at':NOW.isoformat(),'source':'FotMob'}

def zones(table):
    league_id=str(table.get('league_id') or '')
    title=str(table.get('league') or '').casefold()
    count=len(table.get('teams') or [])
    # Somente torneios de pontos corridos cujas zonas são conhecidas.
    if count==20 and league_id=='47':
        return {'drop':3,'top':4}
    if count==20 and league_id=='268':
        return {'drop':4,'top':4}
    # Não aplicar G4/Z4 automaticamente a campeonatos sem regra verificada.
    return {'drop':0,'top':0}

def team_stakes(table,tid):
    rows=table.get('teams') or []
    me=next((r for r in rows if str(r['id'])==str(tid)),None)
    if not me:return None
    rank=me['position'];pts=me['points'];n=len(rows)
    rules=zones(table);reasons=[]
    if rules['top'] and me['played']>=3:
        fourth=rows[3]['points']
        fifth=rows[4]['points']
        gap=pts-fourth
        if rank<=4 and pts-fifth<=6:
            reasons.append({'kind':'defender_g4','label':'Defender o G4',
             'detail':f'{rank}º lugar, {pts} pontos; o 5º soma {fifth}. Uma vitória ajuda a defender a posição.'})
        elif 5<=rank<=8 and fourth-pts<=6:
            reasons.append({'kind':'buscar_g4','label':'Buscar o G4',
             'detail':f'{rank}º lugar, {pts} pontos; o 4º soma {fourth} (diferença: {fourth-pts}).'})
    relegated=rules['drop']
    if relegated and me['played']>=3:
        danger=n-relegated+1
        first_safe=rows[danger-2]
        first_drop=rows[danger-1]
        if rank>=danger:
            reasons.append({'kind':'sair_z4','label':'Sair da zona de rebaixamento',
                'detail':f'{rank}º lugar com {pts} pontos; primeiro fora da zona: '
                         f'{first_safe["position"]}º com {first_safe["points"]}.'})
        elif rank>=danger-3 and pts-first_drop['points']<=6:
            reasons.append({'kind':'evitar_z4','label':'Evitar a zona de rebaixamento',
                'detail':f'{rank}º lugar com {pts} pontos; primeira posição da zona: '
                         f'{first_drop["position"]}º com {first_drop["points"]}.'})
    if not reasons and rank<=3 and me['played']>=3:
        ahead=rows[0]['points']-pts
        if ahead<=4:
            reasons.append({'kind':'primeiras_posicoes','label':'Disputa das primeiras posições',
                            'detail':f'{rank}º lugar, {pts} pontos, {ahead} ponto(s) atrás da liderança.'})
    level='alta' if any(x['kind'] in ('sair_z4','buscar_g4') for x in reasons) else (
          'moderada' if reasons else 'sem_alerta')
    return {'position':rank,'points':pts,'played':me['played'],'goal_diff':me.get('goal_diff'),
            'total_teams':n,'level':level,'reasons':reasons[:3],
            'source':'FotMob','updated_at':table.get('updated_at')}

def normalized_name(value):
    norm=unicodedata.normalize('NFKD',str(value or ''))
    norm=''.join(x for x in norm if not unicodedata.combining(x))
    norm=re.sub(r'[^a-z0-9]+',' ',norm.lower()).strip()
    return ' '.join(x for x in norm.split()
                    if x not in {'fc','cf','ec','sc','ac','the','de','da','do','dos'})

def team_stakes_from_name(table,fixture_name):
    search=normalized_name(fixture_name)
    if not search:return None
    matches=[row for row in table.get('teams') or []
             if normalized_name(row.get('name'))==search]
    if len(matches)!=1:return None
    return team_stakes(table,matches[0]['id'])

def espn_table(doc,league_id,code):
    """ESPN retorna season e children[].standings.entries[] para ligas oficiais."""
    if not isinstance(doc,dict):return None
    season=doc.get('season') or {}
    if not isinstance(season,dict):return None
    current_year=NOW.year
    year=integer(season.get('year'))
    if year is not None and year not in (current_year,current_year-1):return None
    children=doc.get('children') or []
    if not isinstance(children,list) or len(children)!=1:return None
    entries=(children[0].get('standings') or {}).get('entries') or []
    if not isinstance(entries,list) or len(entries)!=20:return None
    rows=[]
    for idx,entry in enumerate(entries):
        if not isinstance(entry,dict):return None
        team=entry.get('team') or {}
        stats={str(v.get('name') or '').lower():v
               for v in entry.get('stats') or [] if isinstance(v,dict)}
        def value(*names):
            for name in names:
                obj=stats.get(name.lower())
                if obj and obj.get('value') is not None:
                    try:return float(obj['value'])
                    except (ValueError,TypeError):continue
            return None
        rank=value('rank','position')
        pts=value('points','point')
        played=value('gamesPlayed','matchesPlayed','played','games')
        if rank is None:rank=idx+1
        tid=str(team.get('id') or '')
        tname=str(team.get('displayName') or team.get('name') or '')[:80]
        if not tid.isdigit() or not tname or any(v is None for v in (pts,played)):return None
        rows.append({'id':tid,'name':tname,'position':int(rank),'points':int(pts),
                     'played':int(played),'goal_diff':integer(value('pointDifferential','goalDifference'))})
    if set(r['position'] for r in rows)!=set(range(1,21)):return None
    if len({r['id'] for r in rows})!=20:return None
    rows.sort(key=lambda item:item['position'])
    return {'league_id':str(league_id),
            'league':'Brasileirão Série A' if code=='bra.1' else 'Premier League',
            'season':str(season.get('displayName') or season.get('year') or '')[:26],
            'teams':rows,'updated_at':NOW.isoformat(),
            'source':'ESPN','join_rule':'Nome completo normalizado e único'}

def make_context(fixture,table):
    if not isinstance(table,dict):return None
    if str(fixture.get('league_id') or '')!=str(table.get('league_id') or ''):return None
    if table.get('source')=='FotMob':
        home=team_stakes(table,fixture.get('home_id'))
        away=team_stakes(table,fixture.get('away_id'))
    elif table.get('source')=='ESPN':
        # IDs ESPN não são equivalentes aos IDs FotMob.
        home=team_stakes_from_name(table,fixture.get('home'))
        away=team_stakes_from_name(table,fixture.get('away'))
    else:return None
    if not home or not away or home['position']==away['position']:return None
    return {'source':table.get('source'),'updated_at':table['updated_at'],
            'league':table['league'],'season':table['season'],
            'home':home,'away':away,
            'note':'Urgência situacional pela tabela atual; não prova obrigação matemática de vencer. '
                   'A pontuação pode já refletir o jogo em andamento.'}

def fetch_table(league_id):
    param=urlencode({'id':league_id})
    for base in ('https://www.fotmob.com/api/data/leagues?','https://www.fotmob.com/api/leagues?'):
        try:
            d=fetch(base+param,timeout=7)
            table=league_table(d,league_id)
            if table:return table
        except Exception:continue
    code={'268':'bra.1','47':'eng.1'}.get(str(league_id))
    if not code:return None
    for root in ('https://site.api.espn.com/apis/v2/sports/soccer/',
                 'https://site.web.api.espn.com/apis/v2/sports/soccer/'):
        try:
            packet=fetch(root+code+'/standings',timeout=7)
            table=espn_table(packet,league_id,code)
            if table:return table
        except Exception:continue
    return None

def run():
    today=datetime.strptime(DAY,'%Y-%m-%d').date()
    days=[(today-timedelta(days=i)).isoformat() for i in range(3)]
    docs={day:read(HISTORY/(day+'.json')) for day in days}
    cache=read(CACHE).get('leagues') or {}
    if not isinstance(cache,dict):cache={}
    targets={}
    for day,doc in docs.items():
        for key,row in (doc.get('matches') or {}).items():
            f=row.get('fixture') or {}
            lid=str(f.get('league_id') or '')
            if not lid.isdigit() or not str(key).startswith('fotmob-'):continue
            rank=0 if f.get('phase')=='live' else 1 if f.get('phase')=='scheduled' else 4
            targets.setdefault(lid,[]).append((rank,day,key))
    candidates=sorted(targets,key=lambda lid:min(a for a,_,_ in targets[lid]))
    stale=[]
    for lid in candidates:
        table=cache.get(lid)
        if not table:
            stale.append(lid);continue
        try:
            age=(NOW-datetime.fromisoformat(table['updated_at'].replace('Z','+00:00'))).total_seconds()
            if age>TTL_MIN*60:stale.append(lid)
        except (ValueError,KeyError,TypeError):stale.append(lid)
    chosen=stale[:MAX_LEAGUES]
    report={'updated_at':NOW.isoformat(),'leagues_found':len(candidates),
            'leagues_queried':len(chosen),'tables_received':0,
            'fixtures_enriched':0,'with_urgency':0,'by_source':{}}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(fetch_table,lid):lid for lid in chosen}
        for done in as_completed(futures):
            result=done.result()
            if result:
                cache[futures[done]]=result
                report['tables_received']+=1
                src=result.get('source') or 'desconhecida'
                report['by_source'][src]=report['by_source'].get(src,0)+1
    for day,doc in docs.items():
        for key,row in (doc.get('matches') or {}).items():
            f=row.get('fixture') or {}
            lid=str(f.get('league_id') or '')
            context=make_context(f,cache.get(lid))
            if not context:continue
            if row.get('standings_context')!=context:
                row['standings_context']=context
            report['fixtures_enriched']+=1
            if any(context[side]['reasons'] for side in ('home','away')):
                report['with_urgency']+=1
        if doc:write(HISTORY/(day+'.json'),doc)
    # Cache leve: classificação resumida em vez da resposta completa da API.
    write(CACHE,{'updated_at':NOW.isoformat(),'leagues':{
        lid:cache[lid] for lid in candidates if lid in cache}})
    write(STATUS,report)
    print(json.dumps(report,ensure_ascii=False))
    return report

if __name__=='__main__':run()
