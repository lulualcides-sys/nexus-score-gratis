/* NEXUS 5.32 — explicação, auditoria e frescor dos dados esportivos. */
(function(root){
'use strict';
const html=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const numeric=x=>x===null||x===undefined||x===''?null:Number.isFinite(+x)?+x:null;
const time=x=>{const d=new Date(x);return Number.isNaN(d.getTime())?'não confirmado':
 d.toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})};
const pickNames={
 '1x2':{home:'Vitória do mandante',draw:'Empate',away:'Vitória do visitante'},
 double_chance:{'1X':'Mandante ou empate','X2':'Visitante ou empate','12':'Um dos times vence'},
 over_under_25:{over:'Mais de 2,5 gols',under:'Menos de 2,5 gols'},
 btts:{yes:'Ambas marcam — SIM',no:'Ambas marcam — NÃO'}
};
function freshness(g,now=Date.now()){
 const live=g?.phase==='live'||g?.live===true;
 const t=Date.parse(g?.observed_at||''),pt=Date.parse(g?.pressure_observed_at||'');
 const minutes=numeric(g?.minute);
 const points=g?.thermometer?.points||g?.pressure||[];
 const last=Array.isArray(points)?Math.max(0,...points.map(p=>numeric(p?.minute??p?.m)||0)):0;
 const age=Number.isFinite(t)?Math.max(0,(now-t)/60000):null;
 const pressureAge=Number.isFinite(pt)?Math.max(0,(now-pt)/60000):null;
 const gap=minutes!==null&&last>0?Math.max(0,minutes-last):null;
 const pressureFresh=live&&last>0&&gap!==null&&gap<=5&&pressureAge!==null&&pressureAge<=12&&age!==null&&age<=12;
 return {live,age,pressureAge,gameMinute:minutes,lastPressureMinute:last,pressureGap:gap,
  pressureFresh,
  label:!live?'Partida fora de tempo real':age===null?'Horário da coleta desconhecido':
        age>12?'PLACAR / SNAPSHOT ATRASADO':!last?'SEM CURVA DE PRESSÃO':
        !pressureFresh?'CURVA DE PRESSÃO ATRASADA':'CURVA RECENTE'};
}
function freshnessHTML(g){
 if(g?.phase!=='live')return '';
 const f=freshness(g);
 const fmt=n=>n===null?'sem confirmação':Math.round(n)+' min';
 const tone=f.pressureFresh?'nexus-fresh-ok':'nexus-fresh-late';
 return '<section class="nexus-audit-fresh '+tone+'" aria-label="Frescor dos dados ao vivo">'+
  '<strong>'+html(f.label)+'</strong>'+
  '<span>Placar: '+html(fmt(f.age))+' desde a coleta · Pressão: '+html(f.lastPressureMinute?f.lastPressureMinute+"′":'sem leitura')+
  ' · Atraso da curva: '+html(f.pressureGap===null?'desconhecido':f.pressureGap+' min')+
  ' · Última coleta de pressão: '+html(fmt(f.pressureAge))+'</span>'+
  '<small>Sem pressão recente, o NEXUS não emite alerta de gol próximo nem EV+ ao vivo.</small></section>';
}
function status(b){
 const odd=b?.odds,p=b?.model_ev;
 if(!b)return {name:'SEM PRÉ-LIVE REGISTRADO',description:'Nenhuma previsão foi congelada antes do início deste jogo.',tone:'missing'};
 if(!odd)return {name:'EV INDISPONÍVEL',description:'Há projeção esportiva, mas não foi salvo trio 1/X/2 de odds pré-jogo verificadas. Não classificar como bom ou ruim para entrada.',tone:'missing'};
 if(!odd.recent_at_check)return {name:'ODD ANTIGA · EV INDISPONÍVEL',description:'A cotação foi registrada antes do jogo, mas estava velha na conferência. Não representa odd atual nem preço de entrada.',tone:'missing'};
 if(!p||!Number.isFinite(+p.ev_pct))return {name:'EV INDISPONÍVEL',description:'Modelo e odds não formaram cálculo completo.',tone:'missing'};
 const positive=Number(p.ev_pct)>0;
 return {name:positive?'EV TEÓRICO POSITIVO · NÃO VALIDADO':'EV TEÓRICO NÃO POSITIVO',
  description:(positive?'O preço superou o valor estimado pelo modelo.':'O preço não superou o valor estimado pelo modelo.')+
  ' Modelo Poisson não calibrado; isto NÃO confirma vantagem real ou rentabilidade.',
  tone:positive?'theory':'missing'};
}
function report(b,g){
 if(!b?.forecast?.one_x_two)return '<section class="nexus-audit-card"><h3>Pré-live anterior ao jogo</h3><p>Não existe análise congelada antes do início. Não usar simulação posterior como previsão passada.</p></section>';
 const state=status(b),sett=b.settlement||null;
 const map=new Map((sett?.checks||[]).map(x=>[x.market+'|'+x.selection,x.result]));
 const picks=(b.indications||[]).slice(0,4).map((p,i)=>{
  const hit=map.get(p.market+'|'+p.selection);
  const outcome=hit==='hit'?'✓ ACERTOU':hit==='miss'?'✕ ERROU':g?.phase==='finished'?'NÃO VERIFICADO':'AGUARDANDO';
  return '<div class="nexus-audit-row"><b>'+(i+1)+'. '+html(pickNames[p.market]?.[p.selection]||p.selection)+'</b>'+
  '<span>'+html(p.probability)+'% · '+html(p.market)+'</span>'+
  '<strong class="'+(hit==='hit'?'pass':hit==='miss'?'fail':'pending')+'">'+html(outcome)+'</strong></div>';
 }).join('');
 const odds=b.odds;
 const price=odds?.prices||{},ev=b.model_ev;
 const prices=odds?'<p class="nexus-audit-meta">Odds 1/X/2 verificadas: '+html(price.home)+' / '+html(price.draw)+' / '+html(price.away)+
   ' · '+html(odds.source)+' / '+html(odds.bookmaker)+' · capturadas '+html(time(odds.captured_at))+'</p>':
  '<p class="nexus-audit-meta">Nenhuma odd 1/X/2 simultânea foi capturada antes do início.</p>';
 return '<section class="nexus-audit-card" aria-label="Pré-live congelado e verificação posterior">'+
  '<header><div><h3>◉ PRÉ-LIVE QUE FICOU SALVO</h3><small>Registrado '+html(time(b.captured_at))+' · '+html(b.model)+'</small></div>'+
  '<span class="nexus-audit-status">'+html(state.name)+'</span></header>'+
  '<p class="nexus-audit-explain">'+html(state.description)+'</p>'+
  '<div class="nexus-audit-grid">'+picks+'</div>'+prices+
  (ev?'<p class="nexus-audit-meta">EV somente matemático '+html(ev.ev_pct)+'% · '+html(ev.selection)+' @ '+html(ev.odd)+'; não é EV comprovado nem operação realizada.</p>':'')+
  (sett?'<p class="nexus-audit-finish"><b>Conferência após o final:</b> '+html(sett.score)+
    ' · '+html(sett.hits)+' de '+html(sett.count)+' cenários bateram. Mercados correlacionados; não representam apostas, retorno nem calibração.</p>':
    '<p class="nexus-audit-finish">Resultado ainda não verificado. A comparação permanece pendente até o placar final confirmado.</p>')+
  '</section>';
}
function archive(rows,limit=120){
 const records=Array.isArray(rows)?rows.slice(0,limit):[];
 if(!records.length)return '<div class="lab-empty"><strong>Histórico pré-live ainda vazio</strong><p>Somente previsões realmente capturadas antes do início entrarão aqui. Jogos antigos sem captura NÃO serão inventados.</p></div>';
 let frozen=0,settled=0,hits=0,decisions=0,odds=0;
 for(const r of records){if(!r.pregame_baseline)continue;frozen++;
  if(r.pregame_baseline.odds)odds++;
  if(r.pregame_baseline.settlement){settled++;hits+=Number(r.pregame_baseline.settlement.hits||0);decisions+=Number(r.pregame_baseline.settlement.count||0);}
 }
 const list=records.map(r=>{
  const b=r.pregame_baseline||{},set=b.settlement;
  return '<details class="nexus-audit-archive-row"><summary><b>'+html(r.home)+' × '+html(r.away)+'</b>'+
   '<small>'+html(r.day)+' · '+html(r.league)+'</small><strong>'+
   (set?html(set.hits)+'/'+html(set.count)+' cenários':'Pendente')+'</strong></summary>'+report(b,r)+'</details>';
 }).join('');
 return '<div class="nexus-audit-archive"><h3>Memória pré-live congelada · até 90 dias</h3>'+
 '<p>Previsões capturadas: '+frozen+' · Jogos avaliados: '+settled+' · Cenários certos: '+
 hits+'/'+decisions+' · com cotações pré-jogo registradas: '+odds+'. Não é ROI, não significa EV+.</p>'+
 list+'</div>';
}
root.NexusAudit={freshness,freshnessHTML,status,report,archive};
if(typeof module!=='undefined'&&module.exports)module.exports=root.NexusAudit;
})(typeof window!=='undefined'?window:globalThis);
