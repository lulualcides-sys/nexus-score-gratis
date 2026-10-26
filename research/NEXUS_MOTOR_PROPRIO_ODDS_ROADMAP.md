# NEXUS — Plano de independência de fontes de odds (motor próprio)

> **PADRÃO ATUALIZADO EM 25/10/2026 — PREVALECE SOBRE ITENS HISTÓRICOS DESTE PLANO:** o motor próprio já possui primeira implementação experimental; a orientação atual é **somente estudar e registrar**, sem alterações em produção até novo pedido. Os únicos mercados previstos para o motor próprio são FT/HT 1X2, HT/FT, BTTS, Over/Under de gols, dupla chance, gols por equipe e placar exato. **Não** desenvolver handicap, cartões, escanteios ou mercados de jogadores no motor sem nova instrução. Pesquisa atual e testes de qualidade em [NEXUS_MOTOR_PADRAO_E_ESTUDO_2026_10_25.md](NEXUS_MOTOR_PADRAO_E_ESTUDO_2026_10_25.md).


**Data de definição:** 25 de outubro de 2026  
**Objetivo solicitado:** observar e registrar o funcionamento das fontes/casas de apostas permitidas, aprender com dados históricos e construir **um motor próprio de probabilidades e odds indicativas** no NEXUS. A meta é reduzir ao mínimo a dependência de sites de odds de terceiros, mantendo a qualidade verificável.

> A independência de **preços de casas** é possível por meio de **odds calculadas pelo NEXUS** a partir de dados de partidas e modelos próprios. Isso **não** cria magicamente odds realmente oferecidas por Betano, Stake ou Pinnacle, não reproduz liquidez negociada, e não substitui a necessidade de dados atualizados de jogos, equipes, escalações e resultados.

## 1. Observar agora, reproduzir funcionalidade depois

### Dados externos que vale registrar (se disponibilizados em interfaces autorizadas)
- ID e horário do jogo, liga, mandante/visitante, placar e minuto.
- Casa/fonte, identificação original do mercado, período (partida/1º tempo), seleção, linha, preço e moeda/formato.
- Horário capturado **e** horário da própria casa quando disponível, juntamente com fase pré-live/live, suspensão e mercado indisponível.
- Mudanças de preço por partida e seleção, abertura e último preço conhecido antes do início; quantidade de atualizações e gaps de coleta.
- Estatísticas **observadas** de gols, escanteios, cartões, chutes (por equipe), resultados finais e desfecho por mercado quando ambas as partes tiverem dados.
- Condições das fontes: tempo de resposta, disponibilidade, 401/403/429, lacunas em jogos importantes, geografia/termos de uso da fonte; nunca preencher uma lacuna com odd inventada.
- Registros de mercados exibidos, UX, navegação, filtros, agrupamento de partidas, escalações, alertas e organização da interface. **Não** copiar marca, layout protegido, imagens/código privados ou conteúdo integral de terceiros sem licença.

### Status do que já temos no repositório
- `telegram_collector/pinnacle_guest.py`: snapshots, mercados originais e alterações de preços observados.
- `telegram_collector/market_depth.py`: integridade por linha e margem implícita (overround).
- `telegram_collector/market_motion.py`: movimentos de preço pré-jogo; captura observada, nunca previsão de lucro.
- `telegram_collector/priority_espn.py` e `priority_boxscore.py`: calendário e estatísticas observadas; dados esportivos não são odds.
- `telegram_collector/optional_odds_api.py`: opções oficiais de cartões/escanteios quando o titular fornece chave válida; proteger cota e credencial no GitHub Secrets.
- `telegram_collector/coverage_radar.py` e `source_health.py`: jogo com/sem cobertura e saúde das fontes.
- Histórico em `market-telegram-data/market-history`, relatórios do Telegram enviados pelo projeto separado `nexus-quant-paper`. Não alterar os dez robôs financeiros ao executar este roteiro.

**Este documento não significa que alguma casa, seu algoritmo de precificação ou seu book interno foram extraídos.** Apenas podemos medir o comportamento visível e permitido pelas fontes e pelos snapshots efetivamente recebidos.

## 2. Contrato de dados para o futuro motor NEXUS

Tabela lógica `odds_observadas`, versionada, append-only:

| Campo | Regra de validação |
|---|---|
| `event_id`, `league_id`, `home`, `away`, `kickoff_utc` | Identidade inequívoca; não associar partidas só por nome aproximado |
| `provider`, `bookmaker`, `source_url_or_ref` | Atribuir origem; aceitar book sem autoria identificada apenas como indicativo |
| `market_family`, `raw_market_key`, `period`, `line`, `selection` | Manter o contrato original, sem colapsar FT/1º tempo ou gols por equipe |
| `decimal_odds`, `observed_at_utc`, `provider_updated_at_utc` | Rejeitar valores inválidos, timestamps contraditórios e observações pós-jogo como preço pré-jogo |
| `phase`, `in_play_minute`, `is_suspended`, `capture_status` | Saber se preço é pré-live/live, indisponível ou histórico |
| `verification_state`, `license_or_usage_note` | `verified_quote`, `indicative`, `modelled`, `missing`; nunca misturar |
| `checksum`, `schema_version`, `capture_run_id` | Deduplicar, auditar revisões e reconstruir séries temporais |

Tabela lógica `observacoes_partida`: ID, fase, minuto, placar, cartões/escanteios/chutes reais por equipe, origem, hora, campos ausentes explícitos. Tabela `desfechos`: somente estatísticas finais confirmadas. Tabela `comportamento_de_mercado`: abertura/fechamento observado, variação, overround por linha, disponibilidade e tempo de atraso.

Regras: manter amostra bruta auditável **na extensão permitida pela licença**, snapshots compactados/deduplicados, limites de tamanho, retenção por data e monitoramento de custos; nenhuma credencial ou dado pessoal no Git.

## 3. Fases de desenvolvimento — não confundir com implementação concluída

1. **Acumular base legalmente utilizável:** padronizar odds, mercados, estatísticas, latência e resultados. Construir índice de jogos importantes sem odds e uma cobertura por fonte/mercado. Verificar licenças de armazenamento e reuso/treinamento antes de reaproveitar dados de cada provedor.
2. **Dashboard de referência:** criar painel original NEXUS comparando abertura x último preço, evolução pré-live/live, dados observados e porcentagem dos jogos com mercados efetivos. Documentar recursos de UX observados, sem copiar interface de casa.
3. **Modelos estatísticos próprios:** começar por gols e 1X2 (Poisson/bivariado ou classificação calibrada); depois ambas marcam, handicap, escanteios e cartões **somente** após obter amostras suficientes com estatísticas válidas. Usar dados cronologicamente anteriores a cada evento; treinamento/teste walk-forward, sem vazamento do futuro.
4. **Geração de preço NEXUS:** transformar probabilidades calibradas em **`odds_teoricas_nexus = 1/p`**, com arredondamento e margem **configurável e explicitada**; linhas e regras de liquidação por mercado. Manter etiqueta visível **ODD CALCULADA PELO NEXUS — NÃO É COTAÇÃO DE CASA**.
5. **Camada própria de distribuição:** API para servir calendário, probabilidades, odds teóricas, mudanças, versões do modelo, status da coleta e alertas; cache no GitHub Pages/Cloudflare quando viável. Reavaliar limites de ferramentas gratuitas e armazenamento.
6. **Auditar por meses antes da independência:** erro de probabilidade (log loss/Brier), calibração, desvio em relação ao fechamento observado, cobertura real por liga/mercado, proporção de jogos sem preço e custo total. Desativar fontes externas de odds **somente após** o motor próprio superar critérios definidos, sem ocultar perda de comparabilidade.

## 4. Limites incontornáveis e proteção do projeto

- Reproduzir uma **plataforma analítica parecida com uma casa** não é se tornar uma operadora que aceita apostas. Apostar com dinheiro real envolve licenças e obrigações específicas.
- Mesmo quando desligarmos fornecedores de **odds**, ainda precisaremos de dados confiáveis de partidas e resultados, próprios ou autorizados de terceiros. Para **odds realmente oferecidas por casas**, sempre haverá dependência dessas casas ou de fontes licenciadas.
- Liquidez real de bolsa em BRL não pode ser estimada de quantidade de ofertas nem derivada de preço. Continuar em `unknown` sem fonte de volume negociado comprovável.
- Não utilizar credenciais de terceiros, simular usuários, contornar CAPTCHA/bloqueios ou copiar conteúdo/dados além das permissões da fonte. Uma API de conta própria só deve ser acessada pelas condições de seu plano.
- Não prometer rentabilidade; qualquer backtest precisa indicar custo, margem, variação, seleção amostral e vieses.
- Toda mudança de produção deve ser testada, manter backup/histórico e evitar alterar fontes aprovadas.

## 5. Checklist quando for autorizado iniciar o motor próprio

- [ ] Revisar a qualidade, licença e cobertura dos arquivos históricos coletados.
- [ ] Normalizar datasets sem unir partidas ou mercados errados.
- [ ] Criar gerador de probabilidades e odds **separado do livro observado**.
- [ ] Validar em períodos futuros, jogos grandes e temporadas diferentes.
- [ ] Construir painel original de qualidade, confiança e drift do modelo.
- [ ] Publicar API NEXUS com dados calculados e rótulos transparentes.
- [ ] Demonstrar redução mensurável de dependência de terceiros.
