/* NEXUS: unidades PAPER auditadas, separadas do P/L financeiro privado.
 * Compatível com painel original e versão Web (snapshot público).
 */
(function(root){
  "use strict";
  const finite=x=>x!==null&&x!==undefined&&x!==''&&Number.isFinite(Number(x))?Number(x):null;
  const formatted=(n,signed=false)=>{
    const v=finite(n);
    if(v===null)return '—';
    return (signed&&v>0?'+':'')+v.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})+'u';
  };
  function normalize(doc){
    const x=doc&&typeof doc==='object'?doc:{};
    const count=Math.max(0,Math.floor(finite(x.settled)||0));
    const profit=finite(x.profit_u),loss=finite(x.loss_u),net=finite(x.paper_pl_u);
    if(!count||x.status!=='with_settlements'||profit===null||loss===null||net===null)
      return {available:false,settled:count,pending:Math.max(0,Math.floor(finite(x.pending)||0)),markets:[]};
    const markets=(Array.isArray(x.markets)?x.markets:[]).filter(m=>
      typeof m.market==='string'&&finite(m.paper_pl_u)!==null);
    return {available:true,settled:count,pending:Math.max(0,Math.floor(finite(x.pending)||0)),
      wins:Math.max(0,Math.floor(finite(x.won)||0)),
      losses:Math.max(0,Math.floor(finite(x.lost)||0)),
      profit,loss,net,roi:finite(x.roi_pct),markets};
  }
  const escapeHTML=str=>String(str??'').replace(/[&<>"']/g,c=>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function render(doc,updated){
    const anchor=document.getElementById('cloud-audit')||document.getElementById('paper-pnl');
    if(!anchor)return;
    let panel=document.getElementById('nexus-units-paper');
    if(!panel){
      panel=document.createElement('section');panel.id='nexus-units-paper';panel.className='nexus-units-paper';
      if(anchor.id==='cloud-audit')anchor.insertAdjacentElement('afterend',panel);
      else anchor.parentElement.appendChild(panel);
    }
    const a=normalize(doc);
    const ago=updated?new Date(updated):null;
    const stamp=ago&&!Number.isNaN(ago.getTime())?ago.toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'}):'sem data';
    if(!a.available){
      panel.innerHTML='<h3>Resultado em unidades · NEXUS paper</h3>'+
       '<p>Sem apostas experimentais liquidadas com odds de entrada verificadas. Lucro e perdas ainda indisponíveis (—), não 0u.</p>'+
       '<small>Snapshot: '+escapeHTML(stamp)+' · Sinais pendentes: '+a.pending+'</small>';
      return;
    }
    const metric=(heading,value,cls='')=>'<div class="nexus-unit-metric '+cls+'"><small>'+heading+'</small><b>'+value+'</b></div>';
    const list=a.markets.map(m=>'<tr><td>'+escapeHTML(m.market==='1x2'?'Match Odds 1X2':m.market)+
      '</td><td>'+Number(m.entries||0)+'</td><td>'+Number(m.wins||0)+' / '+Number(m.losses||0)+'</td>'+
      '<td class="pl-positive">'+formatted(m.profit_u,true)+'</td><td class="pl-negative">-'+formatted(m.loss_u)+'</td>'+
      '<td class="'+(Number(m.paper_pl_u)>=0?'pl-positive':'pl-negative')+'">'+formatted(m.paper_pl_u,true)+'</td></tr>').join('');
    panel.innerHTML='<h3>Resultado em unidades · NEXUS paper</h3>'+
      '<div class="nexus-unit-grid">'+
      metric('LUCRO BRUTO',formatted(a.profit,true),'pl-positive')+
      metric('PERDAS', '-'+formatted(a.loss),'pl-negative')+
      metric('LÍQUIDO',formatted(a.net,true),a.net>=0?'pl-positive':'pl-negative')+
      metric('ROI POR 1u ARRISCADA',a.roi===null?'—':a.roi.toLocaleString('pt-BR',{maximumFractionDigits:2})+'%')+
      '</div><p>'+a.settled+' sinais liquidados · '+a.wins+' ganhos · '+a.losses+' perdas · '+a.pending+' pendentes</p>'+
      (list?'<div class="nexus-unit-scroll"><table><thead><tr><th>Mercado</th><th>Entradas</th><th>V / D</th><th>Lucro</th><th>Perdas</th><th>Líquido</th></tr></thead><tbody>'+list+'</tbody></table></div>':'')+
      '<small>1u por sinal BACK previamente registrado, antes do início. Teste sem taxas; não é lucro real na Bolsa. Snapshot: '+escapeHTML(stamp)+'</small>';
  }
  async function refresh(){
    if(typeof document==='undefined'||typeof fetch!=='function')return;
    const anchor=document.getElementById('cloud-audit')||document.getElementById('paper-pnl');
    if(!anchor)return;
    try{
      const response=await fetch('./data.json',{cache:'no-store'});
      if(!response.ok)throw new Error('sem snapshot');
      const data=await response.json();
      render(data.paper,data.exported_at);
    }catch(_){
      render({},null);
    }
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={normalize,formatted,escapeHTML};
  if(typeof document!=='undefined'){
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',refresh);
    else refresh();
  }
})(typeof window!=='undefined'?window:globalThis);
