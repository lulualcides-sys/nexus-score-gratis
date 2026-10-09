#!/usr/bin/env python3
"""Coletor de alertas de pressão esportiva independente do PC.

Porta as três regras de pressão do NEXUS web 5.29: 🔥 🧨 🚨.
Não pretende representar outras regras da instalação desktop.
Sem preço e probabilidade calibrada, EV+ é indisponível.
"""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,math,re,hashlib

ROOT=Path(__file__).resolve().parent
H=ROOT/'history'
JOURNAL=H/'signal_registry.json'
WINDOWS=(5,10,15)
COOLDOWN=12
MAX_ALERTS=10000

def read(path):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):
        return {}

def goalscore(value):
    m=re.fullmatch(r'\s*(\d{1,2})\s*[-–:]\s*(\d{1,2})\s*',str(value or ''))
    return (int(m[1]),int(m[2])) if m else None

def samples(row):
    result={}
    for entry in (row.get('thermometer') or {}).get('points') or []:
        if not isinstance(entry,dict):continue
        try:
            minute=int(entry.get('minute'));val=float(entry.get('value'))
        except (TypeError,ValueError,OverflowError):continue
        if 1<=minute<=150 and math.isfinite(val) and abs(val)<=1000:
            result[minute]=val
    return result

def pressure_window(points,end,n):
    values=[v for m,v in points.items() if end-n<m<=end]
    expected=min(n,max(1,end))
    if len(values)<math.ceil(expected*.8):
        return {'valid':False,'samples':len(values),'expected':expected}
    home=sum(max(0,v) for v in values)/len(values)
    away=sum(max(0,-v) for v in values)/len(values)
    intensity=max(home,away);difference=abs(home-away)
    level=('CRITICO' if intensity>=62 and difference>=18 else
           'FORTE' if intensity>=43 and difference>=12 else
           'OBSERVAR' if intensity>=25 else 'FRIO')
    side='home' if home>away+2 else 'away' if away>home+2 else None
    return {'valid':True,'samples':len(values),'expected':expected,
            'score':round(min(100,max(0,intensity/80*100))),
            'level':level,'team':side,'difference':round(difference,1),
            'home_force':round(home,1),'away_force':round(away,1)}

def active_signals(fixture,row,observed_at):
    if fixture.get('phase')!='live':return []
    try: minute=int(fixture.get('minute'))
    except (TypeError,ValueError):return []
    if not 10<=minute<=120:return []
    points=samples(row)
    if not points or max(points)<minute-1:return []
    ten=pressure_window(points,minute,10)
    five=pressure_window(points,minute,5)
    if not ten['valid'] or not five['valid'] or not ten['team']:return []
    side=ten['team']
    side_stats=(row.get('stats') or {}).get(side) or {}
    def stat(k):
        try:
            n=side_stats.get(k)
            if n is None or n=='':return None
            v=float(n)
            return v if math.isfinite(v) and v>=0 else None
        except (TypeError,ValueError):return None
    shots=stat('shots_on');chances=stat('big_chances')
    strong=ten['level'] in ('FORTE','CRITICO')
    found=[]
    if strong:found.append(('🔥','pressao_forte_10min'))
    if strong and five['score']>=65:found.append(('🧨','pressao_total_5_10min'))
    if strong and ten['score']>=70 and five['score']>=65 and shots is not None and shots>=3 and chances is not None and chances>=1:
        found.append(('🚨','alerta_cruzado_gol'))
    fid=str(fixture.get('id') or '')
    if not fid or not fixture.get('home') or not fixture.get('away'):return []
    result=[]
    for icon,rule in found:
        result.append({'match_id':fid,'home':str(fixture['home'])[:95],
            'away':str(fixture['away'])[:95],'league':str(fixture.get('league') or '')[:95],
            'minute':minute,'team':side,'icon':icon,'rule':rule,
            'market':'observacao_de_gol','captured_at':observed_at,
            'score_at_alert':str(fixture.get('score') or '')[:15],
            'pressure10':ten,'pressure5':five,'shots_on':shots,'big_chances':chances,
            'source':str(fixture.get('source') or '')[:45],
            'odds':None,'ev_pct':None,'ev_status':'indisponivel_sem_preco_e_modelo_calibrado',
            'outcomes':{str(n):'pendente' for n in WINDOWS},
            'note':'Sinal de pressão observado, não previsão calibrada ou EV+ confirmado.'})
    return result

def goal_events(row,start,end):
    unique=set()
    for item in row.get('events') or []:
        if not isinstance(item,dict) or item.get('type')!='goal':continue
        try: m=int(item.get('minute'))
        except (TypeError,ValueError):continue
        if start<m<=end and item.get('side') in ('home','away'):
            unique.add((m,item['side']))
    return [{'minute':m,'team':side} for m,side in sorted(unique)]

def resolve(item,fixture,row):
    start=int(item.get('minute') or 0)
    try: current_minute=int(fixture.get('minute') or 0)
    except (TypeError,ValueError):current_minute=0
    ended=fixture.get('phase')=='finished'
    at_signal=goalscore(item.get('score_at_alert'))
    now=goalscore(fixture.get('score'))
    windows=item.setdefault('outcomes',{})
    for n in WINDOWS:
        key=str(n)
        # Resultado confirmado fica congelado no banco.
        if windows.get(key) not in ('pendente','indeterminado'):continue
        confirmed=goal_events(row,start,start+n)
        if confirmed:
            windows[key]='gol_confirmado'
            item['goals_after_alert']=goal_events(row,start,start+max(WINDOWS))
        elif ended and start+n>90:
            windows[key]='janela_incompleta'
        elif not ended and current_minute<start+n:
            windows[key]='pendente'
        elif at_signal is not None and now is not None and now==at_signal:
            windows[key]='sem_gol_confirmado'
        else:
            windows[key]='indeterminado'
    return item

def update(docs,previous=None,observed_at=None):
    when=observed_at or datetime.now(timezone.utc).isoformat()
    previous=previous or {}
    entries=[dict(x) for x in previous.get('items',[]) if isinstance(x,dict) and x.get('id')]
    ids={x['id'] for x in entries}
    current={}
    for day,doc in sorted(docs.items(),reverse=True):
        for key,row in (doc.get('matches') or {}).items():
            if not isinstance(row,dict):continue
            fixture=row.get('fixture') or {}
            if not isinstance(fixture,dict):continue
            fid=str(fixture.get('id') or key)
            if not fid:continue
            current.setdefault(fid,(fixture,row))
            for new in active_signals(fixture,row,when):
                if any(e.get('match_id')==fid and e.get('rule')==new['rule']
                       and e.get('team')==new['team']
                       and abs(int(e.get('minute') or 0)-new['minute'])<COOLDOWN
                       for e in entries):continue
                keytext='|'.join((fid,new['team'],new['rule'],str(new['minute'])))
                new['id']=hashlib.sha256(keytext.encode()).hexdigest()[:20]
                if new['id'] in ids:continue
                ids.add(new['id']);entries.append(new)
    for entry in entries:
        if entry.get('match_id') in current:
            fixture,row=current[entry['match_id']]
            resolve(entry,fixture,row)
    entries.sort(key=lambda x:str(x.get('captured_at') or ''),reverse=True)
    return {'schema':1,'updated_at':when,'items':entries[:MAX_ALERTS],
        'notice':'Alertas de pressão verificados quando possível. Não representam apostas nem EV+.'}

def main():
    today=(datetime.now(timezone.utc)-timedelta(hours=3)).date()
    docs={d:read(H/(d+'.json')) for d in
         ((today-timedelta(days=n)).isoformat() for n in range(4))}
    old=read(JOURNAL)
    new=update(docs,old)
    if not JOURNAL.exists() or new['items']!=old.get('items',[]):
        H.mkdir(exist_ok=True)
        JOURNAL.write_text(json.dumps(new,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print('NEXUS CLOUD: registros de alertas',len(new['items']),
          '(sem EV inventado; 5/10/15 min auditáveis)')

if __name__=='__main__':
    main()
