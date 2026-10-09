# NEXUS — desenvolvimento com verificações (método inspirado em Superpowers)

Referência: https://github.com/obra/superpowers (MIT). Adaptação das práticas TDD, debugging sistemático, plano e revisão. Isto **não** instala automaticamente a extensão em nenhum agente.

## Fluxo obrigatório para mudanças
1. Descrever claramente o bug/demanda, arquivos afetados, hipótese e critérios de aceitação.
2. Criar testes de regressão específicos antes de corrigir a implementação; identificar a causa raiz.
3. Preferir mudanças pequenas e isoladas; **não** mexer em produção ao testar fontes novas.
4. Executar as verificações antes do push, e novamente no GitHub após o push.
5. Verificar GitHub Actions/Cloudflare, dados reais e ausência de falsos positivos.
6. Se a fonte falhar, registrar `unavailable`; nunca preencher lacunas com odds, xG, gols, scouts ou EV+ imaginados.
7. Alertar se não houver comprovado efeito na cobertura. Odds históricas de fechamento jamais são odds live/entrada.
8. Para coleta concorrente, proteger o histórico e evitar alteração de dados privados da Bolsa de Aposta.
9. Ao entregar, separar comprovadamente: **programado**, **CI passou**, **dados externos chegaram**, **publicação concluída**.

## Comandos de revisão offline
`python -m unittest discover -s tests -v`
`node tests/test_original_enrich.mjs`
`node tests/test_nexus_iara.mjs`

## Experimentos
- SoccerData só em `experiments/soccerdata/` e workflow próprio; não declarar integrado ao NEXUS antes da confirmação da cobertura.
- Não instalar `soccerdata` no coletor de produção nem acrescentar scraping não aprovado automaticamente.
