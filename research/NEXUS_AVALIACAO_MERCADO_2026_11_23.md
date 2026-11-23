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

## 3. Ranking de força (Elo) — estudo
Script: `research/elo_study.py` (`python3 research/elo_study.py history`). Elo com margem de gols, calculado em ordem cronológica: cada jogo é previsto só com resultados anteriores. 15.632 jogos e 4.225 times, vindos dos arquivos diários e do cache de forma FotMob. Os parâmetros (K, mando, faixa de empate, peso do Elo na mistura com o modelo atual) foram ajustados nos 60% mais antigos.

| Teste (jogos não vistos) | Brier 1X2 |
|---|---|
| Atual, 1.364 jogos | 0,6016 |
| 50% Elo + 50% atual (K=45, mando 65, empate 0,2) | **0,5993** |
| Atual, 304 jogos com odd | 0,5982 |
| Elo misto, 304 jogos com odd | **0,5828** |
| Mercado, 304 jogos com odd | 0,5330 |

Melhora consistente, mas pequena: **ainda não promovido**. Limite: só ~4 jogos por time (30 dias de histórico), e o Elo precisa de temporadas inteiras para estabilizar.
Próximo passo: semear o Elo com temporadas anteriores de fonte com licença aberta (OpenFootball CC0, já usado para auditoria) e repetir a validação. Promover só se ganhar com folga fora da amostra e não piorar os mercados de gols.

## 4. Elo com temporadas anteriores (OpenFootball CC0)
Script: `research/elo_history_study.py` (`MIN=30 python3 research/elo_history_study.py history <pasta_openfootball>`). Entram 58 arquivos de temporada (2022/23 a 2026/27) de 17 ligas: Inglaterra 1–4, Alemanha 1–2, Espanha 1–2, Itália 1–2, França 1–2, Holanda, Portugal, Bélgica, Turquia e México. São 8.160 jogos históricos; 300 dos 337 times FotMob dessas ligas foram ligados por nome dentro da própria liga. O Elo só é usado quando os dois times têm pelo menos MIN jogos anteriores; caso contrário, vale o modelo atual.

| Teste (não visto) | n | Atual | Elo | Mercado |
|---|---|---|---|---|
| MIN=30, todos | 70 | 0,6130 | **0,5956** | — |
| MIN=30, com odd | 29 | 0,6244 | **0,5839** | 0,5431 |
| MIN=15, com odd | 47 | 0,6062 | **0,5883** | 0,5243 |

Melhora clara onde há histórico, mas com amostra pequena: o período de teste coincide com a data fifa. Ainda abaixo do mercado. **Não promovido.** Reavaliar com algumas semanas de rodadas de liga; se o ganho se mantiver com n ≥ 200 jogos com odd e sem piora nos mercados de gols, promover o Elo para as ligas com histórico.
