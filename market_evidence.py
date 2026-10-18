#!/usr/bin/env python3
"""NEXUS: evidências esportivas por mercado, nunca lucro/simulações retroativas.

Só considera forecasts salvos antes do início, resultado efetivamente verificado
e cotação 1X2 de origem íntegra. Não importa dados pessoais/financeiros.
"""
import math
from collections import defaultdict

MARKETS={
    '1x2':'Match Odds · 1X2',
    'double_chance':'Dupla chance',
    'over_under_25':'Total de gols · 2,5',
    'btts':'Ambas marcam',
}
def finite(v):
    if v is None or isinstance(v,bool):return None
    try:
        val=float(v)
        return val if math.isfinite(val) else None
    except (ValueError,TypeError):return None

def audit_markets(archive):
    records=archive if isinstance(archive,list) else []
    seen=set()
    groups={key:dict(market=key,label=label,forecasts=0,with_price=0,
                     theoretical_positive=0,settled=0,hits=0,misses=0,pending=0)
            for key,label in MARKETS.items()}
    fixtures=priced=finalized=0
    for row in records:
        if not isinstance(row,dict) or not isinstance(row.get('pregame_baseline'),dict):
            continue
        fixture=str(row.get('id') or '')
        if not fixture or fixture in seen:continue
        seen.add(fixture)
        b=row['pregame_baseline']
        if b.get('model_status')!='experimental_uncalibrated':continue
        picks=b.get('indications') or []
        if not isinstance(picks,list):continue
        valid=[p for p in picks if isinstance(p,dict) and p.get('market') in groups
               and str(p.get('selection') or '') and finite(p.get('probability')) is not None
               and 0<=float(p['probability'])<=100]
        if not valid:continue
        fixtures+=1
        odds=b.get('odds') if isinstance(b.get('odds'),dict) else None
        prices=(odds.get('prices') or {}) if odds else {}
        complete=(bool(odds) and odds.get('recent_at_check') is True and
                  all(finite(prices.get(x)) is not None and 1.01<float(prices[x])<1000
                      for x in ('home','draw','away')))
        if complete:priced+=1
        settlement=b.get('settlement') if isinstance(b.get('settlement'),dict) else None
        checks=settlement.get('checks') or [] if settlement else []
        checkmap={(c.get('market'),c.get('selection')):c.get('result')
                  for c in checks if isinstance(c,dict) and c.get('result') in ('hit','miss')}
        is_final=bool(settlement and settlement.get('status')=='finished' and checks)
        if is_final:finalized+=1
        for p in valid:
            key=p['market']
            group=groups[key]
            group['forecasts']+=1
            # No pricing for other markets: only odds 1X2 are archived.
            if key=='1x2' and complete and p['selection'] in ('home','draw','away'):
                group['with_price']+=1
                ev=float(p['probability'])*float(prices[p['selection']])-100
                if ev>0:group['theoretical_positive']+=1
            outcome=checkmap.get((key,p['selection'])) if is_final else None
            if outcome in ('hit','miss'):
                group['settled']+=1
                if outcome=='hit':group['hits']+=1
                else:group['misses']+=1
            else:group['pending']+=1
    markets=[{**g,'observed_hit_pct':round(100*g['hits']/g['settled'],1)
              if g['settled'] else None}
             for g in groups.values()]
    return {'schema':1,'scope':'sports_only_unvalidated',
            'fixtures_with_frozen_forecast':fixtures,
            'fixtures_with_verified_pregame_1x2':priced,
            'fixtures_with_result':finalized,
            'markets':markets,
            'note':'Acertos e erros esportivos de previsões anteriores ao jogo; odds 1X2 sem simular entrada ou stake. EV matemático não validado; sem P/L financeiro.'}
