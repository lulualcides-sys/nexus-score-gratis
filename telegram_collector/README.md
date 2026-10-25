# NEXUS Market Research + Telegram (v1)

Este coletor **não altera os scripts do NEXUS**, não acessa a conta Bolsa/Layback e não opera apostas. Usa apenas `https://nexus-score-gratis.pages.dev/data.json`, o snapshot público produzido pelo NEXUS.

## O que está coletado

- Lê todos os jogos presentes na exportação e arquiva snapshots **que mudaram**, identificados por jogo/data/minuto/placar/scouts/odds reais.
- Mantém a evidência observada: fonte, horário, odd decimal **quando existente**, minuto, placar, scouts e resultados confirmados após o fim.
- Catálogo de 27 famílias (Match Odds, dupla chance, total/linhas de gols, ambas marcam, escanteios, cartões, chutes, chances, handicaps etc.). Uma família no catálogo **não significa odds disponíveis**.
- Usa mercados descobertos dinamicamente na lista de odds do NEXUS. Não transforma odd pré-jogo em live, não inventa cotações ou EV, não apresenta simulação como lucro real.
- Guarda o histórico na **branch `market-telegram-data`**; evita commits horários na `main` e builds extras do Cloudflare.
- GitHub Actions dispara a coleta às **:41 de cada hora** (pode atrasar), independentemente do PC. Não equivale a coleta a cada minuto.

## Telegram

No GitHub, vá a **Settings → Secrets and variables → Actions** do repositório NEXUS e adicione dois **repository secrets**:
- `TELEGRAM_BOT_TOKEN`: crie um bot com [@BotFather](https://t.me/BotFather). Nunca envie o token no chat ou faça commit.
- `TELEGRAM_CHAT_ID`: abra o chat do bot, toque em **Start**. Pegue o `chat.id` pelo método oficial `getUpdates`, pelo console do próprio bot ou ferramenta confiável. Também pode usar ID do grupo/canal ao qual o bot tenha permissão.

O envio é um resumo com os dados observados e os mercados que **realmente tiveram cotações**. Não é uma recomendação de aposta ou promessa de lucro. Sem os dois secrets, o coletor continua a criar histórico, mas **não envia mensagens**.

## Teste e segurança

```bash
python3 -m unittest discover -s telegram_collector/tests -v
python3 telegram_collector/collect.py --archive market-history --no-telegram
```

O primeiro comando usa casos sintéticos (não invoca rede). O segundo consulta o NEXUS público; necessita rede. A rotina de GitHub tem validação antes da coleta. Os dados só entram quando existem e podem ser verificáveis. Para ampliar a cobertura será necessário conectar fontes de odds/estatísticas com licença e cadência adequadas.

**Status de implantação:** a presença destes arquivos não comprova sucesso do primeiro job, disponibilidade da fonte ao vivo ou entrega de Telegram. Confirme no GitHub Actions e no arquivo `market-history/status.json` da branch de dados.
