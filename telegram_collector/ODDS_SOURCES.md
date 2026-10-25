# Auditoria de fontes gratuitas de odds — 25/10/2026

Objetivo: cobrir o maior número possível de mercados e casas **sem mensalidade**, com proveniência auditável. A cobertura não equivale a “todas as odds de todos os mercados” — nenhuma fonte verificada entrega isso gratuitamente com alta frequência e acesso irrestrito.

| Fonte | Plano gratuito e mercados | Situação no NEXUS | Observações |
|---|---|---|---|
| **OddsPapi v4** | 250 chamadas mensais; vários esportes, mercados e bookmakers por consulta, sujeito à cobertura real | **Integração opcional existente** no `oddspapi_odds.py`; consome cota só nas duas janelas UTC configuradas, quando há chave `NEXUS_ODDSPAPI_KEY` | Melhor opção para descobertas multimercado. A integração atual valida 1X2, linhas Over/Under 1.5/2.5/3.5, BTTS e alguns AH; demais IDs não serão inventados. [Cota](https://oddspapi.io/us/docs/requests-and-quota); [Plano](https://oddspapi.io/blog/free-sports-data-api/) |
| **API-Football** | 100 chamadas por dia, endpoints de odds pré-live e live, oferta varia por partida/casa | Integração opcional `api_football_odds.py`, atualmente restringe a exportação à 1X2 por prudência | Pode ampliar para catálogo oficial de bets/bookmakers se chave autorizada estiver configurada. [Plano](https://www.api-football.com/pricing) |
| **UK Odds API** | 300 chamadas por mês, 2 casas (10Bet e BetFred) e mercados core | Não conectado; apenas opção de pesquisa | Inclui gols, escanteios e alguns mercados core; mercados avançados são pagos. Exige registro/chave própria. [Planos](https://docs.ukoddsapi.com/getting-started/plans-and-pricing) |
| **TheRundown** | Anuncia plano gratuito limitado a linhas pré-jogo e algumas casas | Não conectado; apenas opção de pesquisa | Atenção ao tipo de cobertura: player props e linhas avançadas ficam em planos superiores. [Referência](https://therundown.io/soccer-odds-api) |
| **TheOddsAPI.com** (sem hífens) | Plano grátis atual limitado a NFL/NBA/MLB, moneyline | Não adicionar ao NEXUS de futebol gratuito | Futebol não está incluído no plano gratuito atual. [Planos](https://theoddsapi.com/pricing) |
| **The-Odds-API.com** (com hífens) | Anuncia 500 créditos mensais em todos os esportes; créditos não equivalem a consultas ilimitadas | Não conectado; validar termos e limites antes de considerar | Empresa/API diferente da acima; histórico e múltiplos mercados consomem créditos. [Planos](https://the-odds-api.com/) |
| **Odds-API.io** | Novas chaves gratuitas suspensas | Não integrar | Chaves antigas podem seguir ativas, mas não é uma fonte nova gratuita acessível. [Comunicado](https://odds-api.io/pricing/free) |

## Casas e rastreabilidade

As odds disponíveis no NEXUS da OddsPapi já permitem buscar as casas **Pinnacle, Bet365 e Betano BR**, quando cada casa oferece cotações válidas e ativas. Nome listado em API não prova cotação disponível num jogo. Não misturar preços de casas distintas num trio 1X2, não atribuir timestamp de coleta a uma odd de origem desconhecida, nem chamar preço de fechamento de preço de entrada.

O coletor `telegram_collector/collect.py` preserva **a melhor odd e as alternativas** do snapshot NEXUS, classificando as famílias conhecidas e retendo os rótulos de mercados ainda não reconhecidos. A rotina `daily.py` só conta cotações com casa, fonte, preço válido, data/hora e escopo pré-live/live coerentes.

## Sobre REA (Reverse Engineer Anything)

Referência oficial: https://github.com/morluto/rea

REA permite inspecionar páginas, JavaScript, apps e formatos de dados **com autorização**. É útil para entender interfaces e campos de APIs públicas e documentar adaptadores. **Não é uma fonte de odds**, nem garante acesso gratuito às APIs de casas. Não usar REA para extrair credenciais, contornar 403/429, paywalls, bloqueios de país, limites ou proibições de uso. Sem autorização explícita de cada operador para uso automatizado, manter somente APIs e datasets cujo acesso seja permitido.

## Próximos avanços seguros

1. Aumentar cobertura pelo catálogo **oficial** da OddsPapi, sem extrapolar IDs de mercados e sem ultrapassar a cota global compartilhada com o NEXUS.
2. Medir e divulgar proporção de partidas com odds confiáveis **por mercado, casa, campeonato e horário**, em vez de prometer cobertura integral.
3. Quando existir autorização, adicionar novos conectores opcionais sem alterar o coletor histórico e sem publicar chaves.
4. Somente calcular P/L simulado quando houver seleção predefinida antes do início, cotações com origem/tempo e liquidação verificável. Não tratar gols observados retrospectivamente como greens de uma estratégia.

**Nenhuma API nova foi ativada por esta implantação.** Custos adicionais previstos: R$ 0. A precisão e disponibilidade dependem das fontes.
