(() => {
  "use strict";
  const section=document.getElementById("pc-private");
  if(!section)return;
  const el=id=>document.getElementById(id);
  const fmt=new Intl.NumberFormat("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2});
  const date=v=>{
    const d=new Date(v||0);
    return Number.isNaN(d.getTime())?"horario indisponivel":d.toLocaleString("pt-BR",{timeZone:"America/Sao_Paulo"});
  };
  fetch("/api/dashboard",{credentials:"same-origin",cache:"no-store"})
    .then(r=>{if(!r.ok)throw Error("acesso nao autorizado");return r.json()})
    .then(data=>{
      const doc=data.pc_import||{};
      const markets=Array.isArray(doc.markets)?doc.markets:[];
      if(!doc.snapshot_only||!markets.length)return;
      section.hidden=false;
      el("pc-summary").textContent=String(doc.operations||0)+" operacoes importadas · P/L registrado: "+
        fmt.format(doc.net_pl)+" "+String(doc.currency||"")+" · "+
        "Arquivo: "+String(doc.source||"nao informado")+" · "+date(doc.observed_at);
      el("pc-explainer").textContent="Resumo real do arquivo local, sem duplicar com a Bolsa nem converter em unidades. "+
        (Number(doc.rows_rejected||0)>0?String(doc.rows_rejected)+" linhas foram rejeitadas por ausencia de P/L ou mercado.":"Nenhuma linha rejeitada.");
      const table=document.createElement("table");
      table.className="nexus-pc-table";
      const head=document.createElement("tr");
      for(const name of ["Mercado original","Entradas","P/L liquido"]){
        const th=document.createElement("th");th.textContent=name;head.append(th);
      }
      table.append(head);
      for(const market of markets){
        const row=document.createElement("tr");
        for(const value of [market.market,market.operations,fmt.format(market.net_pl)+" "+doc.currency]){
          const td=document.createElement("td");td.textContent=String(value??"—");row.append(td);
        }
        row.lastElementChild.className=Number(market.net_pl)>=0?"pl-positive":"pl-negative";
        table.append(row);
      }
      el("pc-markets").replaceChildren(table);
    })
    .catch(()=>{section.hidden=true});
})();
