# SoccerData — avaliação isolada para o NEXUS

Este experimento NÃO altera histórico, odds, alertas ou lucros do NEXUS em produção.
Roda no GitHub Actions com dependências instaladas apenas no runner temporário.

Fontes de teste: **ClubElo** (ratings) e **Understat** (xG histórico da Premier League 2025/26, se disponível) via `soccerdata==1.9.1`. A biblioteca também oferece ESPN, FBref, Football-Data, Understat e outras, porém várias dependem de scraping, podem bloquear acesso e devem ser avaliadas individualmente.

Critérios de aceite antes de ligar ao NEXUS:
1. Endpoint retorna dados reais e identificáveis.
2. Cobertura e vinculação segura a partidas reais; sem confundir nomes iguais.
3. Evidência de benefício adicional aos nossos coletores atuais.
4. Direitos de utilização/termos da fonte permitidos.
5. Não sobrescrever scouts anteriores nem tratar Elo como EV+/probabilidade calibrada.

Execução: workflow **NEXUS — teste isolado SoccerData**. Artefato `soccerdata-probe` indica status `ok`, `empty` ou `unavailable`. Uma indisponibilidade do endpoint não quebra o NEXUS.

Dependências de execução: Python 3.11, `soccerdata==1.9.1`. Consulte https://github.com/probberechts/soccerdata e a licença Apache-2.0.

Se o teste não tiver dados suficientes, manter o coletor atual e documentar o bloqueio em vez de afirmar que melhoramos a cobertura.
