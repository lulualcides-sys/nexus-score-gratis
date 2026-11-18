#!/usr/bin/env python3
"""Blocos de horário para fontes de odds com cota grátis.

O GitHub Free executa o cron "a cada 5 minutos" só de 3 em 3 a 9 em 9 horas.
Exigir os 5 primeiros minutos de um horário exato fazia as APIs quase nunca
serem chamadas. Com um registro (ledger) persistido em history/, cada fonte
consulta na primeira execução de cada bloco e nunca duas vezes no mesmo bloco.
"""
import json
import os
from pathlib import Path


def block_slot(instant, block_hours):
    """ID do bloco UTC que contém `instant` (ex.: blocos de 12 h -> T00/T12)."""
    if block_hours not in (1, 2, 3, 4, 6, 8, 12, 24):
        raise ValueError('bloco precisa dividir 24 h')
    start = (instant.hour // block_hours) * block_hours
    return instant.strftime('%Y-%m-%d') + 'T%02d' % start


def load_ledger(path, defaults):
    """Lê o registro de cota; erro de leitura interrompe para não gastar sem controle."""
    path = Path(path)
    data = {}
    if path.exists():
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError('Ledger de cota inválido')
    for key, value in defaults.items():
        data.setdefault(key, value)
    return data


def save_ledger(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        f.write('\n')
    os.replace(tmp, path)
