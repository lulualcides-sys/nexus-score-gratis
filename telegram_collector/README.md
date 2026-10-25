# NEXUS DATA LAB — Multimercado + Telegram diário (v2)

Coletor GRATUITO independente, sem alterar os scripts centrais da coleta NEXUS, o GitHub Pages ou a Bolsa/Layback.
Origem: `https://nexus-score-gratis.pages.dev/data.json`, exportação pública já produzida pelo NEXUS.
Arquivo persistente: branch `market-telegram-data`, pasta `market-history/`.

## Rotina de trabalho

- **De hora em hora (minuto 41 UTC):** coleta silenciosa de todos os jogos disponíveis no snapshot NEXUS, com deduplicação. **Não envia Telegram a cada jogo ou execução.**
- Preserva as odds observadas dos mercados que a fonte efetivamente forneceu, inclusive **cotações alternativas de outras casas**, com preço, minuto do jogo, fase, fonte e horário disponível.
- Categoriza **27 famílias de mercados**; o catálogo NÃO indica disponibilidade de odds para todas.
- O histórico é acumulado sem transformações retroativas: registros sem hora/casa/fase inequívoca ficam disponíveis para auditoria, mas NÃO contam como odds verificadas no fechamento diário.
- **19h15 horário de Brasília, todos os dias:** `.github/workflows/nexus-market-daily.yml` gera somente o arquivo diário na branch de dados. **19h45:** o workflow `nexus-football-daily.yml` do repositório `nexus-quant-paper` lê esse arquivo e entrega uma mensagem resumida pelo MESMO bot `@NexusQuantAlertasBot`. Os dois relatórios são processos independentes.
- O resumo traz jogos, partidas encerradas, quantidade de odds com proveniência, mercados e casas realmente capturados e placares esportivos agregados de 1X2, Over 2.5, BTTS, cantos, amarelos e chutes no alvo, quando dados existem.
- Não calcula EV+, ROI nem lucro fictício. Um percentual de acerto de mercado não é rentabilidade. O arquivo `market-history/daily/AAAA-MM-DD.json` registra os resultados; o arquivo `.sent.json` evita reenvios em execuções normais. Atrasos, quedas antes de persistir o marcador ou falhas de entrega impedem garantia absoluta de exatamente uma mensagem.
- Coletas e notificações dependem da disponibilidade do GitHub Actions e das fontes; a precisão temporal do NEXUS não é segundo a segundo.

## Reaproveitar o Telegram existente

O Telegram utiliza a conexão existente **no repositório `lulualcides-sys/nexus-quant-paper`**. O token `TELEGRAM_BOT_TOKEN` e o chat criptografado já pertencem a esse projeto; não é necessário copiá-los para o NEXUS SCORE nem criar novo bot.
O NEXUS envia **zero** notificações diretamente: coleta e gera apenas dados. O workflow do Nexus Quant envia no máximo uma mensagem de futebol por data, com marcador em `state/nexus_football_reports/AAAA-MM-DD.json`. O relatório normal dos dez robôs do Nexus Quant continua separado e inalterado.
O arquivo `.sent.json` gerado pelo `daily.py` no NEXUS só seria usado no modo de envio direto, atualmente desativado. As mensagens dependem do bot previamente conectado e da execução do Action de destino.

## Testes

```bash
python3 -m unittest discover -s telegram_collector/tests -v
python3 telegram_collector/collect.py --archive market-history --no-telegram
python3 telegram_collector/daily.py --archive market-history --no-telegram
```

O segundo comando exige acesso ao snapshot público do NEXUS. O terceiro pode gerar um relatório vazio se não houver coletas salvas para o dia. A rotina de produção lê arquivos da branch isolada.

## Onde encontrar odds — sem custos extras

Veja [ODDS_SOURCES.md](ODDS_SOURCES.md). O NEXUS já contém integrações opcionais OddsPapi (limite de cota mensal próprio) e API-Football. A coleta independente apenas reaproveita os dados já exportados, **sem duplicar requisições nem gastar cota de API à parte**. Fontes alternativas exigem licença ou chave gratuita próprias e só serão ativadas conforme disponibilidade e direitos de uso.
