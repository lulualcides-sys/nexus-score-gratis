#!/usr/bin/env python3
"""Fonte independente opcional: The Odds API v4, mercados h2h (1/X/2).

Não se utiliza uma chave no front-end: apenas NEXUS_THE_ODDS_API_KEY no runner.
Rejeita timestamps antigos, mercados de dois resultados e partidas ambíguas.
"""
import os
import json
from urllib.request import Request,urlopen
from datetime import datetime,timezone
from urllib.parse import urlencode

from espn_scoreboard_odds import normalized_team, parse_ts, plain
from pregame_refresh_quotes import append_quote, append_trio

BASE='https://api.the-odds-api.com/v4'
ESPN_LEAGUE_ALIASES={
  'bra.1':('brazil',),'bra.2':('brazil',),'eng.1':('epl',),
  'eng.2':('efl_champ',),'esp.1':('la_liga',),
  'ger.1':('bundesliga',),'ita.1':('italy_serie_a',),
  'fra.1':('france_ligue_one',),'arg.1':('argentina',),
  'usa.1':('mls',),'uefa.champions':('uefa_champs_league',),
}
LEAGUES={
  'usl championship':('usl',),
  'major league soccer':('mls',),
  'mls':('mls',),
  'premier league':('epl','premier_league'),
  'championship':('efl_champ','england_championship'),
  'la liga':('la_liga','spain'),
  'bundesliga':('germany_bundesliga','bundesliga'),
  'ligue 1':('france_ligue_one','ligue_1'),
  'serie a':('italy_serie_a','italy'),
  'brasileirao':('brazil','brasileiro'),
  'brasileirão':('brazil','brasileiro'),
  'primera division':('argentina','primera'),
  'champions league':('uefa_champs_league','champions'),
}

def fixture_sport_keys(league,sports):
    norm=plain(league)
    aliases=ESPN_LEAGUE_ALIASES.get(norm.strip(),())
    # Correspondência do nome inteiro evita equiparar ligas 'championship' diferentes.
    if not aliases and 'usl championship' in norm: aliases=('usl',)
    elif not aliases and ('efl championship' in norm or norm.strip()=='championship'):aliases=LEAGUES['championship']
    elif not aliases:
        for needle,values in LEAGUES.items():
            if needle in norm:
                aliases=values
                break
    return [s['key'] for s in sports if isinstance(s,dict) and
      str(s.get('key') or '').startswith('soccer_') and
      (str(s.get('group') or '').lower().startswith('soccer')) and
      any(t in (str(s.get('key') or '')+' '+plain(s.get('title'))).lower() for t in aliases)]

def find_matching_fixture(fixture,events):
    if not isinstance(events,list):return None
    home=normalized_team(fixture.get('home'))
    away=normalized_team(fixture.get('away'))
    try: kickoff=int(fixture.get('start_timestamp') or 0)
    except (TypeError,ValueError):return None
    if not home or not away or not kickoff:return None
    matches=[e for e in events if isinstance(e,dict) and
        abs((parse_ts(e.get('commence_time')) or 0)-kickoff)<=600 and
        normalized_team(e.get('home_team'))==home and
        normalized_team(e.get('away_team'))==away]
    return matches[0] if len(matches)==1 else None

def threeway_from_event(event,now_ts):
    if not isinstance(event,dict):return None
    for bookmaker in event.get('bookmakers') or []:
        if not isinstance(bookmaker,dict):continue
        book=str(bookmaker.get('title') or bookmaker.get('key') or '').strip()
        if not book:continue
        for market in bookmaker.get('markets') or []:
            if not isinstance(market,dict) or market.get('key')!='h2h':continue
            age=parse_ts(market.get('last_update') or bookmaker.get('last_update'))
            if age is None or age>now_ts+120 or now_ts-age>3600:continue
            selections={}
            for offer in market.get('outcomes') or []:
                if not isinstance(offer,dict):continue
                label=normalized_team(offer.get('name'))
                outcome='home' if label==normalized_team(event.get('home_team')) else (
                    'away' if label==normalized_team(event.get('away_team')) else
                    'draw' if plain(offer.get('name')) in ('draw','tie','empate') else None)
                try: price=float(offer.get('price'))
                except (ValueError,TypeError):continue
                if outcome and 1.01<=price<=1000 and price==price:
                    selections[outcome]=price
            if set(selections)=={'home','draw','away'}:
                return selections,book[:55]
    return None

def fetch_json(url):
    request=Request(url,headers={'Accept':'application/json','User-Agent':'NEXUS/odds-audit'})
    with urlopen(request,timeout=6) as response:
        raw=response.read(1500001)
    if len(raw)>1500000:raise ValueError('resposta excede limite')
    return json.loads(raw)

def collect_odds(docs,candidates,now_ts,key=None,fetcher=fetch_json):
    key=os.getenv('NEXUS_THE_ODDS_API_KEY','') if key is None else key
    status={'status':'not_configured' if not key else 'running','sports_queried':0,
            'matched':0,'quotes_added':0,'errors':[]}
    if not key:return status
    # FREE 500 credits/mo: at most 2 UTC slots/day × 3 leagues (186 at 31 days).
    # Without this guard, a 5-minute GitHub schedule could exhaust the free plan.
    now=datetime.fromtimestamp(now_ts,timezone.utc)
    if now.hour not in (12,21) or now.minute>=5:
        status['status']='waiting_free_slot'
        return status
    try:
        sports=fetcher(BASE+'/sports/?'+urlencode({'apiKey':key}))
        if not isinstance(sports,list):raise ValueError('catálogo indisponível')
    except Exception as err:
        status['status']='unavailable'
        status['errors'].append('Catálogo: '+str(err)[:100])
        return status
    relevant={}
    for day,match_id,delta in candidates:
        if delta<=0:continue
        row=(docs.get(day,{}).get('matches') or {}).get(match_id) or {}
        f=row.get('fixture') or {}
        if f.get('phase')!='scheduled':continue
        try:
            if int(f.get('start_timestamp') or 0)<=now_ts:continue
        except (ValueError,TypeError):continue
        for sport in fixture_sport_keys(f.get('league'),sports):
            relevant.setdefault(sport,[]).append((row,f))
    # Quotas: máximo de 8 competições por coleta; sem varrer milhares de ligas.
    for sport,fixtures in list(relevant.items())[:3]:
        try:
            response=fetcher(BASE+'/sports/'+sport+'/odds/?'+urlencode({
                'apiKey':key,'regions':'eu','markets':'h2h','oddsFormat':'decimal',
                'dateFormat':'iso'}))
            status['sports_queried']+=1
            if not isinstance(response,list):continue
        except Exception as err:
            if len(status['errors'])<8:status['errors'].append(sport+': '+str(err)[:95])
            continue
        for row,f in fixtures:
            event=find_matching_fixture(f,response)
            if not event:continue
            status['matched']+=1
            offer=threeway_from_event(event,now_ts)
            if not offer:continue
            prices,bookmaker=offer
            status['quotes_added']+=append_trio(row,prices,bookmaker,'The Odds API',now_ts)
    status['status']='checked' if not status['errors'] else 'partial'
    return status
