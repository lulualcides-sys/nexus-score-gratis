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
    for path, item in candidates:
        if item is None:
            continue
        had_container = True
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
            if not math.isfinite(v) or str(minute).strip() != str(m):
                continue
            if 1 <= m <= 150 and -1000 <= v <= 1000:
                found[m] = {'minute': m, 'value': v}
        if found:
            return {'points': [found[m] for m in sorted(found)],
                    'state': 'observed', 'source_path': path}
    return {'points': [], 'state': ('missing' if not had_container else
            'no_valid_points' if had_list else 'unsupported_shape'),
            'source_path': None}
