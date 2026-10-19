#!/usr/bin/env python3
"""OddsPapi free optional source: verified 1X2 from multiple bookmakers (no scraping).

Free tier: 250 requests/month. This source deliberately allows at most two
UTC slots/day, with one fixture listing and two price lookups in each slot:
<= 186 requests in a 31-day month, no billing or payment.
Only exact, unambiguous fixture matches and full 1/X/2 offers are stored.
Requires the user's self-created free secret NEXUS_ODDSPAPI_KEY.
"""
import json, math, os
from datetime import datetime,timezone,timedelta
from urllib.parse import urlencode
from urllib.request import Request,urlopen

from espn_scoreboard_odds import normalized_team,parse_ts
from pregame_refresh_quotes import append_trio

BASE='https://api.oddspapi.io/v4'
SLOTS_UTC=(12,21)
BOOKMAKERS=('betano.bet.br','pinnacle','bet365')
MARKET_1X2='101'
SELECTIONS={'101':'home','102':'draw','103':'away'}

def http_json(url):
    req=Request(url,headers={'Accept':'application/json','User-Agent':'NEXUS/6.1-verified-free-odds'})
    with urlopen(req,timeout=9) as resp:raw=resp.read(3200001)
    if len(raw)>3200000:raise ValueError('Resposta da API maior que o limite')
    return json.loads(raw)

def match_fixture(fixture,listed):
    home=normalized_team(fixture.get('home'))
    away=normalized_team(fixture.get('away'))
    try:kickoff=int(fixture.get('start_timestamp') or 0)
    except (ValueError,TypeError,OverflowError):return None
    if not home or not away or not kickoff or not isinstance(listed,list):return None
    found=[]
    for event in listed:
        if not isinstance(event,dict) or not event.get('hasOdds'):continue
        stamp=parse_ts(event.get('startTime'))
        if not stamp or abs(stamp-kickoff)>600:continue
        if (normalized_team(event.get('participant1Name'))==home and
            normalized_team(event.get('participant2Name'))==away):
            found.append(event)
    return found[0] if len(found)==1 else None

def available_1x2(packet,now_ts):
    """Official OddsPapi market catalog: fulltime=101, 1/X/2=101/102/103.
    Reject undocumented numeric market IDs instead of guessing outcomes.
    """
    if not isinstance(packet,dict) or not packet.get('hasOdds'):return None
    if parse_ts(packet.get('startTime')) is None:return None
    offers=[]
    for book in BOOKMAKERS:
        bookmaker=(packet.get('bookmakerOdds') or {}).get(book)
        if not isinstance(bookmaker,dict) or not bookmaker.get('bookmakerIsActive') or bookmaker.get('suspended'):continue
        market=(bookmaker.get('markets') or {}).get(MARKET_1X2)
        if not isinstance(market,dict) or market.get('marketActive') is not True:continue
        selections={}
        for oid,side in SELECTIONS.items():
            outcome=(market.get('outcomes') or {}).get(oid)
            if not isinstance(outcome,dict):break
            players=outcome.get('players') or {}
            if not isinstance(players,dict):break
            active_players=[p for p in players.values() if isinstance(p,dict) and p.get('active') is True]
            if len(active_players)!=1:break
            offer=active_players[0]
            try:price=float(offer.get('price'))
            except (ValueError,TypeError,OverflowError):break
            changed=parse_ts(offer.get('bookmakerChangedAt') or offer.get('changedAt'))
            if (not math.isfinite(price) or not 1.01<price<1000 or changed is None or
                changed>now_ts+120 or now_ts-changed>24*3600):
                break
            selections[side]=round(price,4)
        if set(selections)=={'home','draw','away'}:
            name={'betano.bet.br':'Betano BR','pinnacle':'Pinnacle',
                  'bet365':'Bet365'}.get(book,book)
            offers.append((selections,name))
    return offers

def extract_1x2(packet,now_ts):
    """Compatibilidade com a interface anterior; primeiro conjunto válido."""
    items=available_1x2(packet,now_ts)
    return items[0] if items else None

def collect_odds(docs,candidates,now_ts,key=None,fetcher=http_json):
    key=os.getenv('NEXUS_ODDSPAPI_KEY','') if key is None else key
    result={'status':'not_configured' if not key else 'waiting_free_slot',
            'requests':0,'matched':0,'quotes_added':0,'errors':[],
            'provider':'OddsPapi','bookmakers':'Betano BR / Pinnacle / Bet365',
            'free_tier_monthly_max_requests':186}
    if not key:return result
    instant=datetime.fromtimestamp(now_ts,timezone.utc)
    if instant.hour not in SLOTS_UTC or instant.minute>=5:return result
    relevant=[]
    for day,mid,delta in candidates:
        if not 0<delta<=6*3600:continue
        row=((docs.get(day) or {}).get('matches') or {}).get(mid)
        if not isinstance(row,dict):continue
        fixture=row.get('fixture') or {}
        if fixture.get('phase')!='scheduled':continue
        try:kickoff=int(fixture.get('start_timestamp') or 0)
        except (ValueError,TypeError):continue
        if kickoff<=now_ts:continue
        relevant.append((row,fixture))
    if not relevant:
        result['status']='no_pregame_candidates'
        return result
    start=datetime.fromtimestamp(now_ts,timezone.utc).replace(microsecond=0)
    end=start+timedelta(hours=6)
    params={'apiKey':key,'sportId':10,
            'from':start.isoformat().replace('+00:00','Z'),
            'to':end.isoformat().replace('+00:00','Z'),
            'statusId':0,'hasOdds':'true',
            'bookmakers':','.join(BOOKMAKERS)}
    try:
        result['requests']+=1
        listing=fetcher(BASE+'/fixtures?'+urlencode(params))
        if isinstance(listing,dict):listing=listing.get('data') or listing.get('fixtures')
        if not isinstance(listing,list):raise ValueError('Lista de partidas não retornada')
    except Exception as err:
        result['status']='unavailable'
        result['errors'].append(str(err)[:130])
        return result
    matched=[]
    for row,fixture in relevant:
        event=match_fixture(fixture,listing)
        if event:matched.append((row,event))
    # At most two per slot, prioritizing closest start time, not thousands of leagues.
    matched.sort(key=lambda pair:parse_ts(pair[1].get('startTime')) or float('inf'))
    for row,event in matched[:2]:
        result['matched']+=1
        try:
            url=BASE+'/odds?'+urlencode({'fixtureId':event['fixtureId'],
                'bookmakers':','.join(BOOKMAKERS),'apiKey':key,'verbosity':3})
            result['requests']+=1
            packet=fetcher(url)
            if not isinstance(packet,dict):continue
            if str(packet.get('fixtureId'))!=str(event.get('fixtureId')):continue
            for values,book in available_1x2(packet,now_ts):
                result['quotes_added']+=append_trio(row,values,book,'OddsPapi',now_ts)
        except Exception as err:
            if len(result['errors'])<3:result['errors'].append(str(err)[:130])
    result['status']='checked' if not result['errors'] else 'partial'
    return result
