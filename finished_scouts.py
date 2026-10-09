#!/usr/bin/env python3
"""NEXUS: preenche scouts de jogos encerrados do FotMob sem fabricar estatisticas."""
import json
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta
from urllib.parse import urlencode
from coletar import HISTORY,DAY,NOW,fetch,read,write,stats

PER_RUN=75
def detail(mid):
    last_error=None
    for endpoint in ('https://www.fotmob.com/api/data/matchDetails?','https://www.fotmob.com/api/matchDetails?'):
        try:
            packet=fetch(endpoint+urlencode({'matchId':mid}),timeout=8)
            return stats(packet)
        except Exception as exc:last_error=exc
    raise RuntimeError(str(last_error or 'detalhes indisponiveis'))

def main():
    date=datetime.strptime(DAY,'%Y-%m-%d').date()
    days=[(date-timedelta(days=i)).isoformat() for i in range(3)]
    docs={day:read(HISTORY/(day+'.json')) for day in days}
    pending=[]
    for day,doc in docs.items():
        for key,row in (doc.get('matches') or {}).items():
            if not str(key).startswith('fotmob-'):continue
            if (row.get('fixture') or {}).get('phase')!='finished':continue
            existing=row.get('stats') or {}
            if any(len(existing.get(side) or {})>=6 for side in ('home','away')):continue
            mid=str(key).split('-')[-1]
            if mid.isdigit():pending.append((day,key,mid))
    # Ordem mais recente para detalhes esportivos mais relevantes.
    pending.sort(reverse=True)
    report={'at':NOW.isoformat(),'eligible':len(pending),'attempts':min(len(pending),PER_RUN),
            'enriched':0,'empty':0,'errors':[]}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures={pool.submit(detail,mid):(day,key) for day,key,mid in pending[:PER_RUN]}
        for future in as_completed(futures):
            day,key=futures[future]
            try:incoming=future.result()
            except Exception as err:
                if len(report['errors'])<12:report['errors'].append(str(err)[:110])
                continue
            if not any(incoming.get(side) for side in ('home','away')):
                report['empty']+=1
                continue
            row=docs[day]['matches'][key]
            old=row.setdefault('stats',{})
            for side in ('home','away'):
                src=incoming.get(side) or {}
                dest=old.setdefault(side,{})
                for k,v in src.items():
                    if k not in dest:dest[k]=v
            report['enriched']+=1
    for day,doc in docs.items():
        if doc:write(HISTORY/(day+'.json'),doc)
    write(HISTORY/'finished_scouts_status.json',report)
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
