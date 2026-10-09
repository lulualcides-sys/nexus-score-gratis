# NEXUS SCORE — Coleta gratuita no GitHub ☁️

### [📊 ABRIR PAINEL DE COLETAS E MERCADOS](history/PAINEL.md)

**[Ver execuções automáticas](../../actions)** · [Histórico bruto](history/) · [Status da última coleta](history/status.json)

O GitHub Actions coleta periodicamente partidas públicas, salva apenas os dados realmente retornados e gera o relatório privado `history/PAINEL.md`. Agendamento: **uma vez por hora**, sujeito a atrasos e limites do GitHub Free; não é transmissão minuto a minuto.

**Mercados:** Over/Under, Ambas Marcam, Match Odds e Lay Correct Score podem ter acompanhamento de placar; escanteios, finalizações e grandes chances exigem estatísticas adicionais. A presença de um mercado na lista **não significa EV+**. Não coletamos odds de entrada nem calculamos lucro real.

**NEXUS 5.28:** adiciona a aba `☁ Coletas GitHub` ao aplicativo local, lendo uma pasta `history/` sincronizada ou dados privados via `gh` autenticado. O NEXUS completo ainda não está hospedado no GitHub Actions — apenas o coletor e o relatório.

**Não exige cartão nem servidor pago.** É um repositório privado; preserve-o assim para manter o histórico privado.
