# NEXUS DATA LAB — Multimercado + Telegram diário (v2)

Coletor GRATUITO independente, sem alterar os scripts centrais da coleta NEXUS, o GitHub Pages ou a Bolsa/Layback.
Origem: `https://nexus-score-gratis.pages.dev/data.json`, exportação pública já produzida pelo NEXUS.
Arquivo persistente: branch `market-telegram-data`, pasta `market-history/`.

## Rotina de trabalho

- **De hora em hora (minuto 41 UTC):** coleta silenciosa de todos os jogos disponíveis no snapshot NEXUS, com deduplicação. **Não envia Telegram a cada jogo ou execução.**
- Preserva as odds observadas dos mercados que a fonte efetivamente forneceu, inclusive **cotações alternativas de outras casas**, com preço, minuto do jogo, fase, fonte e horário disponível.
- Categoriza **27 famílias de mercados**; o catálogo NÃO indica disponibilidade de odds para todas.
- O histórico é acumulado sem transformações retroativas: registros sem hora/casa/fase inequívoca ficam disponíveis para auditoria, mas NÃO contam como odds verificadas no fechamento diário.
- **19h15 horário de Brasília, todos os dias:** `.github/workflows/nexus-market-daily.yml` consolida o histórico local disponível e envia **uma mensagem resumida ao MESMO bot do Telegram**, `@NexusQuantAlertasBot` (via Secrets da conta).
- O resumo traz jogos, partidas encerradas, quantidade de odds com proveniência, mercados e casas realmente capturados e placares esportivos agregados de 1X2, Over 2.5, BTTS, cantos, amarelos e chutes no alvo, quando dados existem.
- Não calcula EV+, ROI nem lucro fictício. Um percentual de acerto de mercado não é rentabilidade. O arquivo `market-history/daily/AAAA-MM-DD.json` registra os resultados; o arquivo `.sent.json` evita reenvios em execuções normais. Atrasos, quedas antes de persistir o marcador ou falhas de entrega impedem garantia absoluta de exatamente uma mensagem.
- Coletas e notificações dependem da disponibilidade do GitHub Actions e das fontes; a precisão temporal do NEXUS não é segundo a segundo.

## Reaproveitar o Telegram existente

Os workflows usam SOMENTE os GitHub Secrets já previstos:
`TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`. Não registre um novo bot. Os Secrets devem estar cadastrados neste repositório NEXUS. Nenhuma credencial é escrita em arquivos, logs ou mensagens públicas.
Se faltarem os Secrets, o histórico e os resumos em JSON continuam; as mensagens NÃO serão enviadas.
Para testar manualmente um dia no Actions, execute `NEXUS | Telegram resumo diário` pelo `workflow_dispatch`; se a marca `.sent.json` existir para a data local, não repetirá o envio.

## Testes

```bash
python3 -m unittest discover -s telegram_collector/tests -v
python3 telegram_collector/collect.py --archive market-history --no-telegram
python3 telegram_collector/daily.py --archive market-history --no-telegram
```

O segundo comando exige acesso ao snapshot público do NEXUS. O terceiro pode gerar um relatório vazio se não houver coletas salvas para o dia. A rotina de produção lê arquivos da branch isolada.

## Onde encontrar odds — sem custos extras

Veja [ODDS_SOURCES.md](ODDS_SOURCES.md). O NEXUS já contém integrações opcionais OddsPapi (limite de cota mensal próprio) e API-Football. A coleta independente apenas reaproveita os dados já exportados, **sem duplicar requisições nem gastar cota de API à parte**. Fontes alternativas exigem licença ou chave gratuita próprias e só serão ativadas conforme disponibilidade e direitos de uso.
