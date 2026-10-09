# NEXUS PC — importacao auditavel de P/L

O `pc_reader.py` foi adicionado ao NEXUS para registrar exportacoes reais do computador, sempre preservando o nome original do mercado (inclusive BACK/LAY e linhas Over/Under).

- A pasta monitorada e `NEXUS_IMPORT` no diretorio do usuario do Windows.
- Insira um CSV ou JSON exportado pela plataforma com colunas **Mercado**/`market` e **netPl**/`lucro liquido`.
- Executar uma vez no PC: `python pc_reader.py --watch`. Isso vigia a pasta enquanto estiver aberto; nao e um servico remoto.
- Se o PC tiver `git` autenticado com este repositorio privado e quiser sincronizar automaticamente o *resumo* para a web: `python pc_reader.py --watch --push`. O arquivo de operacoes original nao e enviado.
- A interface privada usa `history/pc_netpl.json`, nao `web/data.json`. Nunca mova relatorios brutos para `web/`.

**Limitacoes:** o bot nao acessa arquivos locais do PC desligado ou sem o programa em execucao. A versao estatica do Cloudflare nao le P/L, por privacidade. A area privada requer hospedagem do `web_server.py` com `NEXUS_WEB_PASSWORD` e HTTPS. Para ver o relatorio no site privado hospedado, o agente deve conseguir fazer `git push` para o repositorio e a hospedagem deve atualizar a copia do historico. Em servidores com armazenamento efemero, nao dependa deles como arquivo primario.

**Exatidao:** o importador usa apenas o P/L registrado no relatorio e apresenta media por operacao. Nao converte em unidades quando stakes/risco das entradas nao foram confirmados; nao deduz ROI, EV+ ou rentabilidade a partir do placar. Seleciona apenas o arquivo mais recente para evitar contagem duplicada.
