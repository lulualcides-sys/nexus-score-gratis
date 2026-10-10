#!/usr/bin/env python3
"""Auditoria conservadora de placares FT com dados OpenFootball (CC0).

Nao fornece estatisticas live, odds, xG, gols por minuto, ou estimativas EV.
Nao edita placares do NEXUS: registra apenas verificacao/conflicto por fonte.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from experiments.openfootball_cc0_probe import score_crosscheck

LEAGUES = {
    'eng.1': ('en.1.json', 'Europe/London'),
    'eng.2': ('en.2.json', 'Europe/London'),
    'ger.1': ('de.1.json', 'Europe/Berlin'),
    'esp.1': ('es.1.json', 'Europe/Madrid'),
    'ita.1': ('it.1.json', 'Europe/Rome'),
    'fra.1': ('fr.1.json', 'Europe/Paris'),
}
ROOT = 'https://raw.githubusercontent.com/openfootball/football.json/master'
CACHE_AGE = timedelta(hours=20)
MAX_BYTES = 2_000_000


def dataset_key(fixture):
    """Nunca associa fixture sem inicio verificavel a dataset ou temporada."""
    league = str(fixture.get('league_code') or '')
    if league not in LEAGUES:
        return None
    try:
        stamp = int(fixture.get('start_timestamp'))
        if stamp <= 0:
            return None
        local = datetime.fromtimestamp(stamp, ZoneInfo(LEAGUES[league][1]))
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    year = local.year if local.month >= 7 else local.year - 1
    season = f'{year}-{(year + 1) % 100:02d}'
    return f'{season}/{LEAGUES[league][0]}'


def download_dataset(key):
    if key.count('/') != 1 or '..' in key or key.startswith('/'):
        raise ValueError('dataset invalido')
    req = Request(f'{ROOT}/{key}', headers={'Accept': 'application/json',
                  'User-Agent': 'NEXUS-Score-CC0-verifier/1.0'})
    with urlopen(req, timeout=9) as response:
        content = response.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError('dataset ultrapassa o limite')
    obj = json.loads(content.decode('utf-8'))
    if not isinstance(obj, dict) or not isinstance(obj.get('matches'), list):
        raise ValueError('dataset sem partidas')
    return obj['matches']


def fresh_cache_entry(entry, now):
    if not isinstance(entry, dict) or not isinstance(entry.get('matches'), list):
        return False
    try:
        at = datetime.fromisoformat(entry['fetched_at'])
        return at.tzinfo is not None and timedelta(0) <= now - at <= CACHE_AGE
    except (ValueError, TypeError, KeyError):
        return False


def audit_documents(documents, cache=None, fetcher=download_dataset, now=None):
    """Recebe snapshots dia->doc; nenhum jogo vivo ou agendado e modificado."""
    now = now or datetime.now(timezone.utc)
    cache = cache if isinstance(cache, dict) else {}
    entries = cache.setdefault('entries', {})
    status = {'updated_at': now.isoformat(), 'source': 'OpenFootball CC0',
              'scope': 'finished_scores_only', 'checked': 0, 'cross_verified': 0,
              'conflicts': 0, 'ambiguous': 0, 'unmatched': 0,
              'unavailable': 0, 'datasets_fetched': 0, 'cache_hits': 0,
              'errors': []}
    fixtures = []
    needed = set()
    for day, doc in documents.items():
        rows = (doc or {}).get('matches') or {}
        if not isinstance(rows, dict):
            continue
        for row in rows.values():
            if not isinstance(row, dict):
                continue
            fixture = row.get('fixture') or {}
            if not isinstance(fixture, dict) or fixture.get('phase') != 'finished':
                continue
            key = dataset_key(fixture)
            if key:
                fixtures.append((row, fixture, key))
                needed.add(key)
    datasets = {}
    for key in sorted(needed):
        entry = entries.get(key)
        if fresh_cache_entry(entry, now):
            datasets[key] = entry['matches']
            status['cache_hits'] += 1
            continue
        try:
            rows = fetcher(key)
            if not isinstance(rows, list):
                raise ValueError('dataset sem lista de partidas')
            datasets[key] = rows
            entries[key] = {'fetched_at': now.isoformat(), 'matches': rows}
            status['datasets_fetched'] += 1
        except (OSError, ValueError, TypeError, TimeoutError) as exc:
            if len(status['errors']) < 10:
                status['errors'].append(f'{key}: {str(exc)[:100]}')
    # Nao carregar temporadas antigas indefinidamente no repositorio.
    cache['entries'] = {key: entries[key] for key in needed if key in datasets}
    for row, fixture, key in fixtures:
        status['checked'] += 1
        if key not in datasets:
            status['unavailable'] += 1
            continue
        outcome = score_crosscheck(fixture, datasets[key])
        state = outcome['status']
        counter = {'cross_verified': 'cross_verified', 'conflict': 'conflicts',
                   'ambiguous': 'ambiguous', 'unmatched': 'unmatched'}.get(state)
        if counter:
            status[counter] += 1
        else:
            status['unavailable'] += 1
        if state in ('cross_verified', 'conflict'):
            # So metadados de auditoria, sem mexer em resultado/scouts/odds.
            row.setdefault('score_verifications', {})['openfootball_cc0'] = {
                'status': state, 'source': 'OpenFootball CC0',
                'checked_at': now.isoformat(), 'score': outcome.get('score')}
    return status, cache


def main():
    from coletar import HISTORY, DAY, NOW, read, write
    today = datetime.fromisoformat(DAY).date()
    days = [(today - timedelta(days=i)).isoformat() for i in range(3)]
    docs = {day: read(HISTORY / f'{day}.json') for day in days}
    status, cache = audit_documents(
        docs, cache=read(HISTORY / 'openfootball_cc0_cache.json'), now=NOW)
    for day, doc in docs.items():
        if doc:
            write(HISTORY / f'{day}.json', doc)
    write(HISTORY / 'openfootball_cc0_cache.json', cache)
    write(HISTORY / 'openfootball_cc0_status.json', status)
    print(json.dumps(status, ensure_ascii=False))


if __name__ == '__main__':
    main()
