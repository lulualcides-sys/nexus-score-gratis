"""Port das regras de leitura do NEXUS SCORE Original 5.29 para a nuvem.

Base: NEXUS_SCORE_5_29_COMPLETO_GITHUB_AUDITORIA.zip, nexus_score/engine.py
e nexus_score/free_match_data.py. Reproduz limiares e estados do indicator_board;
nao transforma indicador heuristico em odds, EV+ ou probabilidades de gol.
O app desktop e o servidor local nao sao iniciados nos runners do GitHub.
"""
from __future__ import annotations
from math import ceil, isfinite

KEYS=('🧨','🔥','🎯','🚩','⚡','💣','⚔️','🧠','🟥','⏱️','🥶','🚨')
SCOUT_FIELDS={'🎯':('shots_on',5),'🚩':('corners',6),
              '💣':('big_chances',3),'⚔️':('dangerous_attacks',25)}
GRAPH_KEYS={'🧨','🔥','⚡','⏱️','🥶','🚨'}

def num(value):
    try:
        if value is None or isinstance(value,bool):return None
        x=float(value)
        return x if isfinite(x) else None
    except (TypeError,ValueError,OverflowError):return None

def thermometer(points, minute, length):
    clean={}
    for p in points or []:
        if not isinstance(p,dict):continue
        m=num(p.get('minute'));v=num(p.get('value'))
        if m is None or v is None:continue
        if m.is_integer() and 1<=m<=150 and abs(v)<=1000:clean[int(m)]=v
    end=int(minute)
    values=[v for m,v in clean.items() if max(0,end-length+1)<=m<=end]
    expected=min(length,max(1,end))
    if len(values)<ceil(expected*.8):
        return {'score':None,'level':'SEM DADOS','dominant':'SEM DADOS',
                'difference':None,'samples':len(values),'expected':expected,
                'home_recent':None,'away_recent':None}
    h=sum(max(0.0,v) for v in values)/len(values)
    a=sum(max(0.0,-v) for v in values)/len(values)
    intensity=max(h,a);diff=abs(h-a)
    level=('CRITICO' if intensity>=62 and diff>=18 else
           'FORTE' if intensity>=43 and diff>=12 else
           'OBSERVAR' if intensity>=25 else 'FRIO')
    dominant='HOME' if h>a+2 else 'AWAY' if a>h+2 else 'EQUILIBRADO'
    # Original: round intens, difference and home/away to one decimal
    # before pressure_info converts intensity into visual 0-100 score.
    score=round(min(100,max(0,round(intensity,1)/80*100)))
    return {'score':score,'level':level,'dominant':dominant,
            'difference':round(diff,1),'home_recent':round(h,1),
            'away_recent':round(a,1),'samples':len(values),'expected':expected}

def board(points, minute, stats=None, incidents=None):
    """Mesmos 12 estados e equipes do signal_board original 5.29."""
    stats=stats or {};incidents=incidents or []
    p10=thermometer(points,minute,10)
    p5=thermometer(points,minute,5)
    valid=p10['score'] is not None
    high=p10['level'] in ('FORTE','CRITICO')
    side=p10['dominant'] if p10['dominant'] in ('HOME','AWAY') else None
    result=[]
    def add(icon,state,team=None,reason=''):
        result.append({'emoji':icon,'state':state,'team':team,'reason':reason})
    def yesno(ok,available):
        return ('active' if ok else 'inactive') if available else 'unavailable'
    add('🧨',yesno(high and p5['score'] is not None and p5['score']>=65,
                    valid and p5['score'] is not None),side,
        'Pressao 10 min forte e 5 min >= 65')
    add('🔥',yesno(high,valid),side,'Pressao 10 min '+p10['level'])
    def stat(icon,key,limit):
        choices=[]
        for part in ('home','away'):
            v=num((stats.get(part) or {}).get(key))
            if v is not None:choices.append((v,part))
        if choices:
            v,team=max(choices)
            add(icon,yesno(v>=limit,True),team.upper(),
                str(v)+' '+key+' acumulados; limite '+str(limit))
        else:add(icon,'unavailable')
    stat('🎯','shots_on',5)
    stat('🚩','corners',6)
    add('⚡',yesno(p10['level'] in ('OBSERVAR','FORTE','CRITICO') and
                  (p10['difference'] or 0)>=18,valid and p10['difference'] is not None),
        side,'Diferenca da intensidade >=18')
    stat('💣','big_chances',3)
    stat('⚔️','dangerous_attacks',25)
    add('🧠','unavailable',reason='Exige odd verificada e probabilidade calibrada')
    reds=[num((stats.get(part) or {}).get('red_cards')) for part in ('home','away')]
    present=[v for v in reds if v is not None]
    direct=any(e.get('emoji')=='🟥' for e in incidents if isinstance(e,dict))
    red_active=direct or any(v>=1 for v in present)
    add('🟥',yesno(red_active,bool(present) or bool(incidents)),
        next((part.upper() for part in ('home','away')
              if (num((stats.get(part) or {}).get('red_cards')) or 0)>=1),None),
        'Expulsao verificada' if red_active else 'Sem expulsao reportada')
    add('⏱️',yesno(int(minute)>=70 and high,valid and int(minute)>0),side)
    add('🥶',yesno(p10['level']=='FRIO',valid),side)
    own=(stats.get((side or '').lower()) or {})
    sot=num(own.get('shots_on'));big=num(own.get('big_chances'))
    available=valid and p5['score'] is not None and side is not None and sot is not None and big is not None
    hit=available and high and p10['score']>=70 and p5['score']>=65 and sot>=3 and big>=1
    add('🚨',yesno(hit,available),side,
        'Alerta heuristico; nao e probabilidade calibrada de gol')
    return {'board':result,'pressure10':p10,'pressure5':p5,
            'active':[x for x in result if x['state']=='active'],
            'source_engine':'NEXUS Original 5.29 | engine.py / free_match_data.py'}
