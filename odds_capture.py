#!/usr/bin/env python3
"""Registra somente odds reais pré-jogo. EV+ requer modelo anterior ao jogo."""
import json, re, math
from pathlib import Path
from urllib.request import Request,urlopen
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parent
HISTORY=ROOT/'history'
NOW=datetime.now(timezone.utc)
BR=timezone(timedelta(hours=-3))
def read(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}
def save(path,doc):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    tmp.replace(path)
def get(url):
    req=Request(url,headers={'Accept':'application/json','User-Agent':'NEXUS 5.29'})
    with urlopen(req,timeout=5) as resp:data=resp.read(1600001)
    if len(data)>1600000:raise ValueError('Resposta grande demais')
    doc=json.loads(data)
    if not isinstance(doc,dict):raise ValueError('JSON inválido')
    return doc
def price(v):
    if not isinstance(v,dict):return None
    for key in ('decimalOdds','decimalValue','decimal'):
        try:
            val=float(v[key])
            if math.isfinite(val) and 1.01<=val<=1000:return round(val,4)
        except (ValueError,TypeError,KeyError):pass
    try:
        american=float(v.get('moneyLine',v.get('moneyline')))
        if math.isfinite(american) and 100<=abs(american)<=100000:
            return round(1+(american/100 if american>0 else 100/abs(american)),4)
    except (ValueError,TypeError):pass
    return None
def threeway(row):
    if not isinstance(row,dict):return {}
    raw={'home':price(row.get('homeTeamOdds')),'draw':price(row.get('drawOdds')),'away':price(row.get('awayTeamOdds'))}
    return {k:v for k,v in raw.items() if v is not None}
def kickoff(event):
    for candidate in (event.get('date'),):
        try:
            dt=datetime.fromisoformat(str(candidate).replace('Z','+00:00'))
            if dt.tzinfo:return int(dt.timestamp())
        except (TypeError,ValueError):pass
    return None
def final_score(f):
    if f.get('phase')!='finished':return None
    m=re.fullmatch(r'(\d{1,2})-(\d{1,2})',str(f.get('score')))
    return (int(m[1]),int(m[2])) if m else None
def form_prediction(fixture,archive,cutoff):
    """Experimental, thresholded historical home/away results; no future leakage."""
    hg=[];ag=[];league_games=0
    for other in archive:
        if other.get('league')!=fixture.get('league'):continue
        start=other.get('start_timestamp')
        try:
            if start is None or float(start)>=cutoff:continue
        except (TypeError,ValueError):continue
        sc=final_score(other)
        if sc is None:continue
        league_games+=1
        if other.get('home')==fixture.get('home'):hg.append(sc)
        if other.get('away')==fixture.get('away'):ag.append(sc)
    if len(hg)<8 or len(ag)<8 or league_games<35:return None
    hg=hg[-20:];ag=ag[-20:]
    denom=len(hg)+len(ag)+9
    probs={'home':(sum(x>y for x,y in hg)+sum(x<y for x,y in ag)+3)/denom,
           'draw':(sum(x==y for x,y in hg)+sum(x==y for x,y in ag)+3)/denom,
           'away':(sum(x<y for x,y in hg)+sum(x>y for x,y in ag)+3)/denom}
    return probs,min(len(hg),len(ag))
def main():
    day=NOW.astimezone(BR).date()
    archive=[]
    for file in sorted(HISTORY.glob('20??-??-??.json')):
        for row in (read(file).get('matches') or {}).values():
            if isinstance(row,dict) and isinstance(row.get('fixture'),dict):
                archive.append(row['fixture'])
    stats={'checked_at':NOW.isoformat(),'matches_queried':0,'quotes_recorded':0,
           'signals_frozen':0,'signals_settled':0,'errors':[]}
    for prev in (0,1):
        file=HISTORY/((day-timedelta(days=prev)).isoformat()+'.json')
        doc=read(file)
        if not doc:continue
        changed=False
        for row in (doc.get('matches') or {}).values():
            if not isinstance(row,dict):continue
            f=row.get('fixture')
            if not isinstance(f,dict):continue
            match=re.fullmatch(r'espn-([a-z0-9.]{2,40})-(\d{1,16})',str(f.get('id','')))
            if not match:continue
            pending=any(x.get('status')=='pending' for x in row.get('paper_signals') or [])
            if f.get('phase')!='scheduled' and not pending:continue
            if stats['matches_queried']>=12:break
            stats['matches_queried']+=1
            try:
                packet=get(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{match[1]}/summary?event={match[2]}')
                comps=(packet.get('header') or {}).get('competitions') or []
                event=comps[0] if comps and isinstance(comps[0],dict) else {}
                start=kickoff(event)
                if start:f['start_timestamp']=start;changed=True
                state=str((((event.get('status') or {}).get('type') or {}).get('state') or ''))
                if state=='post':
                    players=event.get('competitors') or []
                    h=next((x for x in players if x.get('homeAway')=='home'),None)
                    a=next((x for x in players if x.get('homeAway')=='away'),None)
                    if h and a and str(h.get('score','')).isdigit() and str(a.get('score','')).isdigit():
                        f['phase']='finished';f['score']=str(h['score'])+'-'+str(a['score']);changed=True
                result=final_score(f)
                if result:
                    winner='home' if result[0]>result[1] else 'away' if result[0]<result[1] else 'draw'
                    for signal in row.get('paper_signals') or []:
                        if signal.get('status')=='pending' and signal.get('market')=='1x2':
                            signal['status']='settled';signal['won']=(signal.get('selection')==winner)
                            signal['settled_at']=NOW.isoformat()
                            stats['signals_settled']+=1;changed=True
                if not start or NOW.timestamp()>=start or f.get('phase')!='scheduled':continue
                offers=packet.get('pickcenter') or event.get('odds') or []
                if not isinstance(offers,list):continue
                for offer in offers[:3]:
                    prices=threeway(offer)
                    if len(prices)!=3:continue
                    provider=offer.get('provider') or {}
                    bookmaker=str((provider.get('name') if isinstance(provider,dict) else '') or offer.get('providerName') or 'Não informado')
                    for side,quote in prices.items():
                        existing=row.setdefault('odds_quotes',[])
                        if not any(q.get('market')=='1x2' and q.get('selection')==side for q in existing):
                            existing.append({'market':'1x2','selection':side,'odds':quote,'captured_at':NOW.isoformat(),
                                             'source':'ESPN','bookmaker':bookmaker})
                            stats['quotes_recorded']+=1;changed=True
                    forecast=form_prediction(f,archive,NOW.timestamp())
                    if forecast:
                        probabilities,sample=forecast
                        for side,quote in prices.items():
                            ev=100*(probabilities[side]*quote-1)
                            if ev<=5:continue
                            signals=row.setdefault('paper_signals',[])
                            if any(x.get('market')=='1x2' and x.get('selection')==side for x in signals):continue
                            signals.append({'market':'1x2','selection':side,'odds':quote,'captured_at':NOW.isoformat(),
                                            'probability':round(probabilities[side]*100,2),'ev_pct':round(ev,2),
                                            'model':'empirical-form-v1-experimental','sample_size':sample,'status':'pending',
                                            'source':'ESPN','bookmaker':bookmaker})
                            stats['signals_frozen']+=1;changed=True
                    break
            except Exception as exc:stats['errors'].append(str(exc)[:100])
        if changed:save(file,doc)
    save(HISTORY/'odds_status.json',stats)
    print(json.dumps(stats,ensure_ascii=False))
if __name__=='__main__':main()
