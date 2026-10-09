#!/usr/bin/env python3
"""Experimento isolado: audita ate 10 jogos versus Football-Data e OpenLigaDB.

NUNCA modifica history/, web/data.json, odds, sinais ou o NEXUS em producao.
Odd historica nao e odd de entrada. Sem partida/placar compativeis => sem verificacao.
Uso: python experiments/multisource_trial.py --online --limit 10 --output artifacts/multisource-trial.json
"""
import argparse
import json
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from multi_source import (LEAGUES, STAT_COLUMNS, football_data_csv,
                          openliga_events, openliga_fixture, norm, row_date)
from coletar import read

BR=timezone(timedelta(hours=-3))
CODES={v[0]:k for k,v in LEAGUES.items()}


def choose_fixtures(rows,limit=10,seed=20261009):
    """Amostra aleatoria reproduzivel, somente ligas que possuem fonte extra."""
    distinct={}
    for row in rows:
        if not isinstance(row,dict):continue
        fixture=row.get('fixture') or {}
        if not isinstance(fixture,dict):continue
        fid=str(fixture.get('id') or '')
        league=fixture.get('league_code') or fixture.get('league')
        if not fid or not fixture.get('home') or not fixture.get('away'):continue
        if league not in CODES and league!='ger.1':continue
        distinct.setdefault(fid,row)
    data=list(distinct.values())
    return random.Random(seed).sample(data,min(limit,len(data)))


def _score(value):
    m=re.fullmatch(r'(\d{1,2})-(\d{1,2})',str(value or '').strip())
    return (int(m[1]),int(m[2])) if m else None


def compare_football_data(fixture,raw_rows):
    """Confirmar casa, fora, dia (quando conhecido) e placar final idêntico."""
    stamp=fixture.get('start_timestamp')
    league=fixture.get('league_code') or fixture.get('league')
    code=CODES.get(league)
    expected_day=None
    if stamp and code:
        try: expected_day=datetime.fromtimestamp(int(stamp),ZoneInfo(LEAGUES[code][1])).date()
        except (ValueError,TypeError,OverflowError):pass
    for raw in raw_rows:
        if norm(raw.get('HomeTeam'))!=norm(fixture.get('home')):continue
        if norm(raw.get('AwayTeam'))!=norm(fixture.get('away')):continue
        if expected_day and row_date(raw.get('Date'))!=expected_day:continue
        actual=(raw.get('FTHG'),raw.get('FTAG'))
        try:
            actual=tuple(int(x) for x in actual)
        except (ValueError,TypeError):return {'status':'unavailable','stats_available':0}
        current=_score(fixture.get('score')) if fixture.get('phase')=='finished' else None
        if current is None:
            return {'status':'unsettled','stats_available':0}
        if actual!=current:return {'status':'conflict','stats_available':0}
        stats=sum(1 for key in STAT_COLUMNS if _valid_stat(raw.get(key)))
        return {'status':'cross_verified','stats_available':stats}
    return {'status':'unmatched','stats_available':0}


def _valid_stat(v):
    try:return v is not None and v!='' and 0<=float(v)<=10000
    except (ValueError,TypeError):return False


def compare_openliga(fixture,events):
    try:stamp=int(fixture.get('start_timestamp') or 0)
    except (ValueError,TypeError):stamp=0
    for event in events:
        ext=openliga_fixture(event)
        if not ext:continue
        if norm(ext['home'])!=norm(fixture.get('home')) or norm(ext['away'])!=norm(fixture.get('away')):continue
        if stamp and abs(stamp-ext['start_timestamp'])>3*3600:continue
        original=_score(fixture.get('score')) if fixture.get('phase')=='finished' else None
        external=_score(ext.get('score')) if ext.get('phase')=='finished' else None
        if original is None or external is None:return {'status':'unsettled','stats_available':0}
        return {'status':'cross_verified' if original==external else 'conflict','stats_available':0}
    return {'status':'unmatched','stats_available':0}


def sample_history(history,days=3):
    today=datetime.now(BR).date()
    rows=[]
    for index in range(days):
        day=(today-timedelta(days=index)).isoformat()
        doc=read(history/(day+'.json'))
        for item in (doc.get('matches') or {}).values():
            if isinstance(item,dict):rows.append(item)
    return rows


def audit(rows,online=False,limit=10,seed=20261009):
    chosen=choose_fixtures(rows,limit,seed)
    codes=sorted({CODES.get((r['fixture'].get('league_code') or r['fixture'].get('league')))
                  for r in chosen if CODES.get(r['fixture'].get('league_code') or r['fixture'].get('league'))})
    results={}
    errors={}
    if online:
        for code in codes:
            try:results[code]=football_data_csv(code)
            except Exception as ex:errors['Football-Data '+code]=str(ex)[:160]
        if any((r['fixture'].get('league_code') or r['fixture'].get('league'))=='ger.1' for r in chosen):
            year=datetime.now(BR).year
            try:results['openliga']=openliga_events(year if datetime.now(BR).month>=7 else year-1)
            except Exception as ex:errors['OpenLigaDB']=str(ex)[:160]
    entries=[]
    for row in chosen:
        f=row['fixture']
        league=f.get('league_code') or f.get('league')
        code=CODES.get(league)
        sources=list(row.get('sources') or [f.get('source')])
        baseline={'providers_recorded':len({s for s in sources if s}),
                  'stats_recorded':sum(len(s) for s in (row.get('stats') or {}).values() if isinstance(s,dict))}
        checks={}
        if online:
            if code:
                checks['Football-Data.co.uk']=(compare_football_data(f,results[code]) if code in results
                                               else {'status':'unavailable','stats_available':0})
            if league=='ger.1':
                checks['OpenLigaDB']=(compare_openliga(f,results['openliga']) if 'openliga' in results
                                       else {'status':'unavailable','stats_available':0})
        entries.append({'match_id':str(f.get('id'))[:95],'home':str(f.get('home'))[:95],
                        'away':str(f.get('away'))[:95],'league':str(league),
                        'phase':str(f.get('phase')),'baseline':baseline,
                        'verification':checks})
    all_checks=[s for e in entries for s in e['verification'].values()]
    return {'mode':'online' if online else 'offline',
            'sample_requested':limit,'sample_count':len(entries),
            'seed':seed,'sources_requested':codes+(['OpenLigaDB'] if 'D1' in codes else []),
            'providers_errors':errors,
            'verified':sum(x['status']=='cross_verified' for x in all_checks),
            'conflicts':sum(x['status']=='conflict' for x in all_checks),
            'unmatched':sum(x['status']=='unmatched' for x in all_checks),
            'unavailable':sum(x['status']=='unavailable' for x in all_checks),
            'avg_baseline_stats':round(sum(e['baseline']['stats_recorded'] for e in entries)/len(entries),2) if entries else None,
            'matches':entries,
            'note':'Teste isolado, sem modificar dados. Fontes sem correspondencia nao melhoraram a cobertura. Odds historicas nao sao odds de entrada.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--online',action='store_true',help='Consulta CSV e OpenLigaDB (sem alterar coletas)')
    parser.add_argument('--limit',type=int,default=10)
    parser.add_argument('--seed',type=int,default=20261009)
    parser.add_argument('--output',type=str,default=None)
    args=parser.parse_args()
    if not 1<=args.limit<=50:parser.error('limit deve estar entre 1 e 50')
    result=audit(sample_history(ROOT/'history'),online=args.online,limit=args.limit,seed=args.seed)
    rendered=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        dest=Path(args.output).resolve()
        if dest==ROOT/'web'/'data.json' or dest.is_relative_to(ROOT/'history'):
            parser.error('proibido escrever em history/ ou web/data.json')
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(rendered,encoding='utf-8')
    print(rendered)
    return 0


if __name__=='__main__':sys.exit(main())
