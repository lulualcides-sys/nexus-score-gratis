#!/usr/bin/env python3
"""Decodificacao conservadora de momentum realmente reportado pela fonte.

Nunca infere pressao a partir de posse, gols, chutes ou totais acumulados.
Distingue ausente, formato desconhecido e serie presente mas invalida.
"""
import math


def momentum_diagnostic(packet):
    if not isinstance(packet, dict):
        return {'points': [], 'state': 'invalid_payload', 'source_path': None}
    content = packet.get('content')
    if not isinstance(content, dict):
        return {'points': [], 'state': 'missing', 'source_path': None}
    facts = content.get('matchFacts')
    candidates = (
        ('content.matchFacts.momentum', facts.get('momentum') if isinstance(facts, dict) else None),
        ('content.momentum', content.get('momentum')),
    )
    had_container = False
    had_list = False
    not_provided = False
    for path, item in candidates:
        if item is None:
            continue
        had_container = True
        if item is False:
            not_provided = True
            continue
        if isinstance(item, list):
            data = item
        elif isinstance(item, dict):
            main = item.get('main')
            if isinstance(main, dict):
                data = main.get('data')
            elif isinstance(main, list):
                data = main
            else:
                data = None
            if not isinstance(data, list):
                data = item.get('data')
        else:
            continue
        if not isinstance(data, list):
            continue
        had_list = True
        found = {}
        for entry in data:
            if not isinstance(entry, dict):
                continue
            minute = entry.get('minute')
            value = entry.get('value')
            if isinstance(minute, bool) or isinstance(value, bool):
                continue
            try:
                m = int(minute)
                v = float(value)
            except (ValueError, TypeError, OverflowError):
                continue
            if not math.isfinite(v):
                continue
            if isinstance(minute, (int, float)):
                if not math.isfinite(float(minute)) or float(minute) != m:
                    continue
            elif isinstance(minute, str):
                if minute.strip() != str(m):
                    continue
            else:
                continue
            if 1 <= m <= 150 and -1000 <= v <= 1000:
                found[m] = {'minute': m, 'value': v}
        if found:
            return {'points': [found[m] for m in sorted(found)],
                    'state': 'observed', 'source_path': path}
    return {'points': [], 'state': ('missing' if not had_container else
            'no_valid_points' if had_list else
            'not_provided' if not_provided else 'unsupported_shape'),
            'source_path': None}

def momentum_shape(packet):
    """Assinatura de estrutura sem copiar dados, times ou valores do jogo."""
    content=(packet or {}).get('content') or {}
    if not isinstance(content,dict):
        return 'content:not-object'
    facts=content.get('matchFacts') or {}
    candidates=[('facts',(facts or {}).get('momentum') if isinstance(facts,dict) else None),
                ('content',content.get('momentum'))]
    signatures=[]
    def describe(item,depth=0):
        if isinstance(item,dict):
            keys=sorted(str(k)[:24] for k in item)[:8]
            keytext=','.join(keys)
            if depth>=2:return 'dict['+keytext+']'
            deeper=[]
            for k in ('main','data','home','away','values','periods'):
                if k in item:
                    deeper.append(k+':'+describe(item[k],depth+1))
            return 'dict['+keytext+']'+('('+','.join(deeper)+')' if deeper else '')
        if isinstance(item,list):return 'list'
        if item is None:return 'null'
        if isinstance(item,bool):return 'bool'
        return type(item).__name__
    for name,item in candidates:
        if item is not None:signatures.append(name+':'+describe(item))
    return '|'.join(signatures)[:280] if signatures else 'absent'
