# NEXUS — matriz de fontes de odds (18/10/2026)

Objetivo: aumentar odds **observadas** sem falsificar valores, sem contornar bloqueios de acesso e sem contratar serviços.

## Fontes avaliadas
1. ESPN: manter fallback atual quando o placar e o mercado estiverem ligados a um mesmo fixture verificável. Registrar bookmaker, preço, mercado e timestamp.
2. API-Football: usar o módulo já existente somente se a chave e as permissões disponíveis cobrirem o endpoint de odds; sem presumir plano gratuito nem aumentar custos.
3. The Odds API (theoddsapi.com): plano Free 2026 cobre NFL/NBA/MLB, **não** futebol. Não promete resolver a cobertura futebolística sem plano pago.
4. The Odds API (the-odds-api.com): histórico de odds é pago. Não habilitar consultas históricas no projeto gratuito.
5. Betfair Historical Data: tem série BASIC gratuita documentada para dados históricos em granularidade de 1 minuto, mas exige conferência de direitos de acesso, correspondência de mercados e tratamento como histórico, não cotação de entrada já executada.

## Estados obrigatórios
- `verified_pregame`: preço observado antes de kickoff com timestamp e bookmaker reais.
- `historical_closing`: preço histórico de fechamento, nunca equivalente a entrada.
- `live_observed`: horário de consulta explícito, sem atribuir a momento anterior.
- `unavailable`: sem fonte, credencial, preço ou timestamp válido.
- `fictional_scenario`: odd digitada pelo usuário ou valor hipotético; NUNCA agregar ao P/L paper real.

O avaliador de sinais de 40 minutos deve manter desfechos `pendente`, `indeterminado` ou `janela_incompleta` quando não houver prova do período inteiro. Recomenda-se validar as taxas fora da amostra e agrupar por partida para reduzir pseudo-replicação de alertas.
