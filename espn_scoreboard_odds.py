#!/usr/bin/env python3
"""Fallback ESPN 1X2 para jogos FotMob. Só grava preços publicados antes do apito.

A lista FotMob e a agenda ESPN precisam corresponder EXATAMENTE por ambos
os clubes (normalização de FC/SC) e pelo horário (tolerância de 10 min).
Não usa probabilidade do modelo, spread ou odds históricas como cotação.
"""
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlencode

from odds_capture import get as espn_get
from pregame_refresh_quotes import append_quote, threeway_offers

LEAGUE_NAMES = (
    ('usl championship', 'usa.usl.1'),
    ('major league soccer', 'usa.1'),
    ('mls', 'usa.1'),
    ('premier league', 'eng.1'),
    ('english championship', 'eng.2'),
    ('efl championship', 'eng.2'),
    ('la liga', 'esp.1'),
    ('laliga', 'esp.1'),
    ('bundesliga', 'ger.1'),
    ('ligue 1', 'fra.1'),
    ('serie a brazil', 'bra.1'),
    ('brasileirao serie a', 'bra.1'),
    ('brasileirão série a', 'bra.1'),
    ('brasileirao serie b', 'bra.2'),
    ('brasileirão série b', 'bra.2'),
    ('argentina primera', 'arg.1'),
    ('copa libertadores', 'conmebol.libertadores'),
    ('uefa champions', 'uefa.champions'),
    ('champions league', 'uefa.champions'),
    ('colombia primera', 'col.1'),
    ('colombian primera', 'col.1'),
    ('serie a italy', 'ita.1'),
    ('serie a', 'ita.1'),
)

def plain(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    return ''.join(x for x in value if not unicodedata.combining(x)).lower()

def normalized_team(name):
    words=re.findall(r'[a-z0-9]+',plain(name))
    generic={'fc','sc','cf','ac','afc','club','clube','football','soccer','the'}
    return ' '.join(w for w in words if w not in generic)

def league_code(name):
    s=plain(name).replace('-',' ')
    for needle,code in LEAGUE_NAMES:
        if needle in s:return code
    return None

def parse_ts(value):
    try:
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return int(dt.timestamp()) if dt.tzinfo else None
    except (TypeError,ValueError,OverflowError):
        return None

def linked_event(fixture, events):
    """Correspondência inequívoca: mandante, visitante, kickoff <= 600 s."""
    if not isinstance(fixture,dict) or not isinstance(events,list):return None
    home=normalized_team(fixture.get('home'))
    away=normalized_team(fixture.get('away'))
    try: ts=int(fixture.get('start_timestamp') or 0)
    except (ValueError,TypeError):return None
    if not home or not away or ts<=0:return None
    found=[]
    for event in events:
        if not isinstance(event,dict) or not str(event.get('id') or '').isdigit():continue
        start=parse_ts(event.get('date'))
        if start is None or abs(start-ts)>600:continue
        competitions=event.get('competitions') or []
        comp=competitions[0] if competitions and isinstance(competitions[0],dict) else {}
        competitors=comp.get('competitors') or []
        h=next((x.get('team') or {} for x in competitors
                if isinstance(x,dict) and x.get('homeAway')=='home'),{})
        a=next((x.get('team') or {} for x in competitors
                if isinstance(x,dict) and x.get('homeAway')=='away'),{})
        def name(item):
            return normalized_team(item.get('displayName') or item.get('name') or '')
        if name(h)==home and name(a)==away:
            found.append(event)
    return found[0] if len(found)==1 else None

def scoreboard_offers(event):
    comps=event.get('competitions') or []
    c=comps[0] if comps and isinstance(comps[0],dict) else {}
    offers=c.get('odds') or []
    if isinstance(offers,dict):offers=[offers]
    return offers if isinstance(offers,list) else []

def collect_odds(docs,candidates,now_ts,fetcher=espn_get):
    """Atualiza odds_quotes em memória; o chamador mantém persistência."""
    status={'matched':0,'boards_checked':0,'summaries_checked':0,
            'quotes_added':0,'errors':[]}
    groups={}
    for day,key,delta in candidates:
        if delta<=0:continue
        row=(docs.get(day,{}).get('matches') or {}).get(key) or {}
        fixture=row.get('fixture') or {}
        if fixture.get('phase')!='scheduled':continue
        try:
            if int(fixture.get('start_timestamp') or 0)<=now_ts:continue
        except (ValueError,TypeError):continue
        code=league_code(fixture.get('league'))
        if not code:continue
        groups.setdefault((code,day),[]).append((key,row,fixture))
    # Uma agenda por liga e dia. Reduz chamadas ao invés de requisitar cada jogo.
    for (code,day),games in list(groups.items())[:18]:
        url='https://site.api.espn.com/apis/site/v2/sports/soccer/'+code+'/scoreboard?'+urlencode(
            {'dates':day.replace('-',''),'limit':'100'})
        try:
            board=fetcher(url)
            events=board.get('events') or []
            if not isinstance(events,list):events=[]
            status['boards_checked']+=1
        except Exception as err:
            if len(status['errors'])<8:status['errors'].append('ESPN agenda '+code+': '+str(err)[:85])
            continue
        for key,row,fixture in games[:24]:
            linked=linked_event(fixture,events)
            if linked is None:continue
            status['matched']+=1
            offers=scoreboard_offers(linked)
            current=threeway_offers(offers)
            if current is None:
                try:
                    summary=fetcher('https://site.api.espn.com/apis/site/v2/sports/soccer/'+
                       code+'/summary?event='+str(linked['id']))
                    status['summaries_checked']+=1
                    competitions=(summary.get('header') or {}).get('competitions') or []
                    c=competitions[0] if competitions and isinstance(competitions[0],dict) else {}
                    offers=summary.get('pickcenter') or c.get('odds') or []
                    if isinstance(offers,dict):offers=[offers]
                    current=threeway_offers(offers)
                except Exception as err:
                    if len(status['errors'])<8:
                        status['errors'].append('ESPN odds '+str(linked['id'])+': '+str(err)[:85])
            if current is None:continue
            prices,bookmaker=current
            for side,val in prices.items():
                if append_quote(row,side,val,bookmaker,'ESPN',now_ts):
                    status['quotes_added']+=1
    return status
