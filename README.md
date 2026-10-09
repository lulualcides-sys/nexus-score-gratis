# NEXUS SCORE — coletor gratuito

Coleta horária de partidas públicas e pressão (quando a fonte fornece), sem cartão e sem computador ligado. O GitHub Actions grava arquivos em `history/` no repositório privado.

**Limitações:** não hospeda a interface NEXUS, não é monitoramento minuto a minuto nem garante execução no horário exato. Pode haver bloqueio dos provedores ou limites do GitHub Free. Não gera odds nem probabilidades artificiais.

O workflow em `.github/workflows/nexus-gratis.yml` permite acionamento manual e agenda a cada hora. Acompanhe a execução pela aba Actions e o histórico em `history/status.json`.
