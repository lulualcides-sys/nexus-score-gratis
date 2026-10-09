#!/usr/bin/env python3
"""Gera painel legível de dados coletados. Não calcula EV nem lucro."""
import json
from pathlib import Path
from datetime import datetime,timezone
import html
import math

H=Path(__file__).resolve().parent/'history'

def safe(text):
    return str(text or '').replace('|','/').replace('\n',' ')[:140]
def fmt(v):
    return str(v) if v is not None else '—'

def load_json(path):
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):
        return {}

def currency(value,unit='BRL'):
    try:
        n=float(value)
        if not math.isfinite(n):return '—'
        return f'{n:+,.2f}'.replace(',','_').replace('.',',').replace('_','.')+' '+str(unit)[:6]
    except (ValueError,TypeError):
        return '—'

def pl_section(lines, heading, doc):
    lines.extend(['',heading,''])
    if not doc.get('snapshot_only') or not isinstance(doc.get('markets'),list):
        lines.append('Ainda sem snapshot de operacoes importadas. Nenhum resultado inferido.')
        return
    lines.append('Fonte: **'+safe(doc.get('source') or doc.get('provider') or 'sem fonte')+
                 '** · Atualizacao: **'+safe(doc.get('observed_at'))+'**.')
    lines.append('**'+safe(doc.get('operations'))+' operacoes | P/L liquido: '+
                 currency(doc.get('net_pl'),doc.get('currency') or 'BRL')+'**.')
    lines.extend(['','| Mercado informado | Operacoes | P/L real |','|---|---:|---:|'])
    rows=sorted((v for v in doc.get('markets',[]) if isinstance(v,dict)),
                key=lambda x: float(x.get('net_pl') or 0),reverse=True)
    for row in rows[:80]:
        lines.append('| '+safe(row.get('market'))+' | '+safe(row.get('operations'))+' | '+
                     currency(row.get('net_pl'),doc.get('currency') or 'BRL')+' |')
    lines.append('')
    lines.append('*Dados importados da origem; nao sao lucros de apostas recomendadas pelo NEXUS. Sem stake/risco auditado, nao converter para unidades.*')

def main():
    paths=sorted(H.glob('20??-??-??.json'),reverse=True)[:4]
    status={}
    try:status=json.loads((H/'status.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):pass
    odds_status=load_json(H/'odds_status.json')
    bolsa=load_json(H/'bolsa_netpl.json')
    pc=load_json(H/'pc_netpl.json')
    games=[]
    signals={'pending':0,'settled':0,'won':0}
    odds_games=0
    for path in paths:
        try:data=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):continue
        for row in (data.get('matches') or {}).values():
            fixture=(row or {}).get('fixture') or {}
            if (row or {}).get('odds_quotes'):odds_games+=1
            for signal in (row or {}).get('paper_signals') or []:
                if not isinstance(signal,dict):continue
                flag=signal.get('status')
                if flag=='pending':signals['pending']+=1
                elif flag=='settled':
                    signals['settled']+=1
                    if signal.get('won') is True:signals['won']+=1
            if not fixture.get('home') or not fixture.get('away'):continue
            pts=((row.get('thermometer') or {}).get('points') or [])
            st=row.get('stats') or {}
            sides=[st.get('home') or {},st.get('away') or {}]
            scouts=[]
            for key,label in [('shots_on','Chutes no alvo'),('shots_off','Chutes para fora'),('corners','Escanteios'),('big_chances','Grandes chances'),('dangerous_attacks','Ataques perigosos')]:
                if any(key in side for side in sides):
                    scouts.append(label+': '+fmt(sides[0].get(key))+'×'+fmt(sides[1].get(key)))
            odds_names={'home':'Casa','draw':'Empate','away':'Fora'}
            quotes=[]
            for q in (row.get('odds_quotes') or []):
                if not isinstance(q,dict) or q.get('market')!='1x2':continue
                try:
                    value=float(q.get('odds'))
                    if math.isfinite(value) and value>1.0:
                        quotes.append(odds_names.get(q.get('selection'),safe(q.get('selection')))+
                                      ' '+f'{value:.2f}'.replace('.',','))
                except (TypeError,ValueError):pass
            odd_summary=('Match Odds 1X2: '+', '.join(quotes[:3])) if quotes else ''
            games.append((path.stem,fixture,len(pts),', '.join(scouts),
                          len(row.get('observations') or []),odd_summary))
    lines=['# ☁ NEXUS — Painel privado de dados, mercados e P/L','',
           '**CONFIDENCIAL:** este painel inclui dados financeiros. Mantenha o repositório GitHub privado.',
           '',f'Atualizado pelo GitHub Actions. Último status da coleta: **{safe(status.get("updated_at")) or "ainda não executado"}**.',
           '',f'Fontes da última execução: **{safe(", ".join(status.get("sources") or [])) or "nenhuma confirmada"}**. Jogos ao vivo encontrados: **{int(status.get("live_found") or 0)}**.',
           '','**Importante:** odds 1X2 reais podem ser salvas por outro módulo; sinais EV+ só existem quando há modelo com dados anteriores ao jogo. P/L da Bolsa é histórico independente, não resultado dos sinais.',
           '','| Dia | Partida | Placar | Pressão (minutos) | Scouts/mercados observáveis |','|---|---|---|---:|---|']
    for day,game,num,scouts,obs,odd_summary in games[:130]:
        name=safe(game.get('home'))+' × '+safe(game.get('away'))
        details='; '.join(x for x in (scouts,odd_summary) if x) or 'Somente placar (Over/Under, BTTS e Lay CS sem odds)'
        lines.append(f'| {safe(day)} | {name} | {safe(game.get("score"))} | {num} | {safe(details)} |')
    if not games:lines.append('| — | **Aguardando primeira coleta** | — | — | Sem histórico salvo |')
    pl_section(lines,'## P/L real por mercado — Bolsa de Aposta',bolsa)
    pl_section(lines,'## P/L real por mercado — importacao do PC',pc)
    # O painel privado já é acessível no NEXUS Original via link GitHub.
    # Não exige deixar a aplicação desktop aberta para gerar este relatório.
    journal=load_json(H/'signal_registry.json')
    cloud_signals=[r for r in (journal.get('items') or []) if isinstance(r,dict)]
    diag=journal.get('diagnostics') or {}
    lines.extend(['','## Alertas automáticos do NEXUS Original 5.29 — execução na nuvem','',
      '**Registros:** '+str(len(cloud_signals))+
      ' | **Jogos monitorados:** '+str(diag.get('matches_checked','—'))+
      ' | **Ao vivo:** '+str(diag.get('matches_live','—'))+
      ' | **Termômetros recentes:** '+str(diag.get('fresh_pressure','—'))+'.',
      '',
      'Regra proveniente do motor 5.29; scouts acumulados são fotografias, não o minuto real de um lance. '
      'Nenhuma odd ao vivo ou EV+ é deduzida de pressão. Registro com PC desligado: GitHub Actions.',
      '',
      '| Momento UTC | Partida | Equipe | Regra / origem | Gol 5min | Gol 10min | Gol 15min | EV+ |',
      '|---|---|---|---|---|---|---|---|'])
    for row in cloud_signals[:100]:
        outcomes=row.get('outcomes') or {}
        kind=('scout acumulado' if row.get('basis')=='cumulative_stat_snapshot'
              else 'pressão observada' if row.get('basis')=='pressure_window'
              else 'evento confirmado')
        name=safe(row.get('home'))+' × '+safe(row.get('away'))
        side=row.get('team')
        team=safe(row.get('home') if side=='home' else row.get('away') if side=='away' else 'Equipe não definida')
        lines.append('| '+safe(row.get('captured_at'))+' | '+name+
                     ' | '+team+' ('+safe(row.get('minute'))+"') | "+
                     safe(row.get('icon'))+' '+safe(row.get('rule'))+' · '+kind+
                     ' | '+safe(outcomes.get('5') or 'pendente')+
                     ' | '+safe(outcomes.get('10') or 'pendente')+
                     ' | '+safe(outcomes.get('15') or 'pendente')+
                     ' | indisponível |')
    if not cloud_signals:lines.append('| — | Sem alertas elegíveis | — | Aguardando fonte | — | — | — | — |')
    lines.extend(['','## Odds verificadas e EV+ experimental','',
        f'Jogos com odds registradas nos ultimos dias: **{odds_games}**.',
        f'Novas cotacoes capturadas na ultima execucao: **{fmt(odds_status.get("quotes_recorded"))}**.',
        f'Sinais pendentes: **{signals["pending"]}**. Sinais liquidados: **{signals["settled"]}**. '
        f'Acertos entre liquidados: **{signals["won"]}**.',
        'Um EV+ estimado nao garante lucro; sem odds e probabilidade validas nenhum sinal e fabricado.',
        '','## Mercados acompanhados','',
                  '- **Over/Under, Ambas marcam (BTTS), Match Odds e Lay Correct Score:** acompanhamento do placar; não existe EV sem odds verificadas.',
                  '- **Escanteios:** somente quando o total de escanteios for informado.',
                  '- **Finalizações e grandes chances:** somente quando os respectivos scouts forem informados.',
                  '- **Termômetro:** minutos realmente coletados, sem preencher minutos inexistentes.',
                  '','[Ver execuções](https://github.com/lulualcides-sys/nexus-score-gratis/actions)'])
    H.mkdir(exist_ok=True)
    (H/'PAINEL.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Painel atualizado:',len(games),'partidas')
if __name__=='__main__':main()
