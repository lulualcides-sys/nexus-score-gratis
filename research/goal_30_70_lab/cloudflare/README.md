# Cloudflare Workers: piloto desativado até autorização

O cron está preparado para **3 minutos**, mas **não está implantado**: esta conversa não
dispõe de integração Cloudflare Workers/D1 nem de uma fonte de scouts com direito
de coleta nesta frequência.

A infraestrutura precisa de:
1. Conta/credenciais Cloudflare autorizadas;
2. D1 criado e migração SQL aplicada;
3. URL e host de provedor autorizado com timestamps reais de 3 minutos;
4. Testes de limite, custos, latência, duplicação e concorrência antes de produção.

O Worker rejeita partidas fora dos minutos 30–70, fontes atrasadas, campos
inventados, competições femininas e ligas que não sejam principais. Não faz
apostas nem cria probabilidades. Repositório principal e bot Telegram permanecem
intactos.

**Não usar o atual `web/data.json` com atualização horária para fingir
coleta a cada 3 minutos**: isso só repetiria dados desatualizados.
