# NEXUS Live: termômetro ao vivo a cada 2 minutos

Worker da Cloudflare (plano grátis) que, a cada 2 minutos, lê os jogos ao vivo no FotMob e guarda a pressão por minuto e os scouts **publicados pela fonte** no KV `nexus-live`. O site (`web/nexus-live.js`) consulta `/live` a cada minuto nos jogos ao vivo.

- Sem a URL em `web/live-config.json`, o site funciona como antes.
- Jogos sem `momentum` na fonte continuam sem curva (`momentum_state: not_provided`). Nada é inventado.
- Dado com mais de 15 minutos não é tratado como ao vivo.
- Limites do plano grátis: 720 gravações por dia no KV (limite 1.000) e até 40 detalhes por execução (limite 50 subrequests).

## Ativação (uma vez)
1. Cloudflare → **My Profile → API Tokens → Create Token → modelo "Edit Cloudflare Workers"** → criar e copiar.
2. Cloudflare → página inicial da conta → copiar o **Account ID**.
3. GitHub → Settings → Secrets and variables → Actions → criar `CLOUDFLARE_API_TOKEN` e `CLOUDFLARE_ACCOUNT_ID`.
4. GitHub → Actions → "NEXUS Live — publicar Worker Cloudflare" → **Run workflow**.

O workflow cria o KV, publica o Worker, testa `/live` e grava a URL em `web/live-config.json`. Depois disso, o Cloudflare Pages republica o site já ligado ao Worker.
