# Laboratório NEXUS Gol 30–70

**Separado do coletor e do indicador público.** Não modifica modelos aprovados,
odds, entradas, alertas nem `history`.

## Executar no GitHub

O workflow `.github/workflows/nexus-goal3070-lab.yml` instala DuckDB,
scikit-learn e CatBoost somente no job de pesquisa, e entrega JSON em artefato.
Também pode executar manualmente pelo GitHub Actions.

O comando é:

```bash
python -m pip install -r research/goal_30_70_lab/requirements.txt
python -m research.goal_30_70_lab.run --journal history/signal_registry.json --output artifacts/goal3070-lab-report.json
```

## Auditoria

Uma observação (primeiro alerta 30–70) por partida; alvo = gol 15 minutos
depois do sinal. Apenas registros com resultados verificáveis entram no
treinamento; conflitos e desconhecidos ficam em contagem separada.
Treino e holdout são separados por **dia** e não por alertas aleatórios.
Os modelos são: taxa histórica base, NEXUS atual, regressão logística
regularizada, CatBoost raso e modelo de risco discreto em intervalos de 5
minutos. O hazard usa minuto exato verificado do gol; observações com gol
sem minuto documentado são descartadas especificamente para o treinamento
do hazard.

O resultado detalha Brier, AUC, log loss, calibração, confiança por
bootstrap de dia e comparações cronológicas. Nenhum ganho no backtest
autoriza publicação automática de percentual ou aposta. Antes de promover
modelo, exige-se teste prospectivo congelado em datas futuras.

O pipeline de produção mantém **zero dependências de ML**. Sem licença de
dados e sem credenciais Cloudflare, não ativar polling agressivo de provedores.
