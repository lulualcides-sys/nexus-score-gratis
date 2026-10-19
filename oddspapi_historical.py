"""OddsPapi free historical quote auditor; never writes a current/live price."""
import json, math, os, time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from espn_scoreboard_odds import parse_ts

H=Path(__file__).resolve().parent/'history'
LEDGER=H/'oddspapi_historical_status.json'
API='https://api.oddspapi.io/v4/historical-odds'
BOOKS={'betano.bet.br':'Betano BR','pinnacle':'Pinnacle','bet365':'Bet365'}
SIDES={'101':'home','102':'draw','103':'away'}
SINCE=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp())

def fetch_json(url):
    with urlopen(Request(url,headers={'Accept':'application/json'}),timeout=15) as reply:
        raw=reply.read(2000001)
    if len(raw)>2000000:raise ValueError('large_payload')
    return json.loads(raw)

def valid_id(value):
    return isinstance(value,str) and value.startswith('id') and value[2:].isdigit() and len(value)<=64

def historical_prices(packet,kickoff):
    """Each selection has its OWN first/last observed timestamp."""
    if not isinstance(packet,dict) or not isinstance(kickoff,int) or kickoff<SINCE:return []
    output=[]
    for slug,book in BOOKS.items():
        blob=(packet.get('bookmakers') or {}).get(slug) or {}
        market=(blob.get('markets') or {}).get('101') or {}
        for oid,side in SIDES.items():
            outcome=(market.get('outcomes') or {}).get(oid) or {}
            players=outcome.get('players') or {}
            if not isinstance(players,dict):continue
            found=[]
            for seq in players.values():
                if not isinstance(seq,list):continue
                for item in seq:
                    if not isinstance(item,dict):continue
                    stamp=parse_ts(item.get('createdAt'))
                    try:price=float(item.get('price'))
                    except (ValueError,TypeError,OverflowError):continue
                    if (stamp is None or not SINCE<=stamp<kickoff or
                        kickoff-stamp>14*86400 or not math.isfinite(price) or
                        not 1.01<price<1000):continue
                    found.append((stamp,round(price,4)))
            if not found:continue
            found.sort()
            a,b=found[0],found[-1]
            output.append({'market':'1x2','selection':side,'bookmaker':book,
                           'source':'OddsPapi historical','type':'historical_1x2_prices',
                           'first_odd':a[1],'last_odd':b[1],
                           'first_at':datetime.fromtimestamp(a[0],timezone.utc).isoformat(),
                           'last_at':datetime.fromtimestamp(b[0],timezone.utc).isoformat(),
                           'observations':len(found)})
    return output[:9]

def historical_clv(row):
    """Captured vs last observed pregame quote; price movement, NOT EV or bet."""
    f=row.get('fixture') or {}
    if f.get('phase')!='finished':return []
    try:kick=int(f['start_timestamp'])
    except (KeyError,ValueError,TypeError):return []
    previously={}
    for q in row.get('odds_quotes') or []:
        if not isinstance(q,dict) or q.get('market')!='1x2' or q.get('source')!='OddsPapi':continue
        t=parse_ts(q.get('captured_at'))
        if t is None or t>=kick:continue
        try:p=float(q.get('odds'))
        except (ValueError,TypeError):continue
        if not math.isfinite(p) or not 1.01<p<1000:continue
        k=(q.get('bookmaker'),q.get('selection'))
        if k not in previously or previously[k][0]<t:previously[k]=(t,p)
    out=[]
    for item in row.get('oddspapi_historical_quotes') or []:
        if not isinstance(item,dict) or item.get('type')!='historical_1x2_prices':continue
        k=(item.get('bookmaker'),item.get('selection'))
        if k not in previously:continue
        t=parse_ts(item.get('last_at'))
        if t is None or t<previously[k][0] or t>=kick or kick-t>86400:continue
        try:close=float(item['last_odd'])
        except (KeyError,TypeError,ValueError):continue
        if not math.isfinite(close) or not 1.01<close<1000:continue
        out.append({'bookmaker':k[0],'selection':k[1],
                    'captured_odd':round(previously[k][1],4),
                    'historical_last_odd':round(close,4),
                    'movement_pct':round(100*(previously[k][1]/close-1),2),
                    'last_at':item['last_at'],'type':'historical_price_movement_not_ev'})
    return out[:9]

def collect(docs,now_ts,key=None,fetcher=fetch_json,ledger_path=LEDGER,
            enabled=None,sleep_fn=time.sleep):
    now=datetime.fromtimestamp(now_ts,timezone.utc)
    active=(3<=now.hour<=4) if enabled is None else bool(enabled)
    key=os.environ.get('NEXUS_ODDSPAPI_KEY','') if key is None else key
    stats={'status':'disabled' if not active else 'no_finished_fixtures',
           'requests':0,'prices_added':0,'matched':0,'free_endpoint':True,'errors':[]}
    if not active:return stats
    if not key:stats['status']='not_configured';return stats
    path=Path(ledger_path)
    try:record=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    except (OSError,ValueError):stats['status']='ledger_unavailable';return stats
    seen=record.get('attempts') or {}
    if not isinstance(seen,dict):stats['status']='ledger_unavailable';return stats
    day=now.strftime('%Y-%m-%d')
    already=sum(x.get('date')==day for x in seen.values() if isinstance(x,dict))
    if already>=2:stats['status']='daily_limit';return stats
    eligible=[]
    for doc in docs.values():
        if not isinstance(doc,dict):continue
        for match in (doc.get('matches') or {}).values():
            if not isinstance(match,dict):continue
            f=match.get('fixture') or {}
            ident=match.get('oddspapi_fixture_id')
            if f.get('phase')!='finished' or not valid_id(ident) or ident in seen:continue
            try:kick=int(f['start_timestamp'])
            except (ValueError,TypeError,KeyError):continue
            if SINCE<=kick<now_ts and now_ts-kick<=10*86400:eligible.append((kick,ident,match))
    eligible.sort(reverse=True)
    for idx,(_,ident,match) in enumerate(eligible[:2-already]):
        if idx:sleep_fn(5.2)
        seen[ident]={'date':day,'result':'reserved'}
        record.update(attempts=seen,updated_at=now.isoformat())
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(record,ensure_ascii=False)+'\n',encoding='utf-8')
        stats['requests']+=1
        url=API+'?'+urlencode({'fixtureId':ident,'bookmakers':','.join(BOOKS),'apiKey':key})
        try:
            data=fetcher(url)
            if not isinstance(data,dict) or str(data.get('fixtureId'))!=ident:
                raise ValueError('fixture_mismatch')
            found=historical_prices(data,int(match['fixture']['start_timestamp']))
            if found:
                match['oddspapi_historical_quotes']=found
                stats['matched']+=1
                stats['prices_added']+=len(found)
            seen[ident]['result']='collected' if found else 'no_prices'
        except Exception as exc:
            # No exception message or URL: either might expose an API credential.
            code=getattr(exc,'code',None)
            stats['errors'].append('http_'+str(code) if isinstance(code,int) else 'unavailable')
            seen[ident]['result']='failed'
        path.write_text(json.dumps(record,ensure_ascii=False)+'\n',encoding='utf-8')
    if stats['requests']:stats['status']='partial' if stats['errors'] else 'checked'
    return stats

def main():
    now=datetime.now(timezone.utc)
    docs={}
    for offset in range(11):
        day=(now-timedelta(days=offset)).strftime('%Y-%m-%d')
        p=H/(day+'.json')
        if p.exists():
            try:docs[day]=json.loads(p.read_text(encoding='utf-8'))
            except (OSError,ValueError):pass
    stats=collect(docs,int(now.timestamp()))
    if stats['requests'] and stats['matched']:
        for day,doc in docs.items():
            p=H/(day+'.json')
            if p.exists():
                tmp=p.with_suffix('.tmp')
                tmp.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
                tmp.replace(p)
    print('ODDSPAPI_HIST:',json.dumps(stats,sort_keys=True))
    return stats

if __name__=='__main__':main()
