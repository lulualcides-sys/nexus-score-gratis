# NEXUS SCORE — Pesquisa comparativa de cinco plataformas

**Data da análise:** 09/10/2026 · **Abrangência:** NEXUS Original 5.39 e NEXUS Web (repositório `lulualcides-sys/nexus-score-gratis`).

**Objetivo:** inspirar melhorias próprias nos modelos, leitura de partidas, UX, filtros e auditoria. Não copiar código, interface protegida, previsões privadas ou reutilizar dados de plataformas sem autorização.

## Resumo executivo

1. **FootyStats é o principal exemplo para o pré-live por mercados**, com comparação casa/fora, histórico, xG, cantos, BTTS, Over/Under, meio-tempo, API JSON. A documentação confirma odds FT/BTTS, chutes, escanteios e até minutos dos escanteios. Porém as atualizações declaradas da API são a cada **20 minutos** e a cobertura gratuita é limitada: não substitui a coleta minuto a minuto. Os termos proíbem revenda/redistribuição de dados e reprodução concorrente do serviço. Uso de API depende de chave e permissão para o caso concreto.
2. **Forebet é a principal referência de apresentação de previsões probabilísticas**, com 1X2, placar estimado, gols médios, séries estatísticas, HT/FT, Over/Under, BTTS, cantos e cartões. Oferece previsões ao vivo recalculadas a cada minuto em seu próprio site, mas não foi encontrada uma API pública oficial autorizada para replicar essas previsões. O NEXUS deve construir seu próprio modelo, não usar os números do Forebet como dados de treinamento sem uma licença.
3. **Soccerway é referência de cadastro único de partidas e contexto**, com ligas, equipes, tabelas, escalações, H2H, gols, substituições, cartões, forma e xG em alguns jogos. Nada foi verificado que conceda acesso gratuito de integração/redistribuição desses dados; usá-lo como referência visual e fonte de validação humana, não como promessa de feed.
4. **LiveScore é referência de experiência ao vivo**: hierarquia de ligas, favoritos, placares, datas, escalações e notícias. Foi possível confirmar recursos pela página institucional, mas não uma API pública para uso no NEXUS. Serve sobretudo para UX e verificações cruzadas pontuais.
5. **Radar Esportivo é referência de descoberta por estratégia com filtros simples**, como confirmou o desenvolvedor 433 Data no Google Play. O site público é renderizado dinamicamente, e suas regras internas, métodos, tempos e odds não puderam ser inspecionados de maneira verificável. A ideia útil é um botão/preset para selecionar somente partidas que atendam a critérios auditáveis.

## 1. FootyStats — inventário e aplicação

**Site de previsões:** https://footystats.org/predictions

**API, documentação e preços:** https://footystats.org/api — https://footystats.org/api/documentations/match-details — https://footystats.org/api/documentations/match-schedule-and-stats

**Termos:** https://footystats.org/api/documentations/terms-of-use-and-legal

**Recursos públicos identificados:** previsões postadas por usuários e estimativas estatísticas, seções 1X2, vitória mandante/visitante, placar correto, BTTS, gols Over 1.5/2.5, escanteios; comparação de win%, pontos/jogo e média de gols; menus de xG, cartões, árbitros, jogos por metade, H2H e CSV. **Atenção:** o leaderboard e o saldo de moedas virtuais representam *tracking de palpites*, não auditoria de lucro real.

**Campos documentados na API:** `odds_ft_1/x/2`, `odds_ft_over05..45`, `odds_btts_yes/no`, cartões, finalizações no gol/fora, cantos e `team_a_corner_timings`/`team_b_corner_timings`, gols e minutos, dados pré-jogo em `pre_match_home_ppg`/`pre_match_away_ppg`, HT e FT. Validar exemplos, cobertura por competição e timestamps reais antes de confiar em determinado campo.

**Ganho NEXUS:** filtros mercado/condição e estatísticas casa/fora; mostrar `form_home` e `form_away` separadamente; apresentar chance BTTS, Over HT, 1X2 e mercado HT/FT como estimativa *apenas se calculada e testada internamente*. Congelar as odds por fonte/casa/minuto. Ao vivo, a API de 20 minutos **não** deve preencher minutos faltantes do termômetro.

**Riscos:** a página API lista plano Free limitado à Premier League e planos pagos (na consulta, Hobby £29,99/mês com 50 ligas), com redações distintas por localização. Não prometer integração gratuita ilimitada. Site proíbe revenda e redistribuição; obter autorização adequada antes de usar em produto público concorrente.

## 2. Soccerway — inventário e aplicação

**Site:** https://br.soccerway.com/ — https://pt.soccerway.com/

**Verificado:** amplo índice de ligas; calendários/resultados, tabelas, forma de clubes, H2H, escalações, gols, cartões, substituições, posse, xG dependendo da partida; jogadores e estatísticas de carreira.

**Ganho NEXUS:** normalização de partidas em `canonical_fixture_id`, diferenciação de equipes parecidas, escalas/jogadores, dupla verificação de rodada/divisão, tabela contextual (`precisa vencer`/G4/rebaixamento) **somente quando a regra da competição e pontos verificáveis permitirem**. Consolidar ESPN/FotMob/SofaScore por identidade em vez de duplicar cartões.

**Risco:** site informativo não equivale a API licenciada; aplicações com JavaScript e conteúdo protegido podem impedir coleta automática, e permissão comercial exige confirmação.

## 3. LiveScore — inventário e aplicação

**Site:** https://www.livescore.com/en/

**Verificado:** navegação por países/competições, favoritos, tabela de resultados, buscas, forma de apresentação em tempo real, escalações e informações da partida, resultados/notícias.

**Ganho NEXUS:** lista rápida e limpa com **um jogo por confronto**, etiquetas compactas (ao vivo, HT, final), favoritos, alertas apenas sobre novas transições reais (gol, expulsão, domínio), atualização transparente com horário da última coleta; manter um botão '🌡️ Só com termômetro' e permitir filtros por um clique.

**Risco:** sem API oficial pública verificada. A promessa de atualização segundo a segundo não deve ser importada para o NEXUS quando nossas fontes atualizam periodicamente.

## 4. Radar Esportivo — inventário e aplicação

**Site:** https://radaresportivo.com/

**App oficial:** https://play.google.com/store/apps/details?id=com.radaresportivo.app

**Verificado:** o app de 433 Data declara procurar partidas compatíveis com estratégias personalizadas de apostas por meio de filtros; a descrição da página pesquisável aponta dados de gols, escanteios e cartões. **Não** foi possível inspecionar o interior do site ou confirmar API, variáveis precisas, condições de regra ou qualidade dos sinais.

**Ganho NEXUS:** criar presets auditáveis (sem painel avançado que se abre sozinho):
- `Só com termômetro` = cobertura mínima de minutos.
- `Pressão + finalizações` = vantagem nos últimos 5/10 min E chutes efetivamente confirmados.
- `Possível Over` = placar, minuto, históricos e probabilidade de modelo calibrado; não disparar apenas porque há pressão.
- `Canto em sequência` = cantos com minuto confirmado ou alterações observadas entre snapshots, nunca backdating inventado.
- `Zebra reagindo` = favorito definido por odds pré-jogo *verificadas* e zebra mostrando melhora observável; não inferir favorito somente pela pressão.

Estes são **presets propostos para o NEXUS**, não recursos internos comprovados do Radar Esportivo.

## 5. Forebet — inventário e aplicação

**Site:** https://www.forebet.com/pt/ — https://www.forebet.com/pt/live-predictions

**Guia:** https://www.forebet.com/en/news-about-the-site/24674-how-to-use-forebet

**Verificado:** previsão 1/X/2 em porcentagem, placar correto, gols médios, tendências/contexto estatístico, odds, clima, forma casa/fora, confrontos, lesões e suspensões quando disponíveis. Categorias HT/FT, intervalos, BTTS, cantos, cartões e 1X2 ao vivo. O site declara recalcular as próprias previsões durante jogos a cada minuto, mas o conteúdo ao vivo bloqueou o acesso direto na inspeção e isso não confirma uma API pública para terceiros.

**Ganho NEXUS:** versão do pré-live congelada, histórico de variação do cenário de 1X2 condicionado a estado (minuto, placar, cartões); cenários **gerados por modelo próprio** com probabilidades que somam 100% e avaliação de Brier/log loss. Explicar por que o favorito piorou/melhorou sem mudar retroativamente a previsão feita antes da partida. Pré-live histórico não pode virar preço ao vivo.

**Risco:** porcentagens Forebet não equivalem a treinamento nem validação do NEXUS. Sem licença/dados, não copiar previsões para alimentar o produto ou calcular EV+.

## Comparação com o que já existe no NEXUS

**Original 5.39:** possui scanner, termômetro por minuto, pressão separada por equipe, leitura contextual própria, odds de fontes públicas, amostras históricas, pré-live salvo, modelo Poisson **experimental não calibrado**, EV teórico e auditoria descritiva 1/X/2. Não há comprovação de backtest walk-forward calibrado e há categorias em que a cobertura falta. A deduplicação e a fonte/proveniência exigem monitoramento contínuo.

**Web:** exporta jogos/eventos, odds 1X2 da mesma casa e captura, P/L paper somente após liquidação, avaliação de alertas 5/10/15 min, e experimentos multissource; a amostra real cross-verified entre provedores não foi comprovada como ampla. Não afirmar integração real com serviços citados neste estudo.

## Prioridades executáveis, sem alterar produção prematuramente

| Prioridade | Trabalho | Evidência de sucesso |
|---|---|---|
| P0 | Qualidade de dados + IDs canônicos + proveniência/timestamp + deduplicação em ambas versões | Um único jogo; 2 fontes concordando quando disponíveis; ausência explícita quando não; odds no mercado/casa corretos. |
| P1 | Radar de mercado pré-live: gols por metade, BTTS, 1X2, cantos, forma casa/fora e H2H | Campos reais com denominador da amostra, campeonato e status de fonte; nenhum `0` fabricado. |
| P1 | Linha de tempo da previsão: congelar pré-live, registrar mudanças ao vivo e motivos de transição | Snapshots por minuto real coletado; nunca reconstruir histórico usando resultado posterior. |
| P1 | Scanner com presets de um clique e justificativa por alerta | Alertas precisos, controles persistentes, sem repetir jogo nem ícone; explicação curta time/minuto/dados. |
| P2 | Treino offline Poisson + Dixon-Coles/Elo/Glicko e avaliação walk-forward | Backtest por temporadas **não vistas**; Brier/log loss, cobertura, baseline e amostras por mercado/liga. |
| P2 | Avaliar gols nos próximos 5/10/15 min com risco condicional ao time/minuto/placar | Compara com taxa-base por liga, minuto e placar; intervalo de confiança e deduplicação de janela. |
| P3 | Mapa de chutes, xG e xT evento-a-evento somente se licenciados | Coordenadas e resultados de chutes reais; fonte/atribuição e precisão de cobertura verificadas. |
| P3 | Auditoria financeira por mercado, liga e minuto | Odds de **entrada** e operações liquidadas com stake e custos reais; `netPl` separado de paper. |

### Engenharia gratuita e bibliotecas candidatas

- **openfootball/football.json:** https://github.com/openfootball/football.json — public domain, resultados/fixtures e temporadas históricas para baselines. Atenção: a própria documentação alerta que o repositório upstream pode não estar atualizado diariamente; não serve como feed ao vivo.
- **penaltyblog:** https://github.com/martineastwood/penaltyblog — modelos Poisson/Dixon-Coles em Python, licença MIT (ver licença antes de integrar). Bom para benchmark.
- **soccerdata:** https://github.com/probberechts/soccerdata — framework Apache-2.0; licença da biblioteca NÃO concede direitos automáticos sobre dados dos sites de origem. Melhor em experiências isoladas/histórico, conforme `AGENTS.md` do NEXUS Web.
- **StatsBomb Open Data:** https://github.com/hudl/open-data — eventos, escalações e posições de determinados campeonatos/jogos; exigências de atribuição e termos próprios; não é feed ao vivo ilimitado.
- **socceraction:** https://github.com/ML-KULeuven/socceraction — MIT, converte eventos e estima xT/VAEP. Exige eventos com posição real.

## Escopo de implantação e risco

**Não executado neste estudo:** contratação/acesso de API paga, extração em massa dos sites citados, implantação em produção Web/PC, treino em histórico próprio com split temporal, garantia de EV+ ou lucro. Nesta etapa, a pesquisa fundamenta a próxima implementação com permissões e métricas verificáveis.

**Recomendação:** começar por **cadastro canônico + medição de cobertura e consistência + auditoria cronológica**. Depois integrar recursos de pré-live por mercado e variação do cenário condicionado ao minuto. Aumentar o número de sites indiscriminadamente pode *piorar* a duplicação de partidas e a desinformação do modelo.

## Fontes originais pesquisadas

1. https://footystats.org/predictions
2. https://footystats.org/api
3. https://footystats.org/api/documentations/match-details
4. https://footystats.org/api/documentations/match-schedule-and-stats
5. https://footystats.org/api/documentations/terms-of-use-and-legal
6. https://footystats.org/academy/tracking-predictions
7. https://br.soccerway.com/
8. https://pt.soccerway.com/
9. https://www.livescore.com/en/
10. https://radaresportivo.com/
11. https://play.google.com/store/apps/details?id=com.radaresportivo.app
12. https://www.forebet.com/pt/
13. https://www.forebet.com/pt/live-predictions
14. https://www.forebet.com/en/news-about-the-site/24674-how-to-use-forebet
15. https://github.com/openfootball/football.json
16. https://github.com/martineastwood/penaltyblog
17. https://github.com/probberechts/soccerdata
18. https://github.com/hudl/open-data
19. https://github.com/ML-KULeuven/socceraction