#!/usr/bin/env python3
"""Coletor de alertas de pressão esportiva independente do PC.

Porta as três regras de pressão do NEXUS web 5.29: 🔥 🧨 🚨.
Não pretende representar outras regras da instalação desktop.
Sem preço e probabilidade calibrada, EV+ é indisponível.
"""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,math,re,hashlib,sys,subprocess

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

ICON_RULES={
    '🧨':'pressao_total_5_10min',
    '🔥':'pressao_forte_10min',
    '🎯':'chutes_no_alvo_5',
    '🚩':'escanteios_6',
    '⚡':'pressao_ofensiva_18',
    '💣':'grandes_chances_3',
    '⚔️':'ataques_perigosos_25',
    '🟥':'expulsao_confirmada',
    '⏱️':'tensao_tardia_70',
    '🥶':'jogo_frio',
    '🚨':'alerta_cruzado_gol',
}
GRAPH_ICONS={'🧨','🔥','⚡','⏱️','🥶','🚨'}
PRIORITY=['🔥','🧨','⚡','⏱️','🥶','🚨','🎯','🚩','💣','⚔️','🟥']
STAT_FIELDS={'🎯':('shots_on',5),'🚩':('corners',6),
             '💣':('big_chances',3),'⚔️':('dangerous_attacks',25)}

def active_signals(fixture,row,observed_at):
    """O motor é o port das 12 regras do NEXUS Original 5.29, não filtros inventados.

    Os scouts acumulados descrevem o ESTADO na captura, nunca o instante
    real de um chute. Grafico atrasado não produz alerta temporal.
    """
    from nexus_original_529_rules import board as original_board
    if fixture.get('phase')!='live':return []
    try:minute=int(fixture.get('minute'))
    except (TypeError,ValueError):return []
    if not 1<=minute<=120:return []
    fid=str(fixture.get('id') or '')
    if not fid or not fixture.get('home') or not fixture.get('away'):return []
    points=samples(row)
    snap=[{'minute':m,'value':v} for m,v in points.items()]
    stats=row.get('stats') or {}
    incidents=[]
    for e in row.get('events') or []:
        if not isinstance(e,dict) or e.get('type')!='red_card':continue
        side=e.get('side')
        if side in ('home','away'):
            incidents.append({'emoji':'🟥','team':side.upper(),'minute':e.get('minute')})
    original=original_board(snap,minute,stats,incidents)
    pressure_fresh=bool(points) and max(points)>=minute-1
    valid=[]
    for x in original['active']:
        icon=x['emoji']
        if icon not in ICON_RULES:continue
        # O signal_timeline.py Original exige pelo menos 10 minutos para sinais no grafico.
        if icon in GRAPH_ICONS and (minute<10 or not pressure_fresh):continue
        valid.append(x)
    valid.sort(key=lambda x:PRIORITY.index(x['emoji']) if x['emoji'] in PRIORITY else 99)
    result=[]
    for x in valid:
        icon=x['emoji'];team=x.get('team')
        # O NEXUS original nao aponta uma equipe ao red_card sem evidência.
        if icon=='🟥' and team not in ('HOME','AWAY'):
            matched={i.get('team') for i in incidents if i.get('team') in ('HOME','AWAY')}
            team=next(iter(matched)) if len(matched)==1 else None
        side=team.lower() if team in ('HOME','AWAY') else 'unknown'
        own=stats.get(side) or {}
        def stat(key):
            try:
                raw=own.get(key)
                value=float(raw) if raw is not None else None
                return round(value,2) if value is not None and math.isfinite(value) else None
            except (ValueError,TypeError):return None
        basis=('pressure_window' if icon in GRAPH_ICONS else
               'confirmed_event' if icon=='🟥' else 'cumulative_stat_snapshot')
        item={'match_id':fid,'home':str(fixture['home'])[:95],
              'away':str(fixture['away'])[:95],
              'league':str(fixture.get('league') or '')[:95],
              'minute':minute,'team':side,'icon':icon,'rule':ICON_RULES[icon],
              'basis':basis,'market':'observacao_de_gol',
              'captured_at':observed_at,
              'score_at_alert':str(fixture.get('score') or '')[:15],
              'pressure10':original['pressure10'],'pressure5':original['pressure5'],
              'shots_on':stat('shots_on'),'big_chances':stat('big_chances'),
              'source':str(fixture.get('source') or '')[:45],
              'original_engine':'NEXUS SCORE Original 5.29',
              'odds':None,'ev_pct':None,
              'ev_status':'indisponivel_sem_preco_e_modelo_calibrado',
              'outcomes':{str(n):'pendente' for n in WINDOWS},
              'note':str(x.get('reason') or '')[:200]}
        if basis=='cumulative_stat_snapshot':
            field,threshold=STAT_FIELDS[icon]
            value=stat(field)
            item['cumulative_stat']={'field':field,'value':value,
                                     'threshold':threshold}
            item['note']='Estatística acumulada na captura; não marca o minuto real do evento. '+item['note']
        if basis=='confirmed_event':
            item['note']='Expulsão confirmada pela fonte, não é previsão de gol.'
        result.append(item)
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

def diagnostics(docs):
    """Auditoria da coleta: zero alerta nao significa motor desligado."""
    current={}
    for day,doc in sorted(docs.items(),reverse=True):
        for key,row in (doc.get('matches') or {}).items():
            if not isinstance(row,dict):continue
            fixture=row.get('fixture') or {}
            if not isinstance(fixture,dict):continue
            match_id=str(fixture.get('id') or key)
            if match_id:current.setdefault(match_id,(fixture,row))
    counters={'matches_checked':len(current),'matches_live':0,
              'with_pressure':0,'fresh_pressure':0,
              'valid_10min':0,'valid_5min':0,
              'strong_10min':0,'matches_with_signals':0}
    for f,row in current.values():
        if f.get('phase')!='live':continue
        counters['matches_live']+=1
        try:m=int(f.get('minute'))
        except (ValueError,TypeError):continue
        pts=samples(row)
        if not pts:continue
        counters['with_pressure']+=1
        if max(pts)<m-1:continue
        counters['fresh_pressure']+=1
        ten=pressure_window(pts,m,10);five=pressure_window(pts,m,5)
        if ten['valid']:counters['valid_10min']+=1
        if five['valid']:counters['valid_5min']+=1
        if ten['valid'] and ten.get('level') in ('FORTE','CRITICO'):
            counters['strong_10min']+=1
        if active_signals(f,row,'audit'):counters['matches_with_signals']+=1
    return counters

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
            if fid:current.setdefault(fid,(fixture,row))
    # Um jogo duplicado em um arquivo antigo nunca pode disparar um
    # "novo" alerta quando o registro mais recente ja esta encerrado.
    for fid,(fixture,row) in current.items():
        for new in active_signals(fixture,row,when):
            if any(e.get('match_id')==fid and e.get('rule')==new['rule']
                   and e.get('team')==new['team']
                   and (new.get('basis')=='cumulative_stat_snapshot' or
                        abs(int(e.get('minute') or 0)-new['minute'])<COOLDOWN)
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
        'diagnostics':diagnostics(docs),
        'notice':'Alertas de pressão verificados quando possível. Não representam apostas nem EV+.'}

def merge_journals(*journals):
    """Mescla registros de coletas diferentes pelo ID, sem perder alertas."""
    collected={}
    rank={'pendente':0,'indeterminado':1,'janela_incompleta':2,
          'sem_gol_confirmado':3,'gol_confirmado':4}
    for doc in journals:
        if not isinstance(doc,dict):continue
        for raw in doc.get('items') or []:
            if not isinstance(raw,dict) or not raw.get('id'):continue
            key=raw['id']
            if key not in collected:
                item=dict(raw)
                item['outcomes']=dict(raw.get('outcomes') or {})
                collected[key]=item
                continue
            item=collected[key]
            for field,value in raw.items():
                if field not in ('outcomes','goals_after_alert') and item.get(field) is None:
                    item[field]=value
            merged=item.setdefault('outcomes',{})
            for horizon,value in (raw.get('outcomes') or {}).items():
                prev=merged.get(horizon,'pendente')
                if set((prev,value))==set(('gol_confirmado','sem_gol_confirmado')):
                    merged[horizon]='indeterminado'
                    item['outcome_conflict']=True
                elif rank.get(value,-1)>rank.get(prev,-1):
                    merged[horizon]=value
            goals={(g.get('minute'),g.get('team')):g for g in
                    (item.get('goals_after_alert') or [])+(raw.get('goals_after_alert') or [])
                    if isinstance(g,dict)}
            if goals:item['goals_after_alert']=sorted(goals.values(),key=lambda g:g.get('minute') or 0)
    newest=max((d for d in journals if isinstance(d,dict)),
               key=lambda d:str(d.get('updated_at') or ''),default={})
    # Dois jobs podem observar o mesmo total de scouts em minutos distintos.
    # Cumulativos sao unicos por equipe/regra/partida, conservar a 1ª captura.
    deduped=[]
    observed=set()
    for item in sorted(collected.values(),key=lambda x:str(x.get('captured_at') or '')):
        if item.get('basis')=='cumulative_stat_snapshot':
            marker=(item.get('match_id'),item.get('team'),item.get('rule'))
            if marker in observed:continue
            observed.add(marker)
        deduped.append(item)
    entries=sorted(deduped,key=lambda e:str(e.get('captured_at') or ''),reverse=True)
    return {'schema':1,'updated_at':newest.get('updated_at'),
            'items':entries[:MAX_ALERTS],'diagnostics':newest.get('diagnostics') or {},
            'notice':'Registros unidos entre jobs. Não equivale a EV+ ou apostas.'}

def merge_remote(backup_path=None):
    """União do Git remoto e da cópia feita antes do rebase da coleta."""
    try:
        result=subprocess.run(['git','show','origin/main:history/signal_registry.json'],
                              cwd=ROOT,capture_output=True,text=True,timeout=15,check=False)
        remote=json.loads(result.stdout) if result.returncode==0 else {}
        if not isinstance(remote,dict):remote={}
    except (OSError,ValueError,subprocess.TimeoutExpired):
        remote={}
    backup=read(backup_path) if backup_path else {}
    local=read(JOURNAL)
    combined=merge_journals(remote,backup,local)
    if combined!=local:
        H.mkdir(exist_ok=True)
        JOURNAL.write_text(json.dumps(combined,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print('NEXUS Cloud: união de alertas',len(combined['items']))

def main():
    today=(datetime.now(timezone.utc)-timedelta(hours=3)).date()
    docs={d:read(H/(d+'.json')) for d in
         ((today-timedelta(days=n)).isoformat() for n in range(4))}
    old=read(JOURNAL)
    new=update(docs,old)
    # Status persistido mesmo com 0 alertas. Heartbeat no maximo a cada 30 min.
    try:
        last_checked=datetime.fromisoformat(str(old.get('updated_at') or '').replace('Z','+00:00'))
        heartbeat_age=(datetime.now(timezone.utc)-last_checked).total_seconds()
    except (ValueError,TypeError):
        heartbeat_age=3600
    changed=(new['items']!=old.get('items',[]) or
             new['diagnostics']!=old.get('diagnostics') or heartbeat_age>=1800)
    if not JOURNAL.exists() or changed:
        H.mkdir(exist_ok=True)
        JOURNAL.write_text(json.dumps(new,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print('NEXUS CLOUD: registros de alertas',len(new['items']),
          '| diagnostico:',json.dumps(new['diagnostics'],ensure_ascii=False),
          '| sem EV inventado')

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--merge-remote':
        merge_remote(sys.argv[2] if len(sys.argv)>2 else None)
    else:
        main()
