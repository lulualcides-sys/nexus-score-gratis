# NEXUS SCORE — WEB + Coleta gratuita ☁️

**[📱 PREPARAR PUBLICAÇÃO WEB NO CLOUDFLARE](DEPLOY_WEB_CLOUDFLARE.md)** · **[Código web](web/index.html)** · **[Dados esportivos públicos que serão exibidos](web/data.json)**

A versão pública do NEXUS SCORE está publicada em **https://nexus-score-gratis.pages.dev/** por Cloudflare Pages conectado à branch main do GitHub.

**Painel web v5.30 (coletas públicas):** jogos de hoje e dos 2 dias anteriores (3 dias corridos, conforme dados ESPN); analise separada dos ate 10 jogos anteriores disponiveis de cada time na mesma competicao, scouts reais disponíveis (finalizações, posse, passes, faltas, cartões etc.), odds capturadas, margem implícita 1X2, resultados esportivos por mercado, alertas na tela e resultados paper de sinais criados antes do início.

**Importante:** o percentual Over/Under/BTTS histórico não é EV+, nem lucro de bot. O P/L paper é desconhecido até existir ao menos um sinal pré-jogo com odd validada e liquidação. P/L pessoal da Bolsa e PC continua privado e **não** é publicado no Cloudflare. Os alertas não são notificações push com o navegador fechado; a coleta é horária, e o snapshot web é normalmente atualizado de duas em duas horas.

---

# NEXUS SCORE — Coleta gratuita no GitHub ☁️

### [📊 ABRIR PAINEL DE COLETAS E MERCADOS](history/PAINEL.md)

**[🖥️ Leitor de P/L do PC — instrucoes](PC_IMPORT.md)** · No servidor privado: snapshot real por mercado, odds capturadas e sinais EV experimentais. A importacao do PC precisa do agente local rodando.

**[Ver execuções automáticas](../../actions)** · [Histórico bruto](history/) · [Status da última coleta](history/status.json)

**Alertas com o computador desligado (primeira etapa, NEXUS Cloud):** o GitHub executa `signal_registry.py` nas rotinas periódicas, registra os sinais das regras de pressão 🔥/🧨/🚨 disponíveis no código web 5.29 e acompanha gols confirmados em 5, 10 e 15 minutos em `history/signal_registry.json`. O histórico aparece na aba **Coletas GitHub** e no **NEXUS LAB → Alertas**. O job pode atrasar e não substitui dados ausentes. **Não é o motor completo instalado no PC**: para migração idêntica, ainda é necessário disponibilizar seus módulos locais originais. EV+ requer odds ao vivo e modelo calibrado e não é inferido da pressão.

O GitHub Actions coleta periodicamente partidas públicas, salva apenas os dados realmente retornados e gera o relatório privado `history/PAINEL.md`. Agendamento: **uma vez por hora**, sujeito a atrasos e limites do GitHub Free; não é transmissão minuto a minuto.

**Mercados:** Over/Under, Ambas Marcam, Match Odds e Lay Correct Score podem ter acompanhamento de placar; escanteios, finalizações e grandes chances exigem estatísticas adicionais. A presença de um mercado na lista **não significa EV+**. Não coletamos odds de entrada nem calculamos lucro real.

**SoccerData / Understat — xG histórico validado em 09/10/2026:** instalamos SoccerData 1.9.1 somente no runner de teste, confirmamos 380 jogos completos da Premier League 2025/26, e arquivamos as 380 partidas em `history/soccerdata_understat_2025_26.json` no repositório privado. O painel em **Coletas GitHub** mostra apenas a contagem; o site não publica o histórico bruto. Não é xG minuto a minuto nem EV+; não misturar com odds de entrada. O endpoint ClubElo falhou no teste e permanece desligado. Testes e evidências em `experiments/soccerdata/` e nas Actions `soccerdata-evaluation.yml` e `nexus-understat-history.yml`.

**NEXUS 5.28:** adiciona a aba `☁ Coletas GitHub` ao aplicativo local, lendo uma pasta `history/` sincronizada ou dados privados via `gh` autenticado. O NEXUS completo ainda não está hospedado no GitHub Actions — apenas o coletor e o relatório.

**Não exige cartão nem servidor pago.** É um repositório privado; preserve-o assim para manter o histórico privado.

## Multiplas fontes esportivas (NEXUS WEB)

- **FotMob:** descoberta diaria ampliada, escudos do CDN FotMob e detalhes/pressao, quando disponiveis. Rotas 2026 `/api/data/matches` e `/api/data/matchDetails`.
- **ESPN:** verificacao de campeonatos, scouts, escudos ESPN e ultimos 10 resultados disponiveis por time na propria competicao.
- **Football-Data.co.uk:** consulta CSV historica de 10 divisoes europeias; cruza placares e complementa scouts somente quando times e resultados coincidem. Odds de fechamento sao rotuladas como *historicas*, nunca aproveitadas como se fossem odds de entrada.
- **OpenLigaDB:** conferencia independente de Bundesliga e horarios/resultados, sem misturar jogos de nome ou horario incerto.
- **Understat/Betfair Historical:** bases de referencia para trabalhos futuros de xG e odds historicas; nao estao ligadas ao painel ao vivo.

O painel publico usa **hoje mais dois dias anteriores, no fuso America/Sao_Paulo**, e mostra os escudos oficiais encontrados; se algum logo falhar, exibe as iniciais. Em cada dia, organiza os jogos do horario mais cedo para o mais tarde. Cada confronto oferece ate 10 jogos anteriores por time, separadamente.

Em `history/multi_source_status.json`, acompanhe quantos CSVs foram consultados, scouts completados e resultados cruzados. A simples consulta de uma fonte **nao** significa que ela forneceu partidas na janela atual. Resultados paper e P/L pessoal da Bolsa continuam distintos.
