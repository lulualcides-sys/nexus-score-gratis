"""Leitura consolidada de pré-live: UMA partida, variantes originais preservadas.

Nunca reescreve history, nem altera forecasts gravados antes do apito.
Apenas calcula conferências esportivas de versões capturadas, sem P/L.
"""
import copy
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pregame_audit import resolve

SCORE=re.compile(r'^(\d{1,2})\s*[-–:]\s*(\d{1,2})$')

def identity(name):
    name=unicodedata.normalize('NFKD',str(name or '').split('(')[0].casefold())
    return ''.join(ch for ch in name if ch.isascii() and ch.isalnum())

def consolidate(records):
    """records: fixture, day, pregame_baseline (sanitized or None).

    Um confronto e seu kickoff (tolerância 10 min) são identificados usando
    ambos os times na ordem correta. Jogo com placares finais conflitantes
    permanece SEM CONFERÊNCIA. Todas as versões originais ficam acessíveis.
    """
    groups=[]
    index={}
    for raw in records:
        if not isinstance(raw,dict):continue
        f=raw.get('fixture') or {}
        home=identity(f.get('home'));away=identity(f.get('away'))
        try:kick=int(f.get('start_timestamp') or 0)
        except (ValueError,TypeError):continue
        if not home or not away or not 1600000000<kick<4102444800:continue
        key=(home,away)
        pool=index.setdefault(key,[])
        matched=next((g for g in pool if abs(g['start_timestamp']-kick)<=600),None)
        if matched is None:
            matched={'home':str(f.get('home') or '')[:110],
                     'away':str(f.get('away') or '')[:110],
                     'day':datetime.fromtimestamp(kick,timezone(timedelta(hours=-3))).date().isoformat(),
                     'league':str(f.get('league') or '')[:80],
                     'start_timestamp':kick,'variants':[],
                     'final_scores':set(),'observed_phases':set(),'sources':set()}
            groups.append(matched);pool.append(matched)
        phase=str(f.get('phase') or '')
        matched['observed_phases'].add(phase)
        source=str(f.get('source') or '').strip()[:45]
        if source:matched['sources'].add(source)
        score=str(f.get('score') or '').strip()
        if phase=='finished' and SCORE.fullmatch(score):
            matched['final_scores'].add('-'.join(SCORE.fullmatch(score).groups()))
        baseline=raw.get('pregame_baseline')
        if not isinstance(baseline,dict):continue
        variant_id=str(f.get('id') or '')[:90]
        captured=str(baseline.get('captured_at') or '')
        if any(x['id']==variant_id and
               x['pregame_baseline'].get('captured_at')==captured
               for x in matched['variants']):
            existing=next(x for x in matched['variants'] if
                  x['id']==variant_id and x['pregame_baseline'].get('captured_at')==captured)
            if not existing['pregame_baseline'].get('settlement') and baseline.get('settlement'):
                existing['pregame_baseline']=copy.deepcopy(baseline)
            continue
        matched['variants'].append({
           'id':variant_id,'source':source or 'Fonte não identificada',
           'league':str(f.get('league') or '')[:80],
           'pregame_baseline':copy.deepcopy(baseline)})
    output=[]
    for g in groups:
        variants=g['variants']
        if not variants:continue
        scores=g.pop('final_scores')
        states=g.pop('observed_phases')
        g['sources']=sorted(g['sources'])
        g['variants']=sorted(variants,key=lambda x:(
           str(x['pregame_baseline'].get('captured_at') or ''),x['id']))
        conflict=len(scores)>1
        verified_score=next(iter(scores)) if len(scores)==1 else None
        g['result_conflict']=conflict
        g['phase']='finished' if verified_score else 'live' if 'live' in states else 'scheduled'
        g['score']=verified_score or ''
        # Não apagar nem alterar previsões originais na nuvem: o settlement
        # adicionado aqui existe apenas no JSON público derivado.
        for v in g['variants']:
            base=v['pregame_baseline']
            if conflict:
                base['settlement']=None
                continue
            if not verified_score:continue
            old=base.get('settlement') or {}
            if old.get('score')==verified_score and old.get('checks'):
                continue
            h,a=map(int,verified_score.split('-'))
            checks=[]
            for pick in (base.get('indications') or [])[:4]:
                result=resolve(pick,h,a)
                if result is None:continue
                checks.append({'market':pick['market'],
                               'selection':pick['selection'],
                               'result':'hit' if result else 'miss'})
            if not checks:continue
            base['settlement']={'status':'sports_only_verified_match',
                                'score':verified_score,
                                'checks':checks,
                                'count':len(checks),
                                'hits':sum(c['result']=='hit' for c in checks),
                                'derived_from_verified_final':True}
        g['id']=g['variants'][0]['id']
        g['pregame_baseline']=g['variants'][0]['pregame_baseline']
        # Se a fonte ainda não confirmou FT, não anunciar um palpite como erro.
        g['variant_count']=len(g['variants'])
        sigs={tuple((p.get('market'),p.get('selection'),p.get('probability'))
                  for p in (v['pregame_baseline'].get('indications') or []))
              for v in g['variants']}
        g['forecast_divergence']=len(sigs)>1
        output.append(g)
    return sorted(output,key=lambda g:g['start_timestamp'],reverse=True)[:500]
