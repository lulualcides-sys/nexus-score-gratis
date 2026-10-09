#!/usr/bin/env python3
"""Gera painel legível de dados coletados. Não calcula EV nem lucro."""
import json
from pathlib import Path
from datetime import datetime,timezone
import html

H=Path(__file__).resolve().parent/'history'

def safe(text):
    return str(text or '').replace('|','/').replace('\n',' ')[:140]
def fmt(v):
    return str(v) if v is not None else '—'

def main():
    paths=sorted(H.glob('20??-??-??.json'),reverse=True)[:4]
    status={}
    try:status=json.loads((H/'status.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):pass
    games=[]
    for path in paths:
        try:data=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):continue
        for row in (data.get('matches') or {}).values():
            fixture=(row or {}).get('fixture') or {}
            if not fixture.get('home') or not fixture.get('away'):continue
            pts=((row.get('thermometer') or {}).get('points') or [])
            st=row.get('stats') or {}
            sides=[st.get('home') or {},st.get('away') or {}]
            scouts=[]
            for key,label in [('shots_on','Chutes no alvo'),('shots_off','Chutes para fora'),('corners','Escanteios'),('big_chances','Grandes chances'),('dangerous_attacks','Ataques perigosos')]:
                if any(key in side for side in sides):
                    scouts.append(label+': '+fmt(sides[0].get(key))+'×'+fmt(sides[1].get(key)))
            games.append((path.stem,fixture,len(pts),', '.join(scouts),len(row.get('observations') or [])))
    lines=['# ☁ NEXUS — Relatório de coletas','',f'Atualizado pelo GitHub Actions. Último status: **{safe(status.get("updated_at")) or "ainda não executado"}**.',
           '',f'Fontes da última execução: **{safe(", ".join(status.get("sources") or [])) or "nenhuma confirmada"}**. Jogos ao vivo encontrados: **{int(status.get("live_found") or 0)}**.',
           '','**Importante:** cada mercado abaixo indica somente quais informações foram capturadas. O coletor não registra odds nem probabilidades; portanto, EV+, stake e lucro real **não foram calculados**.',
           '','| Dia | Partida | Placar | Pressão (minutos) | Scouts/mercados observáveis |','|---|---|---|---:|---|']
    for day,game,num,scouts,obs in games[:130]:
        name=safe(game.get('home'))+' × '+safe(game.get('away'))
        details=scouts if scouts else 'Somente placar (Over/Under, BTTS, Match Odds sem odds)'
        lines.append(f'| {safe(day)} | {name} | {safe(game.get("score"))} | {num} | {safe(details)} |')
    if not games:lines.append('| — | **Aguardando primeira coleta** | — | — | Sem histórico salvo |')
    lines.extend(['','## Mercados acompanhados','',
                  '- **Over/Under, Ambas marcam (BTTS), Match Odds e Lay Correct Score:** acompanhamento do placar; não existe EV sem odds verificadas.',
                  '- **Escanteios:** somente quando o total de escanteios for informado.',
                  '- **Finalizações e grandes chances:** somente quando os respectivos scouts forem informados.',
                  '- **Termômetro:** minutos realmente coletados, sem preencher minutos inexistentes.',
                  '','[Ver execuções](https://github.com/lulualcides-sys/nexus-score-gratis/actions)'])
    H.mkdir(exist_ok=True)
    (H/'PAINEL.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Painel atualizado:',len(games),'partidas')
if __name__=='__main__':main()
