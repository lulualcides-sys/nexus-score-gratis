#!/usr/bin/env python3
"""Exporta APENAS dados esportivos públicos para Cloudflare Pages.

Nunca publica netPl da Bolsa, IDs privados, regras dos bots ou sinais paper.
O site é público. O repositório de origem continua privado.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json, math, re
ROOT=Path(__file__).resolve().parent
H=ROOT/'history'
OUT=ROOT/'web'/'data.json'
BR=timezone(timedelta(hours=-3))

def load(path):
    try:
        doc=json.loads(path.read_text(encoding='utf-8'))
        return doc if isinstance(doc,dict) else {}
    except (OSError,ValueError):
        return {}

def safe(value,maxlen=110):
    return str(value or '').strip()[:maxlen]

def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) and abs(n)<100000 else None
    except (TypeError,ValueError,OverflowError):
        return None

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
        original=(row.get('stats') or {}).get(side) or {}
        stats[side]={}
        for key in ('shots_on','shots_off','corners','big_chances','dangerous_attacks'):
            n=number(original.get(key))
            if n is not None:stats[side][key]=n
    odds=[]
    for item in row.get('odds_quotes') or []:
        if not isinstance(item,dict):continue
        val=number(item.get('odds'))
        if val is None or not 1.01<=val<=1000:continue
        if item.get('market')=='1x2' and item.get('selection') in ('home','draw','away'):
            odds.append({'sel':item['selection'],'odd':round(val,3),'source':safe(item.get('source'),24),'at':safe(item.get('captured_at'),36)})
    return {'day':day,'id':safe(f.get('id'),90),
            'home':safe(f.get('home')),'away':safe(f.get('away')),
            'league':safe(f.get('league'),85),'minute':f.get('minute') or 0,
            'score':safe(f.get('score'),12),'phase':safe(f.get('phase'),12),
            'source':safe(f.get('source'),30),'observed_at':safe(f.get('collected_at'),36),
            'pressure':points,'stats':stats,'odds':odds[:3]}

def main():
    rows=[]
    for path in sorted(H.glob('20??-??-??.json'),reverse=True)[:4]:
        doc=load(path)
        matches=doc.get('matches') or {}
        if not isinstance(matches,dict):continue
        for row in matches.values():
            item=public_row(row,path.stem)
            if item:rows.append(item)
    rows.sort(key=lambda r:(0 if r['phase']=='live' else 1 if r['phase']=='scheduled' else 2,
                            -len(r['pressure']),r['league'],r['home']))
    rows=rows[:180]
    last=load(H/'status.json')
    status={key:last.get(key) for key in ('day','updated_at','sources','errors','live_found','thermometers_saved') if key in last}
    # Erros podem conter URLs internas: só exibir número, não o conteúdo.
    status.pop('errors',None)
    payload={'app':'NEXUS SCORE WEB','schema':1,'exported_at':datetime.now(timezone.utc).isoformat(),
             'collector':status,
             'notice':'Dados públicos atrasados. Não são odds em tempo real nem recomendações de aposta.',
             'games':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUT.with_suffix('.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    temp.replace(OUT)
    print('WEB EXPORT:',len(rows),'jogos, sem dados financeiros')
if __name__=='__main__':main()
