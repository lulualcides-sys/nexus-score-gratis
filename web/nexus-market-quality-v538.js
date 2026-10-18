/* NEXUS 5.38 — critérios auditáveis por mercado, sem EV validado presumido. */
(function(root){
'use strict';
const H=s=>String(s??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const N=v=>v===null||v===undefined||v===''||typeof v==='boolean'||!Number.isFinite(Number(v))?null:Number(v);
const P=v=>N(v)===null?'—':N(v).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%';
const labels={ '1x2':'Resultado 1X2','double_chance':'Dupla chance',
 'over_under_25':'Total 2,5 gols','btts':'Ambas marcam'};
const selections={home:'Mandante vence',draw:'Empate',away:'Visitante vence',
 '1X':'Mandante ou empate','X2':'Visitante ou empate','12':'Mandante ou visitante',
 over:'Over 2.5',under:'Under 2.5',yes:'SIM',no:'NÃO'};
function analyse(b,fixture){
 if(!b||b.model_status!=='experimental_uncalibrated'||!Array.isArray(b.indications))
  return {status:'missing',items:[],reason:'Sem previsão pré-live congelada verificável.'};
 const start=N(fixture?.start_timestamp);
 const frozen=Date.parse(String(b.captured_at||''))/1000;
 if(!start||!Number.isFinite(frozen)||frozen>=start)
  return {status:'missing',items:[],reason:'Análise não comprovada como anterior ao início.'};
 const o=b.odds||{},prices=o.prices||{};
 const priceTime=Date.parse(String(o.captured_at||''))/1000;
 const compatible=!!o.source&&!!o.bookmaker&&o.recent_at_check===true&&
  Number.isFinite(priceTime)&&priceTime<start&&
  ['home','draw','away'].every(k=>N(prices[k])!==null&&N(prices[k])>1.01&&N(prices[k])<1000);
 const settled=new Map((b.settlement?.checks||[]).filter(x=>x&&
  ['hit','miss'].includes(x.result)).map(x=>[x.market+'|'+x.selection,x.result]));
 const items=b.indications.slice(0,4).filter(x=>x&&labels[x.market]&&N(x.probability)!==null&&
  N(x.probability)>=0&&N(x.probability)<=100).map(x=>{
  const odd=x.market==='1x2'&&compatible&&
   ['home','draw','away'].includes(x.selection)?N(prices[x.selection]):null;
  const ev=odd===null?null:Math.round((N(x.probability)*odd-100)*100)/100;
  const outcome=settled.get(x.market+'|'+x.selection)||null;
  const evState=ev===null?'unavailable':ev>0?'theory_positive':'theory_non_positive';
  return {market:x.market,label:labels[x.market],selection:x.selection,
   selection_label:selections[x.selection]||x.selection,probability:N(x.probability),
   odd,ev_pct:ev,ev_state:evState,result:outcome};
 });
 return {status:compatible?'model_not_calibrated':'no_verified_price',
  source:compatible?String(o.source):null,bookmaker:compatible?String(o.bookmaker):null,
  captured_at:compatible?String(o.captured_at):null,
  items,reason:compatible?'Odds reais pré-jogo comparadas ao modelo não calibrado. Sem EV validado.':
   'Sem trio 1X2 íntegro com cotação anterior ao apito e preço recente verificado.'};
}
function render(b,g){
 const result=analyse(b,g);
 if(!result.items.length)return '<section class="nexus-market-check"><h3>Mercados pré-live</h3>'+
 '<p>'+H(result.reason)+'</p></section>';
 const footer=result.source?
  'Cotação: '+H(result.source)+' · '+H(result.bookmaker)+' · '+H(result.captured_at):
  'Odds não disponíveis ou desatualizadas para estes mercados.';
 return '<section class="nexus-market-check"><h3>◉ MERCADOS · PRÉ-LIVE VERSUS RESULTADO</h3>'+
 '<p>'+H(result.reason)+' Nenhuma operação é presumida.</p>'+
 '<div class="nexus-market-grid">'+result.items.map(x=>{
  const status=x.ev_state==='theory_positive'?'EV TEÓRICO +'+P(x.ev_pct):
   x.ev_state==='theory_non_positive'?'EV TEÓRICO '+P(x.ev_pct):
   'EV INDISPONÍVEL';
  const ending=x.result==='hit'?'✓ CONFIRMADO':x.result==='miss'?'✕ NÃO OCORREU':'⏳ AGUARDANDO FINAL';
  return '<article><small>'+H(x.label)+'</small><strong>'+H(x.selection_label)+'</strong>'+
   '<div><span>Modelo '+P(x.probability)+'</span><b>'+H(status)+'</b></div>'+
   '<p>Odd: '+H(x.odd===null?'—':x.odd.toLocaleString('pt-BR',{minimumFractionDigits:2}))+
   ' · '+H(ending)+'</p></article>';
 }).join('')+'</div><p class="nexus-market-source">'+H(footer)+'</p>'+
 '<small>Acerto/erro esportivo não implica lucro. Probabilidades Poisson experimentais; EV+ matemático não valida rentabilidade.</small></section>';
}
function coverage(evidence,oddsStatus,standings){
 const markets=Array.isArray(evidence?.markets)?evidence.markets:[];
 const obs=Number(evidence?.fixtures_with_frozen_forecast||0);
 const priced=Number(evidence?.fixtures_with_verified_pregame_1x2||0);
 const read=(n)=>Number.isFinite(Number(n))?Number(n):null;
 const rows=markets.map(m=>({market:m.market||'',label:m.label||m.market||'',
  forecasts:read(m.forecasts)||0,priced:read(m.with_price)||0,
  settled:read(m.settled)||0,hits:read(m.hits)||0,
  accuracy:m.settled>0?Math.round(m.hits/m.settled*1000)/10:null}));
 return {prelive:obs,priced,coverage_pct:obs?Math.round(priced/obs*1000)/10:null,
  markets:rows,odds_updated:read(oddsStatus?.odds_updated),
  odds_sources:{
   espn:oddsStatus?.espn_fallback?.quotes_added??null,
   api_football:oddsStatus?.api_football?.status||'not_configured',
   the_odds_api:oddsStatus?.the_odds_api?.status||'not_configured',
   sofascore_blocked:(oddsStatus?.errors||[]).some(x=>/SofaScore.*403/i.test(String(x)))},
  standings:{
   tables:read(standings?.tables_received),cache:read(standings?.cache_tables_present),
   enriched:read(standings?.fixtures_enriched),unqueried:read(standings?.unqueried_leagues)}
 };
}
function coverageHTML(evidence,oddsStatus,standings){
 const c=coverage(evidence,oddsStatus,standings);
 const status= c.prelive?c.priced+' de '+c.prelive+' partidas com pré-live ('+P(c.coverage_pct)+')':
  'Ainda sem pré-live congelado na janela';
 return '<section class="nexus-market-coverage"><h3>📊 SAÚDE DAS FONTES E DOS MERCADOS</h3>'+
 '<p><b>1X2 pré-jogo íntegro:</b> '+H(status)+
 ' · novos preços nesta coleta: '+H(c.odds_updated===null?'—':c.odds_updated)+'.</p>'+
 '<p>ESPN: '+H(c.odds_sources.espn===null?'—':c.odds_sources.espn)+' novas cotações · API-Football: '+
 H(c.odds_sources.api_football)+' · The Odds API: '+H(c.odds_sources.the_odds_api)+
 (c.odds_sources.sofascore_blocked?' · SofaScore: 403, sem contornar bloqueio':'')+'.</p>'+
 '<p>Classificação: '+H(c.standings.tables===null?'—':c.standings.tables)+' tabelas novas · '+
 H(c.standings.cache===null?'—':c.standings.cache)+' tabelas em cache · '+
 H(c.standings.enriched===null?'—':c.standings.enriched)+' partidas com contexto · '+
 H(c.standings.unqueried===null?'—':c.standings.unqueried)+' ligas aguardando consulta.</p>'+
 '<div class="nexus-evidence-scroll"><table><thead><tr><th>Mercado</th>'+
 '<th>Pré-live</th><th>Com odd</th><th>Conferidos</th><th>Acertos</th><th>Taxa observada</th></tr></thead><tbody>'+
 (c.markets.length?c.markets.map(m=>'<tr><th>'+H(m.label)+'</th><td>'+m.forecasts+
 '</td><td>'+m.priced+'</td><td>'+m.settled+'</td><td>'+m.hits+'</td><td>'+
 P(m.accuracy)+'</td></tr>').join(''):'<tr><td colspan="6">Aguardando análise pré-live real registrada</td></tr>')+
 '</tbody></table></div>'+
 '<small>Taxas observadas não são probabilidades calibradas nem retorno financeiro. '+
 'Sem preço da mesma casa, mercado e horário, EV fica indisponível.</small></section>';
}
const api={analyse,render,coverage,coverageHTML};
root.NexusMarketQuality=api;
if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
