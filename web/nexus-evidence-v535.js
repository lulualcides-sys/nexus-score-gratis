/* NEXUS 5.35 — evidências esportivas e registro de odds ≠ operações financeiras.
 * Não produz stake, aposta, P/L de Bolsa, odds ausentes ou resultados fictícios.
 */
(function(root){
"use strict";
const h=x=>String(x??'—').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[ch]));
const num=x=>x===null||x===undefined||x===''||typeof x==='boolean'||!Number.isFinite(Number(x))?null:Number(x);
const count=x=>Math.max(0,Math.floor(num(x)||0)).toLocaleString('pt-BR');
const pct=x=>num(x)===null?'—':num(x).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%';
const brl=x=>num(x)===null?'—':num(x).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const label={gol_confirmado:'✓ Gol confirmado',
 sem_gol_confirmado:'✕ Sem gol confirmado',
 pendente:'… Pendente',indeterminado:'? Indeterminado',
 janela_incompleta:'◷ Janela incompleta'};
const tone={gol_confirmado:'yes',sem_gol_confirmado:'no',
 pendente:'pending',indeterminado:'unknown',janela_incompleta:'unknown'};
function auditHTML(report){
 const d=report&&typeof report==='object'?report:{};
 const evidence=d.market_evidence&&typeof d.market_evidence==='object'?d.market_evidence:null;
 const markets=Array.isArray(evidence?.markets)?evidence.markets:[];
 const paperCount=num(d.settled_paper)||0;
 const paper=paperCount>0&&num(d.paper_profit_loss_brl)!==null?brl(d.paper_profit_loss_brl):'—';
 const kpi=(name,value,note)=>'<div><small>'+h(name)+'</small><b>'+h(value)+'</b>'+
  (note?'<span>'+h(note)+'</span>':'')+'</div>';
 const table=markets.length?
 '<div class="nexus-evidence-scroll"><table><thead><tr><th>Mercado</th>'+
 '<th>Pré-live salvo</th><th>Com odd prévia íntegra</th><th>Desfechos conferidos</th>'+
 '<th>Acertos</th><th>Erros</th><th>Taxa observada</th>'+
 '<th>EV teórico positivo*</th></tr></thead><tbody>'+
 markets.map(m=>'<tr><th>'+h(m.label||m.market)+'</th>'+
 '<td>'+count(m.forecasts)+'</td><td>'+count(m.with_price)+'</td>'+
 '<td>'+count(m.settled)+'</td><td>'+count(m.hits)+'</td>'+
 '<td>'+count(m.misses)+'</td><td>'+pct(m.observed_hit_pct)+'</td>'+
 '<td>'+count(m.theoretical_positive)+'</td></tr>').join('')+
 '</tbody></table></div>':
 '<p class="nexus-evidence-await">A análise por mercado ainda não foi gerada pela coleta. As odds e o histórico anterior permanecem intactos.</p>';
 return '<div class="cloud-audit-head"><h3>Auditoria esportiva por mercado · NEXUS</h3>'+
 '<small>Contagem de dados reais registrados, não de apostas realizadas.</small></div>'+
 '<div class="cloud-audit-stats">'+
 kpi('COTAÇÕES BRUTAS',count(d.quotes_registered),'Podem existir três ou mais preços por partida')+
 kpi('PARTIDAS COM PRÉ-LIVE CONGELADO',evidence?count(evidence.fixtures_with_frozen_forecast):'—','Não reconstruídas após o início')+
 kpi('PARTIDAS COM DESFECHO ESPORTIVO',evidence?count(evidence.fixtures_with_result):'—','Conferência de previsões por mercado')+
 kpi('P/L PAPER AUDITADO',paper,paperCount?''+paperCount+' entradas hipotéticas previamente registradas':'Nenhuma entrada paper liquidada; valor indisponível')+
 '</div>'+
 '<p class="nexus-evidence-explain"><b>Os '+count(d.quotes_registered)+' preços brutos NÃO representam '+count(d.quotes_registered)+' operações.</b> '+
 'A conferência esportiva e o P/L paper são separados das operações reais. Sem entrada prévia, odd e liquidação, o resultado financeiro fica indisponível (—).</p>'+
 table+
 '<p class="nexus-evidence-foot">*EV matemático positivo só quando previsão congelada e odd 1X2 íntegra anterior ao jogo. '+
 'Modelo experimental ainda não calibrado; isso não comprova vantagem real, não indica operação executada e não gera lucro.</p>'+
 '<p class="nexus-evidence-foot">Execuções financeiras: <b>não conectadas nesta auditoria pública</b>. '+
 'O extrato privado da Bolsa de Aposta é independente e jamais é atribuído aos sinais do NEXUS.</p>';
}
function normalizeSummary(evaluation,journal){
 const e=evaluation&&typeof evaluation==='object'?evaluation:{};
 const slots={};
 for(const n of ['5','10','15']){
  const v=e.horizons?.[n]||null;
  if(v&&num(v.observations)!==null){
   slots[n]={observations:Math.max(0,num(v.observations)),settled:Math.max(0,num(v.settled)||0),
    hits:Math.max(0,num(v.hits)||0),misses:Math.max(0,num(v.misses)||0),
    pending:Math.max(0,num(v.pending)||0),unknown:Math.max(0,num(v.unknown)||0),
    incomplete:Math.max(0,num(v.incomplete)||0),rate_pct:num(v.rate_pct)};
  }else{
   // Fallback no mesmo registro verificável da nuvem, sem criar vencedores.
   const dedup=new Set(),raw=Array.isArray(journal?.items)?journal.items:[];
   const clean=raw.filter(x=>x&&x.id&&!dedup.has(x.id)&&dedup.add(x.id));
   const results=clean.map(x=>x.outcome_conflict?'indeterminado':x.outcomes?.[n]||'pendente');
   const hits=results.filter(s=>s==='gol_confirmado').length;
   const misses=results.filter(s=>s==='sem_gol_confirmado').length;
   slots[n]={observations:results.length,settled:hits+misses,hits,misses,
    pending:results.filter(s=>s==='pendente').length,
    unknown:results.filter(s=>s==='indeterminado').length,
    incomplete:results.filter(s=>s==='janela_incompleta').length,
    rate_pct:hits+misses?Math.round(hits/(hits+misses)*1000)/10:null};
  }
 }
 return slots;
}
function uncertainty(hits,total){
 // Intervalo Wilson 95% para ocorrências observadas, não probabilidade futura.
 const n=num(total),k=num(hits);if(n===null||k===null||n<=0||k<0||k>n)return null;
 const z=1.96,p=k/n,d=1+z*z/n;
 const mid=(p+z*z/(2*n))/d,half=z*Math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;
 return {low:Math.max(0,Math.round((mid-half)*1000)/10),
         high:Math.min(100,Math.round((mid+half)*1000)/10)};
}
function calibrationHTML(evaluation){
 const e=evaluation&&typeof evaluation==='object'?evaluation:{};
 const bySignal=Array.isArray(e.views?.['10']?.by_signal)?
  e.views['10'].by_signal:Array.isArray(e.by_signal)?e.by_signal:[];
 const byBand=Array.isArray(e.views?.['10']?.by_minute_band)?
  e.views['10'].by_minute_band:[];
 if(!bySignal.length)return '<section class="nexus-evidence-model"><h3>IARA · resultados observados por sinal</h3>'+
  '<p>Ainda não existem observações verificáveis suficientes para avaliar cada tipo de alerta.</p></section>';
 const result=(list,limit)=>list.filter(x=>x&&Number.isFinite(Number(x.settled)))
   .sort((a,b)=>Number(b.settled)-Number(a.settled)).slice(0,limit)
   .map(x=>{
    const n=Number(x.settled),p=n?Number(x.hits)/n*100:null;
    const ci=n>=20?uncertainty(x.hits,n):null;
    const conclusion=n<20?'Amostra pequena':n<50?'Em observação':'Amostra maior, ainda não calibrada';
    return '<tr><th>'+h(x.label)+'</th><td>'+count(n)+'</td><td>'+pct(p)+'</td>'+
      '<td>'+h(ci?ci.low+'%–'+ci.high+'%':'—')+'</td>'+
      '<td>'+h(conclusion)+'</td></tr>';
   }).join('');
 const header='<table class="nexus-evidence-breakdown"><thead><tr><th>Grupo</th><th>Desfechos</th>'+
  '<th>Gols até 10 min</th><th>Wilson 95%*</th><th>Qualidade</th></tr></thead><tbody>';
 return '<section class="nexus-evidence-model"><h3>◉ IARA · o que os alertas realmente produziram</h3>'+
 '<p>Comparação histórica por tipo de sinal e trecho do jogo. Sem extrapolar para uma chance individual de gol.</p>'+
 '<div class="nexus-evidence-scroll">'+header+result(bySignal,8)+'</tbody></table></div>'+
 (byBand.length?'<details><summary>Ver desempenho por intervalo do jogo</summary>'+
 '<div class="nexus-evidence-scroll">'+header+result(byBand,7)+'</tbody></table></div></details>':'')+
 '<p><small>*Intervalo estatístico descritivo (Wilson), assumindo observações independentes; jogos repetidos violam essa hipótese. '+
 'Não é intervalo de calibração nem previsão operacional. Ajustar parâmetros exige validação fora da amostra.</small></p></section>';
}

function alertHTML(data){
 const d=data&&typeof data==='object'?data:{},journal=d.signal_journal||{};
 const summary=normalizeSummary(d.signal_evaluation,journal);
 const feed=Array.isArray(d.alerts)?d.alerts:[];
 const unique=new Set();
 const alerts=(Array.isArray(journal.items)?journal.items:[]).filter(x=>{
  if(!x||typeof x.id!=='string'||!x.id||unique.has(x.id))return false;
  unique.add(x.id);return true;
 }).slice(0,80);
 const card=n=>{
  const v=summary[n],rate=v.settled>0?pct(v.rate_pct):'—';
  return '<article class="nexus-evidence-window"><small>GOL ATÉ '+n+' MIN APÓS ALERTA</small>'+
   '<strong>'+rate+'</strong><p>'+count(v.settled)+' resultados verificáveis: '+
   '<b>'+count(v.hits)+'</b> com gol · <b>'+count(v.misses)+'</b> sem gol</p>'+
   '<p>'+count(v.pending)+' pendentes · '+count(v.incomplete)+' incompletos · '+
   count(v.unknown)+' indeterminados</p></article>';
 };
 const stamp=x=>{
  const at=new Date(String(x||''));return Number.isFinite(at.getTime())?
   at.toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',
    hour:'2-digit',minute:'2-digit'}):'sem horário verificável';
 };
 const outcome=x=>{
  const status=x.outcome_conflict?'indeterminado':x.outcomes?.['10']||'pendente';
  const string=label[status]||'Não verificável';
  return '<span class="nexus-evidence-result '+(tone[status]||'unknown')+'">'+h(string)+'</span>';
 };
 const observations=alerts.length?
   '<div class="nexus-evidence-alert-list">'+alerts.map(a=>
    '<article class="nexus-evidence-alert"><div><strong>'+h(a.icon||'◉')+' '+
    h(a.home||'Mandante')+' × '+h(a.away||'Visitante')+'</strong>'+
    '<small>'+h(a.league||'')+' · '+h(a.minute==null?'?':String(a.minute))+'′ · '+
    h(stamp(a.captured_at))+'</small><small>'+h(a.rule||'Observação')+
    (a.basis==='cumulative_stat_snapshot'?' · scout acumulado':'')+'</small></div>'+
    '<div class="nexus-evidence-horizons">'+['5','10','15'].map(n=>{
      const state=a.outcome_conflict?'indeterminado':a.outcomes?.[n]||'pendente';
      return '<span title="'+h(label[state]||'Indisponível')+'">'+n+'m: '+
         h(state==='gol_confirmado'?'✓ Gol':state==='sem_gol_confirmado'?'✕ Sem gol':
           state==='pendente'?'… Pendente':state==='janela_incompleta'?'◷ Parcial':'? Incerto')+
       '</span>';
     }).join('')+'</div></article>').join('')+'</div>':
   '<p class="nexus-evidence-await">Sem alertas com minuto confirmado na amostra acessível. Confira o histórico da nuvem ou aguarde a próxima coleta.</p>';
 return '<div class="nexus-evidence-alerts"><h3>Alertas esportivos · acertos e erros verificáveis</h3>'+
 '<p>Avaliação dos alertas reais registrados, em janelas independentes de 5, 10 e 15 minutos. '+
 'Não são odds, apostas ou cálculo de EV+.</p>'+
 '<div class="nexus-evidence-windows">'+['5','10','15'].map(card).join('')+'</div>'+
 calibrationHTML(d.signal_evaluation)+
 '<p class="nexus-evidence-foot">A taxa usa apenas gols/sem gol confirmados. Alertas da mesma partida são correlacionados. '+
 'Alertas pendentes e janelas sem cobertura não entram na taxa.</p>'+
 '<h3>Memória de alertas com minuto confirmado <small>('+count(alerts.length)+' mostrados · últimos 80)</small></h3>'+
 observations+
 (feed.length?'<details class="nexus-evidence-legacy"><summary>Ver outras '+count(feed.length)+
 ' mensagens do radar (não equivalem a resultados de apostas)</summary>'+
 feed.slice(0,65).map(a=>'<div class="nexus-evidence-old"><b>'+
   h(a.message||'Evento de monitoramento')+'</b><small>'+h(stamp(a.created_at))+
   ' · '+h(a.category||'monitoramento')+'</small></div>').join('')+'</details>':'')+
 '</div>';
}
root.NexusEvidence={auditHTML,normalizeSummary,alertHTML,uncertainty,calibrationHTML};
if(typeof module!=='undefined'&&module.exports)module.exports=root.NexusEvidence;
})(typeof window!=='undefined'?window:globalThis);
