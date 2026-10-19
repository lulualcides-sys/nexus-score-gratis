#!/usr/bin/env python3
"""Coleta historica OddsPapi: gratuito, somente partidas finalizadas e IDs conferidos."""
import json,math,os,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from espn_scoreboard_odds import parse_ts
from oddspapi_odds import BASE,BOOKMAKERS

HISTORY=Path(__file__).resolve().parent/'history'
SELS={'101':'home','102':'draw','103':'away'}

def summarize_history(packet,fixture_id,kickoff):
    if not isinstance(packet,dict) or str(packet.get('fixtureId'))!=str(fixture_id):
        return []
    results=[]
    for bookmaker in BOOKMAKERS:
        markets=((packet.get('bookmakers') or {}).get(bookmaker) or {}).get('markets') or {}
        outcomes=(markets.get('101') or {}).get('outcomes') or {}
        prices={}
        for oid,selection in SELS.items():
            items=[]
            for values in ((outcomes.get(oid) or {}).get('players') or {}).values():
                if not isinstance(values,list):continue
                for offer in values:
                    if not isinstance(offer,dict):continue
                    ts=parse_ts(offer.get('createdAt'))
                    try:odd=float(offer.get('price'))
                    except (TypeError,ValueError,OverflowError):continue
                    if ts is None or ts>=kickoff or not math.isfinite(odd) or not 1.01<odd<1000:continue
                    items.append((ts,round(odd,4)))
            if not items:break
            items.sort()
            prices[selection]={'opening':items[0][1],
                 'opening_at':datetime.fromtimestamp(items[0][0],timezone.utc).isoformat(),
                 'closing':items[-1][1],
                 'closing_at':datetime.fromtimestamp(items[-1][0],timezone.utc).isoformat(),
                 'observations':len(items)}
        if set(prices)==set(SELS.values()):
            results.append({'market':'1x2','bookmaker':bookmaker,
                'phase':'historical_closing','prices':prices})
    return results

def fetch_history(fixture_id,key):
    url=BASE+'/historical-odds?'+urlencode({'apiKey':key,'fixtureId':fixture_id,
                                            'bookmakers':','.join(BOOKMAKERS)})
    with urlopen(Request(url,headers={'Accept':'application/json'}),timeout=16) as r:
        raw=r.read(7500001)
    if len(raw)>7500000:raise ValueError('Resposta historica muito grande')
    return json.loads(raw)

def collect(docs,now_ts,key=None,fetcher=fetch_history,limit=2,sleep_fn=time.sleep):
    key=os.getenv('NEXUS_ODDSPAPI_KEY','') if key is None else key
    state={'status':'not_configured' if not key else 'no_eligible',
           'checked':0,'stored':0,'billable_requests':0,'errors':[]}
    if not key:return state
    eligible=[]
    for day,doc in docs.items():
        for mid,row in (doc.get('matches') or {}).items():
            if not isinstance(row,dict):continue
            fixture=row.get('fixture') or {}
            fid=row.get('oddspapi_fixture_id')
            try:kickoff=int(fixture.get('start_timestamp') or 0)
            except (TypeError,ValueError):continue
            if (fixture.get('phase')!='finished' or not isinstance(fid,str)
                or not fid.startswith('id') or len(fid)>80 or not 0<now_ts-kickoff<40*86400
                or row.get('oddspapi_history')):continue
            eligible.append((kickoff,day,mid,fid))
    eligible.sort(reverse=True)
    for i,(kickoff,day,mid,fid) in enumerate(eligible[:max(0,min(limit,2))]):
        if i:sleep_fn(5.2) # /historical-odds exige 5000 ms entre consultas
        state['checked']+=1
        try:
            values=summarize_history(fetcher(fid,key),fid,kickoff)
            if values:
                docs[day]['matches'][mid]['oddspapi_history']={
                    'retrieved_at':datetime.fromtimestamp(now_ts,timezone.utc).isoformat(),
                    'scope':'historical_only','source':'OddsPapi','markets':values}
                state['stored']+=1
        except Exception as e:
            if len(state['errors'])<3:state['errors'].append(type(e).__name__)
    state['status']='partial' if state['errors'] else 'checked' if state['checked'] else 'no_eligible'
    return state

def main():
    now=datetime.now(timezone.utc)
    docs={}
    for delta in range(40):
        day=(now-timedelta(days=delta)).date().isoformat()
        path=HISTORY/(day+'.json')
        if path.exists():
            try:docs[day]=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,ValueError):continue
    result=collect(docs,now.timestamp())
    if result['stored']:
        for day,doc in docs.items():
            path=HISTORY/(day+'.json')
            old=json.loads(path.read_text(encoding='utf-8'))
            if doc==old:continue
            tmp=path.with_suffix('.tmp')
            tmp.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
            tmp.replace(path)
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
