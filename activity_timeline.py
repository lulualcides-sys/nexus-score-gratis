"""Linha do tempo factual de acoes ofensivas: contagens, nunca momentum.

Entrada: eventos individuais observados, com minuto e equipe certificados.
Saida: apenas minutos com evento. Sem zeros para minutos sem cobertura e sem
converter totais acumulados de scouts em lances de minuto ficticio.
"""
from collections import defaultdict
import math

ALLOWED = frozenset(('goal','shot_on','shot_off','big_chance_missed','penalty_missed'))


def observed_activity(events):
    rows = defaultdict(lambda: {'home':0,'away':0,'types':defaultdict(int)})
    seen = set()
    for event in events or []:
        if not isinstance(event,dict):
            continue
        kind = event.get('type')
        side = event.get('side')
        if kind not in ALLOWED or side not in ('home','away'):
            continue
        if event.get('basis') not in (None,'event','confirmed_event'):
            continue
        minute = event.get('minute')
        if isinstance(minute,bool):
            continue
        try:
            m = int(minute)
            if not math.isfinite(float(minute)) or float(minute) != m:
                continue
        except (ValueError,TypeError,OverflowError):
            continue
        if not 0 <= m <= 130:
            continue
        ident=(m,kind,side,str(event.get('text') or '')[:125])
        if ident in seen:continue
        seen.add(ident)
        rows[m][side]+=1
        rows[m]['types'][kind]+=1
    points=[{'m':m,'home':v['home'],'away':v['away'],
             'types':dict(sorted(v['types'].items()))}
            for m,v in sorted(rows.items())]
    return {'basis':'confirmed_event_count',
            'total_events':sum(row['home']+row['away'] for row in points),
            'observed_minutes':len(points),'points':points}
