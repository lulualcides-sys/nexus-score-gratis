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

## Evolução de qualidade do bookmaker e seleção dinâmica (25/10/2026)

O pipeline passou de capturar linhas isoladas para **validar a integridade do livro de preços**:

- `telegram_collector/pinnacle_guest.py` seleciona até **16 jogos por rodada de três horas**. Usa o `priority-coverage.json` para reservar até um terço das consultas para partidas relevantes sem odds ou apenas com cotações indicativas e roda as outras partidas do catálogo em intervalos de três horas. Não usa contas adicionais, proxies ou contorno de 401/403/429.
- `telegram_collector/market_depth.py` valida frescor da captura, bookmaker, presença de todas as seleções, linha original, período e odds numéricas. Só calcula **overround** (margem implícita da casa) em mercados completos: 1X2 com três resultados; totais e handicap com os dois lados. Handicaps têm pontos com sinais opostos por seleção; são agrupados pela chave original do mercado.
- O relatório `market-history/public-no-key/pinnacle-depth.json` registra mercados completos/incompletos, preços inválidos e mediana de overround por família; **overround não é lucro, ROI nem volume transacionado**.
- `telegram_collector/coverage_radar.py` só incorpora a auditoria se for de até quatro horas atrás. O resumo do Telegram de **00h01 Brasília** agora inclui linhas completas, margem 1X2 quando disponível e até três jogos importantes ainda sem odds. O bot financeiro permanece separado.
- Um dos testes de nuvem mostrou **16 jogos, 1.384 odds elegíveis para auditoria, 676 linhas completas, 0 linhas incompletas, 18 registros rejeitados** e margem mediana 1X2 de aproximadamente 5,02%. Números da janela observada, não expectativa de próximos jogos. 

### Fontes avaliadas adicionalmente

- [lacausecrypto/mcp-sports-hub](https://github.com/lacausecrypto/mcp-sports-hub): muitas integrações; as fontes de odds de maior cobertura exigem conta, chave ou testes de acesso. Serve como catálogo de opções, **não uma fonte própria de odds sem cadastro**.
- [DanielTomaro13/sportsdata-mcp Unibet Kambi](https://github.com/DanielTomaro13/sportsdata-mcp/blob/main/documentation/Unibet.md): aposta esportiva com oferta pública de diversos mercados, mas direcionada ao mercado australiano e com geobloqueio frequente em datacenters. **Não implantado**; depende de confirmação de uso autorizado e disponibilidade em GitHub Actions.
- [odds-api/odds-api](https://github.com/odds-api/odds-api): SDK, exemplos e contrato OpenAPI abertos, porém dados reais precisam de chave `ODDS_API_KEY`. **Não resolve** a exigência de zero cadastro.
- [Betfair licença oficial](https://support.developer.betfair.com/hc/en-us/articles/360002464152-Which-API-Licence-Do-I-Require): qualquer acesso à API oficial Exchange exige uma conta KYC verificada. Sem essa conta, **não declarar volume negociado > R$3.000** usando cotações de outras fontes.
- [pinnacleapi/pinnacleapi-documentation](https://github.com/pinnacleapi/pinnacleapi-documentation): acesso à API oficial da Pinnacle fechado ao público em 2025; nosso coletor usa **somente** a superfície de visitante do site, não a API profissional/licenciada.

**Ainda faltando para paridade com uma casa:** odds de escanteios/cartões com origem verificável; dados de volume negociado genuíno; maior cobertura de competições e eventos; métricas de confiabilidade por fonte; regulamentação e infraestrutura de negociação (não fazem parte de um coletor de pesquisa).


## Continuidade: line movement + saúde de fontes (25/10/2026, Brasil)

A integração ficou mais próxima de um pipeline de dados auditável, sem simular um sportsbook que já precifica todos os mercados:

- \`telegram_collector/market_motion.py\`: lê exclusivamente o histórico da Pinnacle na branch de dados. Compara primeiro e último preço da **mesma seleção, mercado e linha**, com timestamp individual validado **antes** do início do jogo. Mudança apresentada em pontos percentuais de probabilidade **implícita bruta**. Guarda \`pinnacle-motion-latest.json\`; não afirma EV, P&L, probabilidade calibrada ou volume. O primeiro arquivo real trouxe 899 seleções com mudança, em 28 jogos e 53 capturas históricas. Nem todas as partidas permaneciam futuras na hora do resumo; é histórico, não sinal para apostar agora.
- \`telegram_collector/coverage_radar.py\`: inclui apenas resumo de movimento recente, recusando amostras futuras e divergências de timestamps.
- \`src/nexus_football_daily.py\` no projeto \`nexus-quant-paper\`: resumo único das 00h01 menciona movimentos observados e o maior deslocamento de probabilidade implícita. Sem avisos por jogo.
- \`telegram_collector/source_health.py\`: consulta, sem rede e sem chaves, os status do NEXUS, ESPN, TipsAudit, Pinnacle e radar. Registra frescor, número de odds, HTTP 401/403/429, jogos sem odds. Arquiva \`market-history/source-health.json\` na coleta regular.
- Testes de regressão: vigiar se o movimento é realmente pré-jogo, não misturar seleções ou linhas, não usar cotação de um jogo depois de começar e não declarar fonte restrita como saudável.

### Novas referências GitHub (avaliação cuidadosa)

1. **[MadunaCapital/scanner-ingestion](https://github.com/MadunaCapital/scanner-ingestion)** — camada isolada de scrapers e *freshness circuit breaker*, um por site. Padrão arquitetural aproveitado no monitor de fontes; não incorporamos código nem endpoints cuja licença/autorização não esteja clara.
2. **[MadunaCapital/scanner-schemas](https://github.com/MadunaCapital/scanner-schemas)** — especificações de um comparador com fontes públicas na África do Sul. A descrição de um endpoint aberto **não equivale** a licença para redistribuição em GitHub público; não ativamos scraping sem conferir as condições da fonte.
3. **[DanielTomaro13/sportsdata-mcp](https://github.com/DanielTomaro13/sportsdata-mcp)** — inventário adicional de integrações públicas e exigências por provedor. O fato de haver um conector sem chave não autoriza contornar 401/403, um login, CAPTCHA ou termos da casa.
4. **[odds-api/odds-api](https://github.com/odds-api/odds-api)** — API/SDK aberto apenas como ferramenta; produção exige chave. Não cumpre a restrição do usuário.
5. **[Kambi Odds Feed+](https://www.kambi.com/what-we-do/odds-feed/)** — fonte comercial, NÃO é feed gratuito sem cadastro.
6. **[Pinnacle API oficial](https://www.pinnacle.com/en/api)** — acesso requer solicitação e pode ter custo; não confundir com o feed web já observado.

**Limites mantidos:** nenhuma invasão de conta, uso de senha/token alheio, contorno de autenticação, ou mascaramento/proxy para evitar limite; um feed bloqueado será marcado como indisponível. Prioridade de expansão: eventos importantes, cartões, escanteios, tempo real e fonte comprovada de liquidez; odds simuladas nunca substituem odds reais de casa.

### Confiabilidade do envio diário (00h01 Brasília)

O fechamento de futebol no repositório independente `nexus-quant-paper` agora **não envia nem marca como entregue** um dia se o JSON bruto estiver indisponível ou inválido. O workflow tenta às 00h01, 00h21, 00h41 e 01h01 de Brasília; assim atrasos da publicação não viram relatórios vazios ou marcadores permanentes. O marcador existente garante apenas um Telegram válido por dia, e os testes simulam a falha na primeira consulta seguida da entrega correta no retry. Horários do GitHub Actions são aproximados e podem sofrer atraso. Os 10 robôs financeiros não foram alterados.
