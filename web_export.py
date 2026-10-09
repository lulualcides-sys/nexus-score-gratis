#!/usr/bin/env python3
"""Snapshot publico do NEXUS: jogos 4 dias, scouts, alertas e resultado paper auditavel.

NUNCA publica operacoes reais da Bolsa, importacao do PC, tokens ou dados privados.
O P/L exibido e somente simulacao retrospectiva de sinais congelados antes do inicio.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import math
import re

ROOT=Path(__file__).resolve().parent
H=ROOT/'history'
OUT=ROOT/'web'/'data.json'
BR=timezone(timedelta(hours=-3))
SCOUTS=('shots_on','shots_off','shots_total','corners','big_chances','dangerous_attacks',
        'possession','fouls','yellow_cards','red_cards','offsides','saves','passes',
        'pass_accuracy','xg')
TYPES={'goal','yellow_card','red_card','penalty_missed','shot_on','shot_off'}

def load(path):
    try:
        doc=json.loads(path.read_text(encoding='utf-8'))
        return doc if isinstance(doc,dict) else {}
    except (OSError,ValueError):
        return {}

def safe(value,maxlen=110):
    return str(value if value is not None else '').strip()[:maxlen]

def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) and abs(n)<100000 else None
    except (TypeError,ValueError,OverflowError):
        return None

def score_outcomes(score,phase):
    if phase!='finished':return {}
    m=re.fullmatch(r'(\d{1,2})-(\d{1,2})',score)
    if not m:return {}
    home,away=map(int,m.groups())
    total=home+away
    return {'over_15':total>1,'over_25':total>2,'over_35':total>3,
            'btts':home>0 and away>0,'result':'home' if home>away else 'away' if away>home else 'draw',
            'correct_score':score}

def pregame_signal(item,fixture):
    if not isinstance(item,dict) or item.get('market')!='1x2':return None
    start=number(fixture.get('start_timestamp'))
    odds=number(item.get('odds'))
    prob=number(item.get('probability'))
    ev=number(item.get('ev_pct'))
    sample=number(item.get('sample_size'))
    side=safe(item.get('selection'),10)
    if side not in ('home','away','draw') or not start or not odds or odds<=1.01 or odds>=1000:return None
    if prob is None or not 0<=prob<=100 or ev is None or sample is None or sample<8:return None
    try:
        captured=datetime.fromisoformat(str(item.get('captured_at') or '').replace('Z','+00:00'))
        if not captured.tzinfo or captured.timestamp()>=start:return None
    except (TypeError,ValueError):return None
    settled=item.get('status')=='settled' and isinstance(item.get('won'),bool)
    result=round((odds-1) if item['won'] else -1,4) if settled else None
    return {'market':'1x2','selection':side,'odds':round(odds,4),
            'probability':round(prob,2),'ev_pct':round(ev,2),'sample_size':int(sample),
            'model':safe(item.get('model'),70),'captured_at':safe(item.get('captured_at'),40),
            'status':'settled' if settled else 'pending','paper_pl_u':result}

def public_row(row,day):
    if not isinstance(row,dict):return None
    f=row.get('fixture') or {}
    if not isinstance(f,dict) or not f.get('home') or not f.get('away'):return None
    points=[]
    for point in ((row.get('thermometer') or {}).get('points') or []):
        if not isinstance(point,dict):continue
        try:
            m=int(point.get('minute'));v=number(point.get('value'))
        except (TypeError,ValueError):continue
        if v is not None and 1<=m<=150:points.append({'m':m,'v':round(v,2)})
    points=sorted({p['m']:p for p in points}.values(),key=lambda p:p['m'])[-150:]
    stats={}
    for side in ('home','away'):
        orig=(row.get('stats') or {}).get(side) or {}
        stats[side]={}
        if not isinstance(orig,dict):continue
        for key in SCOUTS:
            n=number(orig.get(key))
            if n is not None:stats[side][key]=n
    odds=[]
    for item in row.get('odds_quotes') or []:
        if not isinstance(item,dict):continue
        val=number(item.get('odds'))
        if val is None or not 1.01<=val<=1000:continue
        if item.get('market')=='1x2' and item.get('selection') in ('home','draw','away'):
            odds.append({'sel':item['selection'],'odd':round(val,3),
                         'source':safe(item.get('source'),24),
                         'bookmaker':safe(item.get('bookmaker'),35),
                         'at':safe(item.get('captured_at'),36)})
    events=[]
    for event in row.get('events') or []:
        if not isinstance(event,dict) or event.get('type') not in TYPES:continue
        try:minute=int(event.get('minute'))
        except (ValueError,TypeError):continue
        if not 0<=minute<=130:continue
        events.append({'m':minute,'type':event['type'],
                       'side':event.get('side') if event.get('side') in ('home','away') else '',
                       'text':safe(event.get('text'),125)})
    signals=[]
    for item in row.get('paper_signals') or []:
        q=pregame_signal(item,f)
        if q:signals.append(q)
    return {'day':day,'id':safe(f.get('id'),90),
            'home':safe(f.get('home')),'away':safe(f.get('away')),
            'league':safe(f.get('league'),85),'league_code':safe(f.get('league_code'),40),
            'round':safe(f.get('round'),70),'venue':safe(f.get('venue'),100),
            'start_timestamp':f.get('start_timestamp'),'minute':f.get('minute') or 0,
            'score':safe(f.get('score'),12),'phase':safe(f.get('phase'),12),
            'source':safe(f.get('source'),30),'observed_at':safe(f.get('collected_at'),36),
            'pressure':points,'stats':stats,'odds':odds[:5],
            'events':events[:130],'signals':signals[:20],
            'outcomes':score_outcomes(safe(f.get('score'),12),f.get('phase'))}

def paper_summary(rows):
    signals=[s for r in rows for s in r['signals']]
    settled=[s for s in signals if s['status']=='settled' and s['paper_pl_u'] is not None]
    wins=sum(1 for s in settled if s['paper_pl_u']>0)
    groups={}
    for s in settled:
        group=groups.setdefault(s['market'],{'market':s['market'],'entries':0,'wins':0,'paper_pl_u':0.0})
        group['entries']+=1
        group['wins']+=s['paper_pl_u']>0
        group['paper_pl_u']+=s['paper_pl_u']
    for v in groups.values():v['paper_pl_u']=round(v['paper_pl_u'],3)
    return {'unit':'1u nominal por entrada BACK 1X2 (teste sem taxas)',
            'status':'with_settlements' if settled else 'insufficient_data',
            'settled':len(settled),'pending':len(signals)-len(settled),
            'won':wins,'paper_pl_u':round(sum(s['paper_pl_u'] for s in settled),3) if settled else None,
            'markets':list(groups.values())}

def alerts_from(rows):
    alerts=[]
    for g in rows:
        if len(alerts)>=35:break
        if g['phase']=='finished':continue
        for s in g['signals']:
            if s['status']=='pending' and s['ev_pct']>5:
                alerts.append({'kind':'ev_experimental','match_id':g['id'],'day':g['day'],
                               'title':'EV experimental '+s['selection'].upper()+' · '+safe(g['home'])+' × '+safe(g['away']),
                               'detail':'EV '+str(s['ev_pct'])+'% · odd '+str(s['odds'])+
                                        ' · modelo '+safe(s['model'])+' (nao validado)',
                               'observed_at':s['captured_at']})
        if g['phase']=='live':
            on=[number((g['stats'].get(side) or {}).get('shots_on')) for side in ('home','away')]
            corners=[number((g['stats'].get(side) or {}).get('corners')) for side in ('home','away')]
            if all(x is not None for x in on) and sum(on)>=7:
                alerts.append({'kind':'stat_watch','match_id':g['id'],'day':g['day'],
                               'title':'Finalizacoes no alvo · '+g['home']+' × '+g['away'],
                               'detail':str(int(sum(on)))+' chutes no alvo registrados. Somente monitoramento; EV nao calculado.',
                               'observed_at':g['observed_at']})
            if all(x is not None for x in corners) and sum(corners)>=9:
                alerts.append({'kind':'stat_watch','match_id':g['id'],'day':g['day'],
                               'title':'Escanteios · '+g['home']+' × '+g['away'],
                               'detail':str(int(sum(corners)))+' escanteios registrados. Somente monitoramento; EV nao calculado.',
                               'observed_at':g['observed_at']})
    return alerts[:35]

def main():
    today=datetime.now(BR).date()
    days={(today-timedelta(days=i)).isoformat() for i in range(4)}
    rows=[]
    for path in sorted(H.glob('20??-??-??.json'),reverse=True):
        if path.stem not in days:continue
        doc=load(path)
        matches=doc.get('matches') or {}
        if not isinstance(matches,dict):continue
        for row in matches.values():
            item=public_row(row,path.stem)
            if item:rows.append(item)
    rows.sort(key=lambda r:(0 if r['phase']=='live' else 1 if r['phase']=='scheduled' else 2,
                            -int(r['day'].replace('-','')),r['league'],r['home']))
    # Conservar partidas de todos os dias; sem truncamento prematuro que exclua o historico.
    rows=rows[:500]
    last=load(H/'status.json')
    backfill=load(H/'backfill_status.json')
    status={key:last.get(key) for key in ('day','updated_at','sources','live_found','thermometers_saved') if key in last}
    payload={'app':'NEXUS SCORE WEB','schema':2,'exported_at':datetime.now(timezone.utc).isoformat(),
             'collector':status,'backfill':{k:backfill.get(k) for k in ('days','games','with_stats','events','checked_at')},
             'notice':'Atualizacao periodica, sem odds em tempo real. EV experimental nao e recomendacao nem lucro realizado.',
             'paper':paper_summary(rows),'alerts':alerts_from(rows),'games':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUT.with_suffix('.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    temp.replace(OUT)
    print('WEB EXPORT:',len(rows),'jogos,',len(payload['alerts']),'alertas de monitoramento,',
          payload['paper']['settled'],'operacoes paper; ZERO dados financeiros privados')
if __name__=='__main__':main()
