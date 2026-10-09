#!/usr/bin/env python3
"""Completa os últimos três dias do FotMob (não só o dia atual).

Cada partida é arquivada no dia do início em Brasília; não cria placar,
tempo, odds ou scouts sintéticos. Preserva coletas anteriores de cada jogo.
"""
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from coletar import HISTORY, DAY, BR, NOW, fotmob_list, read, write

def local_day(f):
    try:
        ts=int(f.get('start_timestamp'))
        if ts>0:return datetime.fromtimestamp(ts,BR).date().isoformat()
    except (TypeError,ValueError,OverflowError):pass
    return None

def assign_fixture(row,fixture):
    """Snapshot novo atualiza metadados sem excluir scouts históricos."""
    f=row.get('fixture') or {}
    if (f.get('phase')=='finished' and fixture.get('phase')!='finished'):
        return row
    if f.get('phase')=='finished' and fixture.get('phase')=='finished':
        if f.get('score')!=fixture.get('score'):
            # Conflito de placar: conservar valor já observado para auditoria.
            return row
    row['fixture']={**f,**fixture}
    row.setdefault('sources',[])
    if 'FotMob' not in row['sources']:row['sources'].append('FotMob')
    return row

def run():
    today=date.fromisoformat(DAY)
    dates=[(today-timedelta(days=i)).isoformat() for i in range(3)]
    docs={day:read(HISTORY/(day+'.json')) for day in dates}
    report={'updated_at':NOW.isoformat(),'days':dates,'queries':0,
      'games_added':0,'games_updated':0,'failed':[]}
    # Consultar também o dia UTC seguinte: jogos das 21-23h BRT podem
    # constar no calendário UTC do dia seguinte.
    queries=dates+[ (today+timedelta(days=1)).isoformat()]
    with ThreadPoolExecutor(max_workers=4) as pool:
        future={pool.submit(fotmob_list,d):d for d in queries}
        for task in as_completed(future):
            requested=future[task]
            report['queries']+=1
            try:
                games=task.result()
            except Exception as e:
                report['failed'].append(requested+': '+str(e)[:120])
                continue
            for f in games:
                day=local_day(f)
                if day not in docs:continue
                matches=docs[day].setdefault('matches',{})
                mid=f.get('id')
                if not isinstance(mid,str) or not mid.startswith('fotmob-'):continue
                existed=mid in matches
                assign_fixture(matches.setdefault(mid,{}),f)
                report['games_updated' if existed else 'games_added']+=1
    for day,doc in docs.items():
        if doc:
            doc['day']=day
            doc['updated_at']=NOW.isoformat()
            write(HISTORY/(day+'.json'),doc)
    write(HISTORY/'fotmob_three_days_status.json',report)
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':run()
