# Cinco plataformas analisadas e fontes autorizadas — NEXUS (09/10/2026)

## Plataforma → ideia → condição de implantação

| Plataforma | Referência útil | O que não presumir |
|---|---|---|
| [FootyStats](https://footystats.org/predictions) | Forma casa/fora, mercados gols 1.5/2.5, BTTS, cantos, HT/FT, xG, odds e H2H | [API](https://footystats.org/api) tem acesso gratuito limitado, planos pagos; [termos](https://footystats.org/api/documentations/terms-of-use-and-legal) vedam redistribuição e cópia concorrente. Não usar sem licenciamento aplicável. |
| [Soccerway](https://br.soccerway.com/) | Navegação por campeonato, rodada, escalações, tabelas e identidade de clubes | Portal público não é prova de API gratuita ou autorização de redistribuição. |
| [LiveScore](https://www.livescore.com/en/) | Lista rápida, favoritos, placar ao vivo, eventos e atualização visível | UX é referência; não há feed oficial gratuito confirmado para NEXUS. |
| [Radar Esportivo](https://radaresportivo.com/) | Filtros/presets prontos por estratégia | As regras e desempenho internos não foram auditados; inspirar scanner próprio, sem importar sinais privados. |
| [Forebet](https://www.forebet.com/pt/) | Probabilidades e cenários 1X2, placar estimado, BTTS e HT/FT, leitura live | Método/percentuais são proprietários; não reproduzir endpoint sem licença nem afirmar calibração a partir do site. |

## APIs e programas GitHub

- [openfootball/football.json](https://github.com/openfootball/football.json): resultados/fixtures **CC0/domínio público**, sem chave. Incluir apenas FT com confirmação explícita, liga/equipes/dia; fonte histórica **não serve** para odds ou xG live. Upstream nem sempre é atualizado diariamente.
- [openfootball/south-america](https://github.com/openfootball/south-america): dados CC0 de Brasil, Argentina e Colombia em Football.TXT. Verificar atualização e conversão antes de importar.
- [StatsBomb Open Data](https://github.com/statsbomb/open-data): eventos e posições para campeonatos limitados, com condições específicas de uso e atribuição.
- [socceraction](https://github.com/ML-KULeuven/socceraction): MIT para xT/VAEP em dados evento-a-evento legítimos; não fabricar coordenadas.
- [soccerdata](https://github.com/probberechts/soccerdata): somente histórico/experimento, respeitando condições de cada provedor. Não instalar scraping irrestrito em produção.
- [TheSportsDB](https://www.thesportsdb.com/documentation): API V1 de demonstração com **limites e termos**, Premium para livescores e mais recursos; [condições de uso](https://www.thesportsdb.com/docs_terms_of_use.php).
- [football-data.co.uk](https://football-data.co.uk/contact.php): **não autorizado para integração de produto comercial ou treinamento AI por scraping automatizado**, conforme texto publicado pelo próprio operador. Não contornar com um script GitHub.

## Implementação e validação

**NEXUS Original 5.40:** arquivo `nexus_score/openfootball_cc0.py` no pacote desktop. Consulta CC0 como *fallback histórico* quando ESPN/SofaScore/FotMob não possuem amostra suficiente; compara nomes normalizados, usa dois anos de calendário e partidas FT anteriores à data do jogo, cache 24 h. Não converte isso em odd ao vivo, scouts por minuto ou lucro real. Continua com Poisson local experimental, não calibrado.

**NEXUS Web (este repositório):** `experiments/openfootball_cc0_probe.py` + testes: cruzamento offline de **placares finais** contra registros CC0 de mesma liga, mandante, visitante e dia. O experimento não modifica `history/`, `web/data.json`, alertas, EV ou operações. Sua execução não implica aumento comprovado da cobertura.

## Roadmap de maior retorno

1. **P0:** identidade canônica e provenance por campo (fonte, timestamps, divergência, confiança de cruzamento) e um jogo por confronto.
2. **P1:** radar pré-live com forma casa/fora, H2H real, BTTS/gols HT/FT e amostra por competição; filtros de um clique.
3. **P1:** preservar snapshots pré-jogo e registrar evolução ao vivo por observação real; sem reescrever histórico.
4. **P2:** benchmark simples Poisson vs mercado vs modelo próprio por **walk-forward**. Brier, log loss e amostra por liga. Sem alegar EV real a partir de taxa de acerto.
5. **P3:** mapas de chute/xT somente com coordenadas reais devidamente licenciadas; P/L por mercado quando houver odds, stake, liquidação e comissão comprovadas.

### Critérios de segurança de dados

**Nenhuma chave privilegiada, login de terceiros, bypass de paywall ou API privada** faz parte deste projeto. Bibliotecas no GitHub não conferem licenças sobre as bases de onde extraem informação. Experimentos offline não devem anunciar resultados financeiros ou estatísticas live.
