#!/usr/bin/env python3
"""Historico cronologico dos scouts OBSERVADOS ao vivo.

Valores representam totais acumulados NA CAPTURA. Nunca presumir que um
chute, canto ou chance ocorreu exatamente no minuto de observacao.
"""
from datetime import datetime
import math

FIELDS = ('shots_on','shots_off','shots_total','corners','big_chances',
          'dangerous_attacks','xg','possession')
COUNTS = set(FIELDS) - {'xg','possession'}


def clean_observed(raw):
    answer = {'home': {}, 'away': {}}
    for side in answer:
        team = (raw or {}).get(side) or {}
        if not isinstance(team, dict):
            continue
        for field in FIELDS:
            value = team.get(field)
            if value is None or isinstance(value,bool):
                continue
            try:
                number = float(value)
            except (TypeError,ValueError):
                continue
            if not math.isfinite(number) or not 0 <= number <= (100 if field=='possession' else 50 if field=='xg' else 10000):
                continue
            if field in COUNTS and not number.is_integer():
                continue
            answer[side][field] = round(number, 3) if field=='xg' else int(number) if field in COUNTS else round(number, 2)
    return answer


def append_snapshot(prior, raw_stats, minute, observed_at, source='FotMob'):
    """Adiciona observacao factual; deduplica minuto; conserva ate 72 capturas."""
    previous = [dict(x) for x in (prior or []) if isinstance(x,dict)]
    try:
        numeric = int(minute)
        instant = datetime.fromisoformat(str(observed_at).replace('Z','+00:00'))
    except (TypeError,ValueError):
        return previous[-72:]
    if numeric < 1 or numeric > 130 or instant.tzinfo is None or str(minute).strip()!=str(numeric):
        return previous[-72:]
    values = clean_observed(raw_stats)
    if not values['home'] and not values['away']:
        return previous[-72:]
    item = {'at': instant.isoformat(), 'minute':numeric,'source':str(source)[:40],
            'stats':values}
    by_minute = {int(x['minute']):x for x in previous
                 if isinstance(x.get('minute'),int) and 1<=x['minute']<=130 and
                 isinstance(x.get('at'),str)}
    current = by_minute.get(numeric)
    if current is None or item['at'] >= current['at']:
        by_minute[numeric] = item
    return sorted(by_minute.values(),key=lambda x:(x['at'],x['minute']))[-72:]


def public_snapshots(history):
    """Exporta somente capturas marcadas com hora, minuto e fonte."""
    out = []
    for item in history or []:
        if not isinstance(item,dict):
            continue
        try:
            m=int(item['minute'])
            dt=datetime.fromisoformat(str(item['at']).replace('Z','+00:00'))
        except (ValueError,TypeError,KeyError):
            continue
        if dt.tzinfo is None or not 1<=m<=130:
            continue
        observed=clean_observed(item.get('stats'))
        if not observed['home'] and not observed['away']:
            continue
        out.append({'m':m,'at':dt.isoformat(),
                    'source':str(item.get('source') or 'Fonte publica')[:40],
                    'stats':observed})
    return sorted(out,key=lambda x:(x['at'],x['m']))[-72:]

def snapshot_deltas(history, max_gap_minutes=40):
    """Diferencas ENTRE capturas observadas, sem atribuir minuto dos lances."""
    snapshots=public_snapshots(history)
    if len(snapshots)<2:return {'status':'insufficient','reason':'Menos de duas coletas reais'}
    a,b=snapshots[-2:]
    try:
        start=datetime.fromisoformat(a['at']);end=datetime.fromisoformat(b['at'])
    except (ValueError,TypeError):
        return {'status':'insufficient','reason':'Horario da coleta invalido'}
    elapsed=(end-start).total_seconds()/60
    if not 0<elapsed<=max_gap_minutes:
        return {'status':'insufficient','reason':'Coletas distantes ou desordenadas'}
    if a.get('source')!=b.get('source'):
        return {'status':'insufficient','reason':'Fontes diferentes; evitar misturar scouts'}
    fields=('shots_on','shots_total','corners','big_chances','dangerous_attacks','xg')
    observed={'home':{},'away':{}}
    for side in observed:
        for field in fields:
            old=a.get('stats',{}).get(side,{}).get(field)
            new=b.get('stats',{}).get(side,{}).get(field)
            if old is None or new is None or new<old:continue
            delta=round(new-old,3)
            if field!='xg':delta=int(delta)
            observed[side][field]=delta
    if not any(observed.values()):
        return {'status':'insufficient','reason':'Nao ha contadores comparaveis'}
    return {'status':'observed_delta','source':b['source'],'from_at':a['at'],
            'to_at':b['at'],'elapsed_minutes':round(elapsed,1),
            'from_minute':a['m'],'to_minute':b['m'],
            'changes':observed,
            'note':'Variacao de totais entre capturas reais; minuto de cada lance desconhecido'}

