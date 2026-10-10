#!/usr/bin/env python3
"""Probe offline: audit OpenFootball CC0 FT results against NEXUS fixtures.

Never fetches private sites, modifies history, copies bookmakers' odds,
or reports that a historical score represents live match statistics.
Source data: https://github.com/openfootball/football.json (CC0).
"""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import re
import unicodedata

TZ={'eng.1':'Europe/London','eng.2':'Europe/London','ger.1':'Europe/Berlin',
    'esp.1':'Europe/Madrid','ita.1':'Europe/Rome','fra.1':'Europe/Paris'}

def norm(value):
    raw=unicodedata.normalize('NFKD',str(value or '').lower())
    words=re.findall(r'[a-z0-9]+',''.join(c for c in raw if not unicodedata.combining(c)))
    return ' '.join(w for w in words if w not in ('fc','afc','sc','cf'))

def ft_score(row):
    if not isinstance(row,dict):return None
    score=row.get('score')
    if not isinstance(score,dict):return None
    values=score.get('ft')
    if not isinstance(values,list) or len(values)!=2:return None
    if not all(isinstance(x,int) and not isinstance(x,bool) and 0<=x<30 for x in values):return None
    return tuple(values)

def expected_score(value):
    m=re.fullmatch(r'\s*(\d{1,2})\s*[-:]\s*(\d{1,2})\s*',str(value or ''))
    return (int(m[1]),int(m[2])) if m else None

def score_crosscheck(fixture,rows):
    if not isinstance(fixture,dict):return {'status':'unavailable'}
    if fixture.get('phase')!='finished':return {'status':'unsettled'}
    score=expected_score(fixture.get('score'))
    if score is None:return {'status':'unavailable'}
    league=fixture.get('league_code')
    if league not in TZ:return {'status':'unsupported_league'}
    try:
        ts=int(fixture.get('start_timestamp') or 0)
        day=datetime.fromtimestamp(ts,ZoneInfo(TZ[league])).date()
    except (ValueError,TypeError,OverflowError,OSError):
        return {'status':'unavailable'}
    home,away=norm(fixture.get('home')),norm(fixture.get('away'))
    if not home or not away or home==away:return {'status':'unavailable'}
    matches=[]
    for match in rows or []:
        if not isinstance(match,dict) or norm(match.get('team1'))!=home or norm(match.get('team2'))!=away:
            continue
        try: parsed=datetime.strptime(str(match.get('date')),'%Y-%m-%d').date()
        except (ValueError,TypeError):continue
        if parsed!=day:continue
        ft=ft_score(match)
        if ft is not None:matches.append(ft)
    if not matches:return {'status':'unmatched'}
    if len(matches)!=1:return {'status':'ambiguous'}
    return {'status':'cross_verified' if score==matches[0] else 'conflict',
            'source':'OpenFootball CC0','score':list(matches[0])}

def summary(fixtures,cc0_by_league):
    counters={}
    for f in fixtures or []:
        if not isinstance(f,dict):continue
        league=f.get('league_code')
        if league not in (cc0_by_league or {}):
            outcome='unavailable'
        else:
            outcome=score_crosscheck(f,cc0_by_league.get(league,[]))['status']
        counters[outcome]=counters.get(outcome,0)+1
    return {'source':'OpenFootball CC0','checked':sum(counters.values()),
            'cross_verified':counters.get('cross_verified',0),
            'conflict':counters.get('conflict',0),'by_status':counters,
            'scope':'offline_result_crosscheck_only',
            'odds':None,'live_scouts':None,
            'note':'CC0 results can verify FT scores, not live xG, bookmaker odds or event minutes.'}
