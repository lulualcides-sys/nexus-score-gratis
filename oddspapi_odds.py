#!/usr/bin/env python3
"""OddsPapi free optional source: verified 1X2 from multiple bookmakers (no scraping).

Free tier: 250 requests/month. This source deliberately allows at most two
UTC slots/day, with one fixture listing and two price lookups in each slot:
<= 186 requests in a 31-day month, no billing or payment.
Only exact, unambiguous fixture matches and full 1/X/2 offers are stored.
Requires the user's self-created free secret NEXUS_ODDSPAPI_KEY.
"""
import json, math, os, time
from pathlib import Path
from datetime import datetime,timezone,timedelta
from urllib.parse import urlencode
from urllib.request import Request,urlopen

from espn_scoreboard_odds import normalized_team,parse_ts
from pregame_refresh_quotes import append_trio,append_market_group

BASE='https://api.oddspapi.io/v4'
SLOTS_UTC=(12,21)
SLOT_WINDOW_HOURS=2 # atrasos do GitHub Actions nao podem cancelar a coleta
MONTHLY_BUDGET=186 # limite conservador: ate 3 requisicoes x 2 janelas x 31 dias
BOOKMAKERS=('betano.bet.br','pinnacle','bet365')
MARKET_1X2='101'
SELECTIONS={'101':'home','102':'draw','103':'away'}
# IDs e outcomes documentados por OddsPapi v4; nao inferir outros mercados.
EXTRA_SPECS={
    'over_under_25':('1010',{'1010':'over','1011':'under'}),
    'over_under_15':('1012',{'1012':'over','1013':'under'}),
    'over_under_35':('1014',{'1014':'over','1015':'under'}),
    'btts':('104',{'104':'yes','105':'no'}),
    # Asian Handicap: mesmo mercado e mesma linha em ambas selecoes.
    'ah_m05':('1068',{'1068':'home','1069':'away'}),
    'ah_p05':('1076',{'1076':'home','1077':'away'}),
    'ah_m1':('1064',{'1064':'home','1065':'away'}),
}
# No Asian Handicap 0, identificar a selecao apenas pelo identificador
# explicitamente fornecido pelo operador (home/away), nunca pela ordem.
AH_ZERO_ID='1072'
PRIMARY_LEAGUES=('premier league','bundesliga','la liga','laliga',
 'serie a','ligue 1','brasileir','libertadores','champions league',
 'europa league','eredivisie','liga portugal','primeira liga',
 'major league soccer','mls','ligapro argentina','argentina primera')


def safe_provider_error(error):
    """Nunca publicar query string nem token recebido numa excecao da API."""
    status=getattr(error,'code',None)
    if isinstance(status,int) and 400<=status<=599:
        return 'provider_http_'+str(status)
    if isinstance(error,TimeoutError):
        return 'provider_timeout'
    return 'provider_unavailable'


def http_json(url):
    req=Request(url,headers={'Accept':'application/json','User-Agent':'NEXUS/6.1-verified-free-odds'})
    with urlopen(req,timeout=9) as resp:raw=resp.read(3200001)
    if len(raw)>3200000:raise ValueError('Resposta da API maior que o limite')
    return json.loads(raw)


def free_slot_id(instant):
    """Janela em UTC estendida contra atrasos de agendamento."""
    for hour in SLOTS_UTC:
        if hour<=instant.hour<hour+SLOT_WINDOW_HOURS:
            return instant.strftime('%Y-%m-%d')+'T%02d'%hour
    return None

def load_usage(path, instant):
    """Falha de leitura interrompe coleta para nao gastar creditos sem controle."""
    path=Path(path)
    if path.exists():
        with path.open('r',encoding='utf-8') as f:
            data=json.load(f)
        if not isinstance(data,dict):raise ValueError('Ledger de cota invalido')
    else:data={}
    month=instant.strftime('%Y-%m')
    if data.get('month')!=month:
        data={'month':month,'requests':0,'slots':{}}
    if (not isinstance(data.get('requests'),int) or data['requests']<0 or
        not isinstance(data.get('slots'),dict)):
        raise ValueError('Ledger de cota invalido')
    return data

def save_usage(path, data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        f.write('\n')
    os.replace(tmp,path)

def match_fixture(fixture,listed):
    home=normalized_team(fixture.get('home'))
    away=normalized_team(fixture.get('away'))
    try:kickoff=int(fixture.get('start_timestamp') or 0)
    except (ValueError,TypeError,OverflowError):return None
    if not home or not away or not kickoff or not isinstance(listed,list):return None
    found=[]
    for event in listed:
        if not isinstance(event,dict) or not event.get('hasOdds'):continue
        if fixture.get('phase')=='live' and event.get('statusId')!=1:continue
        if fixture.get('phase')=='scheduled' and event.get('statusId') not in (0,None):continue
        stamp=parse_ts(event.get('startTime'))
        if not stamp or abs(stamp-kickoff)>600:continue
        if (normalized_team(event.get('participant1Name'))==home and
            normalized_team(event.get('participant2Name'))==away):
            found.append(event)
    return found[0] if len(found)==1 else None

def priority_score(fixture,delta):
    """Ranking por proximidade e prestigio (heuristica, NAO liquidez medida)."""
    league=str(fixture.get('league') or '').casefold()
    preferred=any(s in league for s in PRIMARY_LEAGUES)
    minutes=abs(delta)/60
    return round((0 if preferred else 110)+minutes+(0 if minutes<=75 else 25),2)

def active_outcomes(bookmaker,market_id,ids,now_ts,phase):
    market=(bookmaker.get('markets') or {}).get(market_id)
    if not isinstance(market,dict) or market.get('marketActive') is not True:return None
    values={}
    for oid,selection in ids.items():
        outcome=(market.get('outcomes') or {}).get(oid)
        if not isinstance(outcome,dict):return None
        players=outcome.get('players') or {}
        if not isinstance(players,dict):return None
        active=[p for p in players.values() if isinstance(p,dict) and p.get('active') is True]
        if len(active)!=1:return None
        offer=active[0]
        try:price=float(offer.get('price'))
        except (ValueError,TypeError,OverflowError):return None
        changed=parse_ts(offer.get('bookmakerChangedAt') or offer.get('changedAt'))
        ttl=600 if phase=='live' else 24*3600
        if not math.isfinite(price) or not 1.01<price<1000 or changed is None or changed>now_ts+120 or now_ts-changed>ttl:
            return None
        values[selection]=round(price,4)
    return values if len(values)==len(ids) else None

def available_extra_markets(packet,now_ts,phase='pregame'):
    if not isinstance(packet,dict) or not packet.get('hasOdds'):return []
    if phase=='live' and packet.get('statusId')!=1:return []
    if phase=='pregame' and packet.get('statusId') not in (None,0):return []
    found=[]
    for slug in BOOKMAKERS:
        book=(packet.get('bookmakerOdds') or {}).get(slug)
        if not isinstance(book,dict) or not book.get('bookmakerIsActive') or book.get('suspended'):continue
        name={'betano.bet.br':'Betano BR','pinnacle':'Pinnacle','bet365':'Bet365'}.get(slug,slug)
        for market,(mid,ids) in EXTRA_SPECS.items():
            values=active_outcomes(book,mid,ids,now_ts,phase)
            if values:found.append((market,values,name))
        # Handicap asiatico 0 usa outcomes 1072/1073 no catalogo OddsPapi,
        # INDEPENDENTE do bookmakerOutcomeId, que pode ser um codigo opaco.
        pairs=active_outcomes(book,AH_ZERO_ID,
                              {'1072':'home','1073':'away'},now_ts,phase)
        if pairs:found.append(('ah_0',pairs,name))
    return found

def available_1x2(packet,now_ts,phase='pregame'):
    """Official OddsPapi market catalog: fulltime=101, 1/X/2=101/102/103.
    Reject undocumented numeric market IDs instead of guessing outcomes.
    """
    if not isinstance(packet,dict) or not packet.get('hasOdds'):return []
    if parse_ts(packet.get('startTime')) is None:return []
    if phase=='live' and packet.get('statusId')!=1:return []
    if phase=='pregame' and packet.get('statusId') not in (None,0):return []
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
                changed>now_ts+120 or now_ts-changed>(600 if phase=='live' else 24*3600)):
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

def collect_odds(docs,candidates,now_ts,key=None,fetcher=http_json,ledger_path=None,sleep_fn=time.sleep):
    key=os.getenv('NEXUS_ODDSPAPI_KEY','') if key is None else key
    result={'status':'not_configured' if not key else 'waiting_free_slot',
            'requests':0,'matched':0,'quotes_added':0,'errors':[],
            'provider':'OddsPapi','bookmakers':'Betano BR / Pinnacle / Bet365',
            'free_tier_monthly_max_requests':186,'markets_added':0,'live_quotes_added':0,
            'prioritized':[],'duplicate_provider_matches_skipped':0}
    if not key:return result
    instant=datetime.fromtimestamp(now_ts,timezone.utc)
    slot=free_slot_id(instant)
    if not slot:return result
    usage=None
    if ledger_path is not None:
        try:
            usage=load_usage(ledger_path,instant)
        except (OSError,ValueError):
            result['status']='budget_unavailable'
            return result
        if slot in usage['slots']:
            result['status']='already_checked'
            return result
        if usage['requests']+3>MONTHLY_BUDGET:
            result['status']='free_budget_exhausted'
            return result
    def reserve_request():
        # Persistir ANTES de cada chamada: falhas, retries e reinicios gastam cota.
        if usage is not None:
            usage['requests']+=1
            record=usage['slots'].setdefault(slot,{'requests':0,'attempted_at':instant.isoformat()})
            record['requests']+=1
            save_usage(ledger_path,usage)
        result['requests']+=1
    relevant=[]
    for day,mid,delta in candidates:
        row=((docs.get(day) or {}).get('matches') or {}).get(mid)
        if not isinstance(row,dict):continue
        fixture=row.get('fixture') or {}
        phase=fixture.get('phase')
        if not ((phase=='scheduled' and 0<delta<=6*3600) or
                (phase=='live' and -150*60<=delta<=0)):continue
        try:kickoff=int(fixture.get('start_timestamp') or 0)
        except (ValueError,TypeError):continue
        if not kickoff or (phase=='scheduled' and kickoff<=now_ts):continue
        relevant.append((row,fixture,delta))
    if not relevant:
        result['status']='no_pregame_candidates'
        return result
    start=datetime.fromtimestamp(now_ts,timezone.utc).replace(microsecond=0)-timedelta(hours=3)
    end=start+timedelta(hours=9)
    params={'apiKey':key,'sportId':10,
            'from':start.isoformat().replace('+00:00','Z'),
            'to':end.isoformat().replace('+00:00','Z'),
            'hasOdds':'true','bookmakers':','.join(BOOKMAKERS)}
    try:
        reserve_request()
        listing=fetcher(BASE+'/fixtures?'+urlencode(params))
        if isinstance(listing,dict):listing=listing.get('data') or listing.get('fixtures')
        if not isinstance(listing,list):raise ValueError('Lista de partidas não retornada')
    except Exception as err:
        result['status']='unavailable'
        result['errors'].append(safe_provider_error(err))
        return result
    matched=[]
    for row,fixture,delta in relevant:
        event=match_fixture(fixture,listing)
        if event:
            fixture_id=str(event.get('fixtureId') or '')
            if fixture_id.startswith('id') and len(fixture_id)<=80:
                row['oddspapi_fixture_id']=fixture_id
            matched.append((row,fixture,event,priority_score(fixture,delta)))
    # Janela com limite de 2 jogos: 1 live + 1 pre quando ambos existirem.
    matched.sort(key=lambda pair:pair[3])
    # Duas fontes internas podem apontar para o mesmo fixture da OddsPapi.
    # Uma consulta /odds por ID real evita gastar a cota gratuita em duplicatas.
    unique_matches=[]
    provider_ids=set()
    for item in matched:
        provider_id=str(item[2].get('fixtureId') or '')
        if not provider_id:continue
        if provider_id in provider_ids:
            result['duplicate_provider_matches_skipped']+=1
            continue
        provider_ids.add(provider_id)
        unique_matches.append(item)
    matched=unique_matches
    live=next((m for m in matched if m[1].get('phase')=='live'),None)
    pre=next((m for m in matched if m[1].get('phase')=='scheduled'),None)
    selected=([live,pre] if live and pre else matched[:2])
    for index,(row,fixture,event,score) in enumerate(selected):
        # OddsPapi v4 limita chamadas /odds a ~1 por segundo.
        # Ritmo conservador evita 429 sem retries cobrados da cota mensal.
        if index:sleep_fn(1.2)
        result['matched']+=1
        try:
            url=BASE+'/odds?'+urlencode({'fixtureId':event['fixtureId'],
                'bookmakers':','.join(BOOKMAKERS),'apiKey':key,'verbosity':3})
            reserve_request()
            packet=fetcher(url)
            if not isinstance(packet,dict):continue
            if str(packet.get('fixtureId'))!=str(event.get('fixtureId')):continue
            phase='live' if fixture.get('phase')=='live' else 'pregame'
            if phase=='live' and packet.get('statusId')!=1:continue
            if phase=='pregame' and packet.get('statusId') not in (None,0):continue
            result['prioritized'].append({'league':str(fixture.get('league') or '')[:60],
                                           'phase':phase,'priority_score':score})
            for values,book in available_1x2(packet,now_ts,phase):
                if phase=='live':
                    result['live_quotes_added']+=append_market_group(
                        row,'1x2',values,book,'OddsPapi',now_ts,phase='live')
                else:
                    result['quotes_added']+=append_trio(row,values,book,'OddsPapi',now_ts)
            for market,values,book in available_extra_markets(packet,now_ts,phase):
                count=append_market_group(row,market,values,book,'OddsPapi',now_ts,phase)
                if phase=='live':result['live_quotes_added']+=count
                else:result['markets_added']+=count
        except Exception as err:
            if len(result['errors'])<3:result['errors'].append(safe_provider_error(err))
    result['status']='checked' if not result['errors'] else 'partial'
    return result
