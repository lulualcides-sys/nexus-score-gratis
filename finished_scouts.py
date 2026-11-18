#!/usr/bin/env python3
"""NEXUS: preenche scouts de jogos encerrados do FotMob sem fabricar estatisticas."""
import json
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta
from urllib.parse import urlencode
from coletar import HISTORY,DAY,NOW,fetch,read,write,stats
from major_league_scope import catalog_rank

PER_RUN=75
# Partida que voltou sem scouts: nova tentativa só depois desta janela e no
# máximo EMPTY_MAX_TRIES vezes, para não ocupar todas as vagas toda hora.
EMPTY_RETRY_HOURS=6
EMPTY_MAX_TRIES=3
def detail(mid):
    last_error=None
    for endpoint in ('https://www.fotmob.com/api/data/matchDetails?','https://www.fotmob.com/api/matchDetails?'):
        try:
            packet=fetch(endpoint+urlencode({'matchId':mid}),timeout=8)
            return stats(packet)
        except Exception as exc:last_error=exc
    raise RuntimeError(str(last_error or 'detalhes indisponiveis'))

def _empty_blocked(row,now):
    marker=row.get('scouts_empty')
    if not isinstance(marker,dict):return False
    try:tries=int(marker.get('tries') or 0)
    except (TypeError,ValueError):tries=0
    if tries>=EMPTY_MAX_TRIES:return True
    try:
        checked=datetime.fromisoformat(str(marker.get('checked_at')).replace('Z','+00:00'))
        return (now-checked).total_seconds()<EMPTY_RETRY_HOURS*3600
    except (TypeError,ValueError):return False


def _candidates(docs,now):
    for day,doc in docs.items():
        for key,row in ((doc or {}).get('matches') or {}).items():
            if not str(key).startswith('fotmob-'):continue
            fixture=row.get('fixture') or {}
            if fixture.get('phase')!='finished':continue
            existing=row.get('stats') or {}
            if any(len(existing.get(side) or {})>=6 for side in ('home','away')):continue
            if _empty_blocked(row,now):continue
            mid=str(key).split('-')[-1]
            if not mid.isdigit():continue
            lid=fixture.get('league_id') if fixture.get('league_id_verified') is True else ''
            try:start=int(fixture.get('start_timestamp') or 0)
            except (TypeError,ValueError):start=0
            yield (catalog_rank(lid),-start,day,key,mid)


def count_pending(docs,now):
    return sum(1 for _ in _candidates(docs,now))


def select_pending(docs,now,limit):
    """Ligas do catálogo primeiro; dentro de cada nível, as mais recentes."""
    ranked=sorted(_candidates(docs,now))
    return [(day,key,mid) for _,_,day,key,mid in ranked[:max(0,limit)]]


def mark_empty(row,now):
    marker=row.get('scouts_empty') if isinstance(row.get('scouts_empty'),dict) else {}
    try:tries=int(marker.get('tries') or 0)
    except (TypeError,ValueError):tries=0
    row['scouts_empty']={'checked_at':now.isoformat(),'tries':tries+1}


def main():
    date=datetime.strptime(DAY,'%Y-%m-%d').date()
    days=[(date-timedelta(days=i)).isoformat() for i in range(3)]
    docs={day:read(HISTORY/(day+'.json')) for day in days}
    pending=select_pending(docs,NOW,PER_RUN)
    eligible=count_pending(docs,NOW)
    report={'at':NOW.isoformat(),'eligible':eligible,'attempts':len(pending),
            'enriched':0,'empty':0,'errors':[],
            'priority':'ligas principais > ampliadas > demais; vazios aguardam '+str(EMPTY_RETRY_HOURS)+' h'}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures={pool.submit(detail,mid):(day,key) for day,key,mid in pending}
        for future in as_completed(futures):
            day,key=futures[future]
            try:incoming=future.result()
            except Exception as err:
                if len(report['errors'])<12:report['errors'].append(str(err)[:110])
                continue
            row=docs[day]['matches'][key]
            if not any(incoming.get(side) for side in ('home','away')):
                report['empty']+=1
                mark_empty(row,NOW)
                continue
            row.pop('scouts_empty',None)
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
