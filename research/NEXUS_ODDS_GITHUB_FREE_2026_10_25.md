# NEXUS — pesquisas GitHub para odds sem cadastro (25/10/2026)

**Objetivo:** maximizar cobertura de jogos importantes e mercados com preços observados, preservando fonte, bookmaker, timestamp e linha; zero assinatura, sem conta pessoal.

## Projetos avaliados e decisões

| Projeto | O que oferece | Decisão |
|---|---|---|
| [sportsdata-mcp](https://github.com/DanielTomaro13/sportsdata-mcp) | Especificação pública da Pinnacle Arcadia guest API; full matchup/straight markets, odds americanas, linhas/periods. Não requer cadastro. | **Implementado** em `telegram_collector/pinnacle_guest.py` com coleta a cada 3h e limite de partidas. Coleta real chegou a 1.249 odds em 11 jogos, com uma consulta 403 isolada. Subsequentemente o coletor passa a evitar partidas negadas por 24h e interrompe consulta ao receber 401/403/429. |
| [sparegk/smart-odds](https://github.com/sparegk/smart-odds) | Contratos de importação exigindo bookmaker, mercado, seleção, período, horário da fonte e tratamento de lookahead em backtests. | **Referência de validação.** Não é um feed próprio de odds grátis. Nosso histórico já mantém timebox/linha/fonte, sem inventar liquidez. |
| [mtarcure/soccer-betting-scraper](https://github.com/mtarcure/soccer-betting-scraper) | Estatísticas de BTTS, O/U, escanteios, cartões e finalizações, baseadas em fontes públicas, sem chave. Código MIT. | **Referência futura para previsão**, NÃO usar estatísticas como se fossem odds de bookmaker. Usa Football-Data.co.uk como origem (restrições abaixo). |
| [jordantete/OddsHarvester](https://github.com/jordantete/OddsHarvester) | Scraper de odds de mercados múltiplos do OddsPortal. | **Não ativado.** Os termos do OddsPortal não concedem autorização geral para coleta automatizada. |
| [Ken-Mutisya/sports-odds-scraper](https://github.com/Ken-Mutisya/sports-odds-scraper) | Odds de casas por Apify, com mercado total/handicap. | **Não ativado.** O projeto cobra por evento após pequena amostra, pode exigir proxy residencial; não atende custo zero. |
| [omkarcloud/flashscore-scraper](https://github.com/omkarcloud/flashscore-scraper) | Descreve API de odds/estatísticas do Flashscore. | **Pesquisa, sem integração.** Alegações de gratuidade e acesso contínuo em nuvem não foram verificadas, e o site pode proibir automação. |
| [AnishKhetani/premier-league-data](https://github.com/AnishKhetani/premier-league-data) | Pipeline MIT sobre CSV de odds e resultados de Premier League (1X2, Over/Under 2.5, AH), abertura e fechamento. | **Referência de campos**, não incorporamos dados licenciados de terceiros. |
| [football-data.co.uk/matches/fixtures.csv](https://football-data.co.uk/matches/fixtures.csv) | Planilha gratuita de futuras partidas com odds 1X2, O/U 2.5, AH de várias casas. | **Não automatizado no GitHub público.** O fornecedor limita download automatizado a 2 vezes/semana, apenas uso pessoal/acadêmico; redistribuição em repositório público não está claramente autorizada. [Política](https://football-data.co.uk/contact.php). |

## Mudanças implementadas

- `telegram_collector/pinnacle_guest.py`: consulta com chave PÚBLICA do cliente visitante (não chave pessoal), conector separado a cada três horas, limites de payload e partidas, sem contas/cookies/proxies. Salva em `market-history/public-no-key/pinnacle-*.json` e status.
- Identifica mercados pelo código original Pinnacle: `s;0;m` 1X2 FT; `s;1;m` 1X2 1º tempo; `s;0;ou;2.5` total gols FT; `s;0;tt;1.5;home` gols do mandante; `s;0;s;-0.5` handicap FT; mais códigos de 1º tempo. O `period`, `line`, `raw_market_key` e odds americana original são preservados.
- `telegram_collector/coverage_radar.py`: cruza odds da Pinnacle com partidas NEXUS de ligas importantes somente se **ambos os clubes** + kickoff ±10 min e timestamp pré-live forem compatíveis; odds indicativas de terceiros não são misturadas com preços da casa.
- `src/nexus_football_daily.py` (repositório separado `nexus-quant-paper`): informa cobertura e preços da Pinnacle no único Telegram diário de 00h01 Brasília, sem alertas por jogo.
- `market-history/public-no-key/pinnacle-status.json`: distingue `ok`, `blocked`, `partial_blocked`, `unavailable` e possíveis `403`; um resultado bloqueado nunca é tratado como cobertura de odds de fonte.
- Auditoria de preço **não é garantia de aposta executável**, liquidez > R$3 mil nem EV positivo.

## Critérios para próximos conectores

1. Fonte expressamente pública, sem cadastro/assinatura. Sem tentativa de superar 401/403, CAPTCHA ou restrições de IP.
2. Limites baixos e previsíveis; preferir múltiplos mercados num único request, em vez de sondar cada jogo agressivamente.
3. Preservar bookmaker, mercado original, linha, período, odds, fase, data/hora de observação e status de acesso.
4. Rejeitar nomes de times ou ligas ambíguos: não copiar preços entre jogos.
5. Não colocar CSV de terceiros cujo uso/redistribuição seja restrito em GitHub público.
6. Apenas calcular ROI/PL prospectivo com odds registradas antes do evento e entradas congeladas.
