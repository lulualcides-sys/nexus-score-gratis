# NEXUS — padrão permanente: motor independente, qualidade antes de cobertura

**Revisão da diretriz:** 25/10/2026. **Estado:** SOMENTE ESTUDO; não autoriza novos patches do motor.
**Vinculação:** complementa `NEXUS_MOTOR_PROPRIO_ODDS_ROADMAP.md` e é referenciado por `AGENTS.md`.

## 1. Padrão de longo prazo aprovado pelo proprietário

1. Prioridade máxima para um **motor próprio, livre e auditável**, capaz de estimar probabilidades e odds justas usando cálculos estatísticos e dados históricos confiáveis. Eliminar, sempre que tecnicamente possível, a dependência de serviços de **odds** de terceiros.
2. Só trabalhar com os mercados principais solicitados: **1X2 FT, 1X2 HT, HT/FT, dupla chance FT, BTTS FT/HT, Over/Under de gols FT/HT, gols por equipe FT e placar exato FT**. **Fora do escopo do motor próprio: handicaps, cartões, escanteios e jogadores**; não adicioná-los sem solicitação explícita. Outros coletores já existentes devem ser preservados até ordem contrária.
3. **Precisão acima da quantidade.** Não forçar previsão para clubes, ligas ou intervalos sem base suficiente. Uma probabilidade com baixa amostra não equivale a confiança e não deve ser tratada como recomendação.
4. **Sem assinatura nem serviço pago como dependência obrigatória.** Preferir histórico próprio e bases redistribuíveis CC0. O objetivo viável é produzir probabilidades localmente, mesmo sem fornecedor externo de odds. Para jogos **novos**, sempre será necessário algum registro atualizado do calendário e dos placares, salvo coleta manual/autônoma legítima; independência absoluta de toda origem de dados não é tecnicamente garantida.
5. **Separação de identidade:** `odds_justas_modelo` e probabilidades NEXUS nunca se tornam `odd_bookmaker_verificada`; não atribuir EV, ROI, lucro ou liquidez negociada fictícios.
6. **Este turno autoriza somente análise e documentação.** Não atualizar algoritmo, programação, interface, chaves, notificações ou automações para "melhorar" algo por conta própria. O desenvolvimento futuro exigirá pedido para implementá-lo e testes de regressão.

## 2. Foto factual da versão atual, não uma meta de desempenho

Última versão auditada nos dados do GitHub do projeto:
- `telegram_collector/model_only.py`: `nexus-poisson-segmented-1.0`; Poisson com forças ataque/defesa suavizadas, vantagem do mandante por liga, decaimento histórico e proporção de gols para o intervalo.
- Histórico elegível após filtrar competições ambíguas: **627** jogos; agenda prioritária com **10** jogos futuros, dos quais **5** receberam odds teóricas e **5** foram recusados por dados insuficientes. Valores de uma execução, sujeitos a mudança.
- `telegram_collector/model_backtest.py`: amostra retrospectiva **50 jogos em 6 ligas**, **Brier multiclasses 1X2 = 0,69680**, **RPS = 0,25597**. **Cuidado:** um preditor constante de 1/3 para cada resultado tem Brier multiclasses 2/3 ≈ **0,66667** em qualquer jogo; a amostra atual está **pior que esse referencial ingênuo**. As ligas, os confrontos e o tamanho amostral não permitem concluir que o modelo tenha habilidade preditiva comprovada ou lucro.
- A medição atual precisa também de **baseline específico por liga, mercado e período**, validação prospectiva de previsões congeladas e intervalos de incerteza. Não comunicar métricas como certificação de precisão.

## 3. Pesquisa matemática — testar hipóteses, não importar automaticamente

### Prioridade A — base, identificações e incerteza

- Ampliar o histórico de **várias temporadas**, de forma legal, com versão, licença, data, ID canônico do clube, competição, mandante, visitante, FT, HT e data de encerramento **comprovada**. Examinar `openfootball/football.json` e `openfootball/south-america` (CC0) para Europa, Brasil, Argentina e outras ligas, verificando **cobertura efetiva** de cada temporada. Rejeitar jogos sem escore confirmado e placeholders `[0,0]`.
- Deduplicar por ID de partida, competição, mandante/visitante e horário; resolver apelidos/equipes promovidas sem juntar clubes homônimos. Auditar se existe **múltipla entrada da mesma partida em calendários e snapshots**.
- Separar treinos FT e HT conforme informação realmente observada. Caso o HT não exista, **não disfarçar uma média entre ligas como evidência local**; mostrar confiança inferior ou omitir aquele mercado.
- Medir variação de resultados ao longo da temporada, mando, mudanças de liga/promovidos e obsolescência; não aumentar a confiança com jogos antigos só para preencher lacunas.

### Prioridade B — candidatos de modelos independentes

1. **Baseline Poisson atual**, para comparação e teste de sensibilidade de meia-vida, shrinkage e mínimo efetivo de jogos; rejeitar ajuste "na sensação".
2. **Poisson por máxima verossimilhança + Dixon–Coles (ρ/τ)**, com pesos temporais e correção de 0–0/1–0/0–1/1–1, restrições de parâmetros que garantam probabilidades não negativas e normalização da matriz. Principal candidato para melhorar **empate/placar exato**. Não afirmar que é melhor antes de comparar erros fora da amostra.
3. **Bivariado Poisson ou dinâmica de força por equipe**: considerar só se estatística robusta e dados suficientes; parâmetros extras aumentam risco de overfitting. Calibrar HT/FT respeitando a dependência entre os tempos.
4. **Hierárquico bayesiano / partial pooling** para promovidos e clubes pouco observados; prior de liga explícito, intervalo de incerteza em cada previsão. Considerar custo computacional em GitHub Actions gratuito.
5. **Rating Elo de gols / ensemble pequeno** somente se superar, em dados futuros isolados, uma versão simples. Não somar vários modelos correlacionados por promessa de precisão.
6. **Pós-calibração** (isotônica/Platt/Dirichlet ou equivalente) apenas com janela própria de treino, nunca usando o período de avaliação; validar por mercado e por faixas de favoritismo.

### Prioridade C — consistência e validação

- Construir, congelar e versionar a **mesma distribuição conjunta de placares de HT e FT**; derivar todos os mercados do mesmo livro probabilístico. Checagens: 1X2 FT/HT soma 1; HT/FT soma 1 e tem as marginais corretas; Over/Under e Sim/Não somam 1; FT Over 2.5 não pode ser menor que HT Over 2.5; odds justas = 1/p; probabilidades jamais negativas.
- Medir truncamento da distribuição de gols e o erro residual, em vez de renormalizar excessivamente a cauda e criar desvios ocultos.
- **Walk-forward por temporada/data**, avaliação fora da amostra, sem placares futuros, sem ajuste de hiperparâmetros na janela de teste. Registrar prévias imutáveis antes dos jogos e avaliá-las após o término. Testes de "corrupção do futuro" devem garantir previsões anteriores invariantes.
- Comparar, no **mesmo conjunto de jogos**, Brier 1X2, RPS 1X2, log loss, Brier BTTS e Over/Under, além de calibração por faixa de probabilidade, por liga, jogo importante, HT/FT e time com baixo histórico. Usar **baselines** de 1/3, frequência histórica da liga, Poisson atual e modelos alternativos, com intervalo de incerteza/bootstrap.
- Definir critérios prospectivos para sair do rótulo **experimental**, com quantidade de jogos, estabilidade por liga e melhora consistente fora da amostra. 50 jogos isolados são insuficientes; não declarar número exato de partidas como prova automática.
- Colocar o motor em **shadow mode** enquanto valida: paralelo aos coletores, mas sem modificar suas odds reais, o Telegram ou robôs financeiros.

## 4. Bibliografia verificável

- Mark Dixon e Stuart Coles (1997), *Modelling Association Football Scores and Inefficiencies in the Football Betting Market*, JRSS C. DOI: https://doi.org/10.1111/1467-9876.00065
- Koopman e Lit (2015), *A dynamic bivariate Poisson model for analysing and forecasting match results in the English Premier League*: https://doi.org/10.1111/rssa.12042
- Bayes hierárquico, Baio e Blangiardo (2010): https://doi.org/10.1080/02664760802684177
- Implementações para estudar, **sem importar código automaticamente**: https://github.com/jpmouracodex/football-mle (MIT) ; https://github.com/callumfm/dixon-coles (MIT)
- Modelos e limitações: https://penaltyblog.readthedocs.io/en/latest/models/overview.html
- Dados públicos CC0: https://github.com/openfootball/football.json e https://github.com/openfootball/south-america
- Exemplo de comparação honesta modelo vs mercado: https://github.com/Charliedrakebro/dixon-coles-football-model — inclui comparação temporal, mas **desempenho de terceiros não transfere para NEXUS**.

## 5. Política de trabalhos futuros

Ordem sugerida **somente quando o usuário autorizar implementar**:
**auditoria de dados e licenças → baseline reproduzível → candidatos estatísticos separados → walk-forward e calibração → publicação experimental com confiança/abstenção → monitoramento prospectivo prolongado → promoção somente com evidência.**

**Nada deste documento dispara código, scraping, login, deploy, alteração de avisos ou promessa de acompanhamento em segundo plano.**