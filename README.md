# NEXUS SCORE — WEB + Coleta gratuita ☁️

**[📱 PREPARAR PUBLICAÇÃO WEB NO CLOUDFLARE](DEPLOY_WEB_CLOUDFLARE.md)** · **[Código web](web/index.html)** · **[Dados esportivos públicos que serão exibidos](web/data.json)**

A versão pública do NEXUS SCORE está publicada em **https://nexus-score-gratis.pages.dev/** por Cloudflare Pages conectado à branch main do GitHub.

**Painel web v5.30 (coletas públicas):** histórico de hoje e 3 dias anteriores (quando retornados pela ESPN), scouts reais disponíveis (finalizações, posse, passes, faltas, cartões etc.), odds capturadas, margem implícita 1X2, resultados esportivos por mercado, alertas na tela e resultados paper de sinais criados antes do início.

**Importante:** o percentual Over/Under/BTTS histórico não é EV+, nem lucro de bot. O P/L paper é desconhecido até existir ao menos um sinal pré-jogo com odd validada e liquidação. P/L pessoal da Bolsa e PC continua privado e **não** é publicado no Cloudflare. Os alertas não são notificações push com o navegador fechado; a coleta é horária, e o snapshot web é normalmente atualizado de duas em duas horas.

---

# NEXUS SCORE — Coleta gratuita no GitHub ☁️

### [📊 ABRIR PAINEL DE COLETAS E MERCADOS](history/PAINEL.md)

**[🖥️ Leitor de P/L do PC — instrucoes](PC_IMPORT.md)** · No servidor privado: snapshot real por mercado, odds capturadas e sinais EV experimentais. A importacao do PC precisa do agente local rodando.

**[Ver execuções automáticas](../../actions)** · [Histórico bruto](history/) · [Status da última coleta](history/status.json)

O GitHub Actions coleta periodicamente partidas públicas, salva apenas os dados realmente retornados e gera o relatório privado `history/PAINEL.md`. Agendamento: **uma vez por hora**, sujeito a atrasos e limites do GitHub Free; não é transmissão minuto a minuto.

**Mercados:** Over/Under, Ambas Marcam, Match Odds e Lay Correct Score podem ter acompanhamento de placar; escanteios, finalizações e grandes chances exigem estatísticas adicionais. A presença de um mercado na lista **não significa EV+**. Não coletamos odds de entrada nem calculamos lucro real.

**NEXUS 5.28:** adiciona a aba `☁ Coletas GitHub` ao aplicativo local, lendo uma pasta `history/` sincronizada ou dados privados via `gh` autenticado. O NEXUS completo ainda não está hospedado no GitHub Actions — apenas o coletor e o relatório.

**Não exige cartão nem servidor pago.** É um repositório privado; preserve-o assim para manter o histórico privado.
