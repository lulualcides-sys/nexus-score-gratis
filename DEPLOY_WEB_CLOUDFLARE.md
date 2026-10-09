# NEXUS SCORE WEB — publicação gratuita Cloudflare Pages

O site está pronto em `web/index.html`, `web/style.css`, `web/app.js` e `web/data.json`. Não precisa instalar NEXUS no PC para abrir a versão web.

## Publicar pelo celular (uma vez)

1. Abra https://dash.cloudflare.com/sign-up e crie/entre na conta gratuita. Não ative Workers Paid nem forneça cartão.
2. No painel, entre em **Workers & Pages** → **Create application** → **Pages** → **Import an existing Git repository**. Autorize GitHub para **apenas** `lulualcides-sys/nexus-score-gratis`.
3. Escolha repositório `lulualcides-sys/nexus-score-gratis`; nome do projeto, por exemplo, `nexus-score-web`; branch `main`.
4. Configure:
    - Framework: **None** (ou HTML estático).
    - Build command: `exit 0`
    - Build output directory: `web`
    - Variáveis de ambiente: **nenhuma**.
5. Clique em **Save and Deploy / Deploy site**. Espere o Cloudflare exibir a URL `https://<nome>.pages.dev`. Use **a URL REAL mostrada**; ainda não há endereço publicado confirmado.
6. MUITO IMPORTANTE: em **Settings → Build → Build watch paths**, remova o Include padrão `*` e coloque **`web/*`**. Assim apenas mudanças na pasta web disparam novos builds e a atualização de duas em duas horas não consome mais de 500 builds/mês.

## Segurança e limites

- O repositório **é privado** e deve continuar privado. A Cloudflare poderá ler o código para construir o site.
- **O SITE PUBLICADO É PÚBLICO.** O exportador publica somente partidas, placares, estatísticas, pressão e odds públicas. **Não** publica operações da Bolsa, valores de lucro, bots ou previsões de EV+.
- A coleta interna do GitHub segue horária, mas o snapshot **público do painel é atualizado a cada 2 horas**, sujeito ao agendamento e à fonte. É histórico, **não um terminal de trades ao vivo**.
- A aba completa do NEXUS 5.29, a auditoria avançada e o P/L real continuam acessíveis na instalação local ou no repositório privado do GitHub — **não fazem parte desta interface pública**.
- Se a fonte não trouxer pressão ou odd, o painel informa ausência de dados.
- Não coloque tokens, senhas ou credenciais no código da web nem nas variáveis do site.

Ver dados antes de publicar: [snapshot privado](web/data.json) e [workflow](.github/workflows/nexus-gratis.yml).

Links oficiais: https://developers.cloudflare.com/pages/framework-guides/deploy-anything/ e https://developers.cloudflare.com/pages/configuration/build-watch-paths/
