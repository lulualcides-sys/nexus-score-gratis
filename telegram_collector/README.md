# NEXUS DATA LAB — Multimercado + Telegram 00h01 (v3)

Coletor GRATUITO independente, sem alterar os scripts centrais da coleta NEXUS, o GitHub Pages ou a Bolsa/Layback.
Origem: `https://nexus-score-gratis.pages.dev/data.json`, exportação pública já produzida pelo NEXUS.
Arquivo persistente: branch `market-telegram-data`, pasta `market-history/`.

## Rotina de trabalho

- **Três vezes por hora (:14, :34 e :54 UTC):** coleta silenciosa de todos os jogos públicos e lê os registros pré-live/live salvos em `history/` pelo NEXUS (sem nova chamada a API paga ou gasto adicional). Preserva o histórico e deduplica. O cron do GitHub pode atrasar.
- Preserva as odds observadas dos mercados que a fonte efetivamente forneceu, inclusive **cotações alternativas de outras casas**, com preço, minuto do jogo, fase, fonte e horário disponível.
- Categoriza **27 famílias de mercados**; o catálogo NÃO indica disponibilidade de odds para todas.
- O histórico é acumulado sem transformações retroativas: registros sem hora/casa/fase inequívoca ficam disponíveis para auditoria, mas NÃO contam como odds verificadas no fechamento diário.
- **00h01 Brasília (03h01 UTC):** `nexus-football-daily.yml` no `nexus-quant-paper` lê diretamente o arquivo do **dia anterior** da branch de dados e envia uma única mensagem ao MESMO bot `@NexusQuantAlertasBot`. O consolidado persistente do NEXUS é arquivado às 00h12 e não bloqueia a notificação. A execução é aproximada, não em tempo real garantido.
- O resumo distingue **todos os jogos monitorados** dos que apresentam **volume negociado ≥ R$ 3.000 comprovado em BRL** por fonte, horário, tipo de volume e valor. Moeda não convertida ou ausência de liquidez => `unknown`. **Resultado por liquidez** só usa eventos qualificados; total geral fica separado. Sem preços, métricas e liquidez fictícias.
- Não calcula EV+, ROI nem lucro fictício. Um percentual de acerto de mercado não é rentabilidade. O arquivo `market-history/daily/AAAA-MM-DD.json` registra os resultados; o arquivo `.sent.json` evita reenvios em execuções normais. Atrasos, quedas antes de persistir o marcador ou falhas de entrega impedem garantia absoluta de exatamente uma mensagem.
- Coletas e notificações dependem da disponibilidade do GitHub Actions e das fontes; a precisão temporal do NEXUS não é segundo a segundo.

## Reaproveitar o Telegram existente

O Telegram utiliza a conexão existente **no repositório `lulualcides-sys/nexus-quant-paper`**. O token `TELEGRAM_BOT_TOKEN` e o chat criptografado já pertencem a esse projeto; não é necessário copiá-los para o NEXUS SCORE nem criar novo bot.
O NEXUS envia **zero** notificações diretamente: coleta e gera apenas dados. O workflow do Nexus Quant envia no máximo uma mensagem de futebol por data, com marcador em `state/nexus_football_reports/AAAA-MM-DD.json`. O relatório normal dos dez robôs do Nexus Quant continua separado e inalterado.
O arquivo `.sent.json` gerado pelo `daily.py` no NEXUS só seria usado no modo de envio direto, atualmente desativado. As mensagens dependem do bot previamente conectado e da execução do Action de destino.

## Testes

```bash
python3 -m unittest discover -s telegram_collector/tests -v
python3 telegram_collector/collect.py --archive market-history --history-dir history --no-telegram
python3 telegram_collector/daily.py --archive market-history --no-telegram
```

O segundo comando exige acesso ao snapshot público do NEXUS. O terceiro pode gerar um relatório vazio se não houver coletas salvas para o dia. A rotina de produção lê arquivos da branch isolada.

## Onde encontrar odds — sem custos extras

Veja [ODDS_SOURCES.md](ODDS_SOURCES.md). O NEXUS já contém integrações opcionais OddsPapi (limite de cota mensal próprio) e API-Football. A coleta independente reaproveita os dados exportados e o `history/` do mesmo repositório, **sem duplicar requisições de odds nem gastar cota de API à parte**. Fontes alternativas exigem licença ou chave gratuita próprias e só serão ativadas conforme disponibilidade e direitos de uso.
