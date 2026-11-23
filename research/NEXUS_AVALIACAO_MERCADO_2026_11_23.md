# NEXUS × mercado — avaliação de 23/11/2026

Estudo offline com os dados já coletados. Não altera o modelo publicado.

## 1. Motor NEXUS × odds reais (1X2)
Previsão congelada antes do jogo e odd capturada **antes** do apito (sem vazamento), 123 jogos encerrados (`web/data.json` → `pregame_archive`). Margem média das casas: 6,5%.

| | Brier | Log loss | Acerto do favorito |
|---|---|---|---|
| NEXUS | 0,6275 | 1,0433 | 47,2% |
| Mercado (sem margem) | **0,5884** | **0,9853** | 48,8% |

Apostas simuladas (1 u) onde o NEXUS vê EV acima do limiar: EV>0%: −6,6% ROI (161 apostas); >5%: −1,2% (129); >10%: +1,8% (112); >20%: −7,1% (88). Sem sinal consistente: é ruído. **Não há evidência de valor.**

## 2. Variantes do modelo (validação cronológica)
3.400 jogos dos arquivos diários; ajuste nos 60% mais antigos e teste nos 40% mais novos (1.360). Grade: força do prior, média do prior, fatores casa/fora e correção Dixon-Coles.

| | Brier 1X2 | Brier Mais/Menos 2,5 | Brier Ambas marcam |
|---|---|---|---|
| Atual | 0,6018 | 0,2390 | 0,2485 |
| Melhor variante (k=3, prior 1,2, casa 1,2, fora 1,0, rho 0) | 0,5997 | 0,2419 | 0,2521 |
| Mercado (296 jogos de teste com odd) | **0,535** | — | — |

Ganho mínimo no 1X2 e piora nos mercados de gols: **não promovido**. O limite está nas entradas (só média de gols dos últimos 10 jogos), não nos parâmetros.

## Próximo passo que pode fechar a diferença
Entradas mais fortes, com validação temporal: força por Elo/rating entre temporadas, xG histórico (Understat já arquivado para a Premier League) e mando por equipe. Odds de Mais/Menos 2,5 e Ambas marcam passam a ser congeladas (API-Football) para medir esses mercados contra preço.
