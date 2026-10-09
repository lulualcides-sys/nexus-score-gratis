#!/usr/bin/env python3
"""SofaScore opcional: cotejo estrito de partidas e preços de Match Odds 1X2.
Sem login/chave. Se a API não responder ou os nomes e horários divergirem,
não cria registros. Valores fracionários são convertidos em odds decimais.
"""
import re
import unicodedata
from datetime import datetime,timezone
from odds_capture import get

BASE='https://www.sofascore.com/api/v1'

def normalized(v):
    s=unicodedata.normalize('NFKD',str(v or ''))
    s=''.join(ch for ch in s if not unicodedata.combining(ch))
    s=re.sub(r'[^a-z0-9]+',' ',s.lower())
    return ' '.join(t for t in s.split() if t not in
        {'fc','cf','sc','ec','ac','afc','club','clube','de','da','do','dos','the'})

def fixture_match(fixture,event):
    if not isinstance(event,dict) or not isinstance(fixture,dict):return False
    try:
        a=int(fixture.get('start_timestamp') or 0)
        b=int(event.get('startTimestamp') or 0)
    except (ValueError,TypeError):return False
    if a<=0 or b<=0 or abs(a-b)>10*60:return False
    home=(event.get('homeTeam') or {}).get('name')
    away=(event.get('awayTeam') or {}).get('name')
    return bool(normalized(home) and normalized(away) and
       normalized(home)==normalized(fixture.get('home')) and
       normalized(away)==normalized(fixture.get('away')))

def decimal(offer):
    if not isinstance(offer,dict):return None
    for field in ('decimalValue','decimalOdds'):
        try:
            val=float(offer[field])
            if 1.01<=val<=1000:return round(val,4)
        except (KeyError,TypeError,ValueError):pass
    frac=str(offer.get('fractionalValue') or '')
    hit=re.fullmatch(r'(\d{1,5})/(\d{1,5})',frac)
    if hit and int(hit[2])>0:
        val=1+int(hit[1])/int(hit[2])
        return round(val,4) if 1.01<=val<=1000 else None
    return None

def three_way_market(doc):
    markets=doc.get('markets') or []
    if not isinstance(markets,list):return None
    for m in markets:
        if not isinstance(m,dict):continue
        name=str(m.get('marketName') or m.get('name') or '').lower()
        if (m.get('marketId')!=1 and name not in ('full time','1x2','full time result')):
            continue
        if m.get('isLive') is True or m.get('suspended') is True:continue
        selections={}
        for choice in m.get('choices') or []:
            if not isinstance(choice,dict):continue
            outcome={'1':'home','x':'draw','2':'away'}.get(str(choice.get('name') or '').lower())
            val=decimal(choice)
            if outcome and val:selections[outcome]=val
        if set(selections)=={'home','draw','away'}:
            src=m.get('bookmaker') or m.get('provider') or {}
            value=src.get('name') if isinstance(src,dict) else src
            bookmaker=str(value or '').strip()
            if not bookmaker:bookmaker='Bookmaker não identificado'
            return selections,bookmaker[:55]
    return None

def calendar(day):
    packet=get(BASE+'/sport/football/scheduled-events/'+day)
    return [event for event in (packet.get('events') or [])
            if isinstance(event,dict) and event.get('id') is not None]

def event_quotes(event_id):
    if not str(event_id).isdigit():return None
    packet=get(BASE+'/event/'+str(event_id)+'/odds/1/all')
    return three_way_market(packet)

def link_fixtures(candidates,events):
    """Relacionar apenas nomes EXATOS normalizados + horario <=10min e unicidade."""
    pairs=[]
    for day,key,delta,fixture in candidates:
        matches=[ev for ev in events if fixture_match(fixture,ev)]
        if len(matches)==1:
            pairs.append((day,key,delta,fixture,matches[0]['id']))
    return pairs
