#!/usr/bin/env python3
"""Associa cotações PRÉ-JOGO a fixtures equivalentes de provedores diferentes.

Somente em snapshot público: NUNCA cria sinais, entradas ou odds 'live'.
Cruza nomes inteiros/casos de alias explícitos, dois clubes, data e kickoff.
"""
import re
import unicodedata
from datetime import datetime, timezone

ALIAS={
    # FotMob: Gimnasia LP / ESPN: Gimnasia La Plata
    'gimnasia lp':'gimnasia la plata',
}

def team_key(value):
    value=unicodedata.normalize('NFKD',str(value or '').lower())
    value=''.join(c for c in value if not unicodedata.combining(c))
    value=' '.join(re.findall(r'[a-z0-9]+',value))
    for token in (' fc ',' sc '):
        value=(' '+value+' ').replace(token,' ').strip()
    value=ALIAS.get(value,value)
    return value

def time_key(value):
    try:
        n=int(value)
        return n if 1000000000<n<4102444800 else None
    except (TypeError,ValueError,OverflowError):
        return None

def quote_time(quote):
    try:
        value=datetime.fromisoformat(str(quote.get('at') or '').replace('Z','+00:00'))
        return value.timestamp() if value.tzinfo else None
    except (ValueError,TypeError,OverflowError):
        return None

def verified_trio(game):
    """Quotes may be shown only when all three selections are observed pre-kickoff."""
    start=time_key(game.get('start_timestamp'))
    if not start:return None
    quotes=game.get('odds') or []
    if not isinstance(quotes,list):return None
    selections={}
    source=None
    house=None
    for q in quotes:
        if not isinstance(q,dict):return None
        side=q.get('sel')
        if side not in ('home','draw','away') or side in selections:return None
        try: value=float(q.get('odd'))
        except (ValueError,TypeError):return None
        qt=quote_time(q)
        if not 1.01<=value<=1000 or qt is None or qt>=start:return None
        if not q.get('source') or not q.get('bookmaker'):return None
        if source is None:source=q.get('source')
        if house is None:house=q.get('bookmaker')
        if source!=q.get('source') or house!=q.get('bookmaker'):return None
        selections[side]=q
    return [selections[side] for side in ('home','draw','away')] if len(selections)==3 else None

def same_fixture(a,b):
    if a.get('id')==b.get('id'):return False
    if a.get('day')!=b.get('day'):return False
    ta,tb=time_key(a.get('start_timestamp')),time_key(b.get('start_timestamp'))
    if not ta or not tb or abs(ta-tb)>600:return False
    for key in ('home','away'):
        namea,nameb=team_key(a.get(key)),team_key(b.get(key))
        if not namea or namea!=nameb:return False
    return True

def bridge_pregame_prices(games):
    donors=[g for g in games if isinstance(g,dict) and verified_trio(g)]
    status={'linked':0,'candidates':0,'ambiguous':0,'source':'snapshot_public_only',
            'market':'1x2','scope':'pregame'}
    for game in games:
        if not isinstance(game,dict) or game.get('odds'):continue
        matched=[g for g in donors if same_fixture(game,g)]
        if not matched:continue
        status['candidates']+=1
        if len(matched)!=1:
            status['ambiguous']+=1
            continue
        donor=matched[0]
        game['odds']=[q.copy() for q in verified_trio(donor)]
        game['odds_scope']='pregame'
        game['odds_source_match']=donor['id']
        status['linked']+=1
    return status
