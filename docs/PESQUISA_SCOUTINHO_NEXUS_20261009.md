# Pesquisa de produto: Scoutinho como referência de ideias para o NEXUS SCORE
**09/10/2026 — estudo público, arquitetura independente.**

Este documento registra o que pesquisar e como validar antes de implementar novas ideias no NEXUS Web e Original. **Não** importa código, probabilidades, odds ou dados privados do Scoutinho.

## Superfícies analisadas
- [Página inicial: agenda, filtros, cartões de resultado e previsões](https://scoutinho.app/)
- [Catálogo público de 34 artigos](https://scoutinho.app/artigos)
- [Sobre: metodologia, transparência, calibração e walk-forward](https://scoutinho.app/sobre)
- [Exemplo de página de partida com previsões, forma, gráficos, mapas, estatísticas e scouts por tempo](https://scoutinho.app/jogo/gimnasia-lp-vs-atletico-tucuman-2026-10-09)
- [Análises editoriais](https://scoutinho.app/analises)

## Regras de produto que devemos adotar
1. **Pressão:** a direção do momentum indica quem cria cerco, não que haverá gol. A própria pesquisa do Scoutinho observou pouca alteração na taxa de qualquer gol após pressão intensa; ver [gráfico de pressão](https://scoutinho.app/artigos/como-ler-o-grafico-de-pressao). NEXUS deve distinguir evento futuro da equipe que pressiona e evento de qualquer equipe.
2. **Qualidade, não volume:** xG, grandes chances e chutes no alvo descrevem melhor oportunidades do que posse/escanteios. Não converter totais em coordenadas ou xG de chutes individuais; ver [xG](https://scoutinho.app/artigos/o-que-e-xg-gols-esperados), [mapa de chutes](https://scoutinho.app/artigos/como-ler-o-mapa-de-chutes) e [posse](https://scoutinho.app/artigos/quem-tem-mais-posse-de-bola-ganha-o-jogo).
3. **Contexto:** resultado, minuto, mando, agregado, substituições, cartões, força relativa e metas na tabela mudam a interpretação dos mesmos scouts. Ver [pressão e reação](https://scoutinho.app/artigos/a-pressao-anuncia-a-virada-ate-certo-ponto), [substituições](https://scoutinho.app/artigos/o-que-as-substituicoes-dizem-sobre-o-plano-de-cada-time) e [gol tardio](https://scoutinho.app/artigos/com-que-frequencia-sai-gol-depois-dos-75-minutos).
4. **Modelo:** aprender com a *estrutura* de um ensemble, baseline, calibração e backtest cronológico, nunca copiar os pesos de terceiros ou alegar performance alheia. Ver [modelo](https://scoutinho.app/artigos/como-o-scoutinho-monta-uma-previsao), [probabilidade](https://scoutinho.app/artigos/o-que-significa-a-probabilidade-do-modelo) e [Sobre](https://scoutinho.app/sobre).
5. **Explicabilidade:** para cada alerta, exibir time, período observado, fontes, scouts que sustentam a leitura e motivos para ausência do sinal; preservar as análises pré-jogo congeladas.
6. **Auditoria:** não mostrar precisão calibrada, +u ou EV real sem dados históricos rotulados, odds de entrada reais e rastreio das versões treinadas somente no passado. Alertas em janela 5/10/15 minutos devem ser comparados à linha de base do mesmo minuto e liga; amostras da mesma partida não são independentes.

## Fontes e bibliotecas abertas candidatas
- [soccerdata](https://github.com/probberechts/soccerdata): conectores históricos. Condições dos provedores e bloqueios exigem isolamento.
- [StatsBomb Open Data](https://github.com/statsbomb/open-data): dados de eventos e coordenadas de jogos selecionados. Conferir termos de uso e fornecer atribuição.
- [socceraction](https://github.com/ML-KULeuven/socceraction): licença MIT, ferramentas SPADL, VAEP, xT para eventos completos, não para estatísticas agregadas.
- [openfootball](https://github.com/openfootball/football.json): resultados históricos públicos para baselines, conferir termos.
- [Football-Data.co.uk](https://www.football-data.co.uk/data.php): fornece CSV/odds, mas **não usar em treinamento automatizado/produto comercial sem verificar permissão**; o site declara restrições.

## Implementação local efetuada — NEXUS Original 5.39
- Novo motor descritivo independente `static/nexus_context_539.js`.
- Explicação expansível `POR QUE ESSA LEITURA?` no próprio cartão da IA: xG, grandes chances, chutes certos, posse improdutiva, pressão recente observada, placar e tempo. Nenhum cartão duplicado nem previsão de gol fabricada.
- `nexus_score/model_audit_539.py`: Brier multiclasses e amostras por liga de trios completos 1X2 arquivados antes do jogo. Somente diagnóstico descritivo, `walk_forward_verified=false`.
- Endpoint local `/api/model-audit` e informação no `NEXUS LAB > MODELO`.
- Testes Python/JavaScript, servidor local e documentação do Original. Esses arquivos pertencem ao pacote desktop, não foram presumidos compatíveis com o coletor Web deste repositório.

## Próximos marcos
A) Fonte evento-a-evento licenciada + identidade de fixture + mapas de chutes com localização real.
B) Histórico por campeonato com split temporal e baselines Elo/Poisson/mercado.
C) Modelo próprio treinado walk-forward com calibração e relatórios honestos por competição.
D) Alertas ao vivo validados em 5/10/15 min contra taxa-base por minuto e placar.
E) Atributos contextuais auditáveis: agregado mata-mata, mando, motivação na tabela, substituições e expulsões.

**Sem alegações de resultado:** estudar o Scoutinho não transfere seus modelos, dados, acurácia ou histórico financeiro para o NEXUS.