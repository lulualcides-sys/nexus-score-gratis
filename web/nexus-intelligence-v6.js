/* NEXUS 6.0 — apenas estatísticas auditáveis e simulação explicitamente fictícia. */
(function(root){
'use strict';
const esc=x=>String(x==null?'':x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=x=>x==null||!Number.isFinite(Number(x))?'—':Number(x).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%';
const n=x=>Math.max(0,Number(x)||0).toLocaleString('pt-BR');
const brl=x=>Number(x).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
let tab='signals', minSample=20, compact=true, scenario='over_15', odd='1.80', stake='100';
function historicalScenario(market,price,risk){
 const count=Number(market?.finished_verified),wins=Number(market?.hits),misses=Number(market?.misses);
 if(!Number.isFinite(count)||count<=0||!Number.isInteger(wins)||!Number.isInteger(misses)||
    wins+misses!==count||!Number.isFinite(price)||price<=1||price>100||
    !Number.isFinite(risk)||risk<=0||risk>100000)return null;
 const profit=market.market==='lay_goleada'?wins*risk/(price-1)-misses*risk:
     wins*risk*(price-1)-misses*risk;
 return {matches:count,wins,misses,profit:Math.round(profit*100)/100};
}
function render(doc,odds){
 const host=typeof document!=='undefined'?document.getElementById('cloud-intelligence-v6'):null;
 if(!host)return;
 if(!doc||!Array.isArray(doc.signal_ranking)){
  host.innerHTML='<h3>NEXUS 6.0 — Radar Inteligente</h3><p>Sem coleta histórica válida para esta versão. O arquivo antigo não foi removido.</p>';
  return;
 }
 const rankings=tab==='leagues'?doc.league_ranking:doc.signal_ranking;
 const filtered=(rankings||[]).filter(x=>Number(x.settled)>=minSample);
 const markets=Array.isArray(doc.markets?.markets)?doc.markets.markets:[];
 const market=markets.find(m=>m.market===scenario);
 const last=doc.last_day||'—',first=doc.first_day||'—';
 const rows=filtered.slice(0,40).map((x,i)=>{
  const grade=x.quality_index==null?'Amostra insuficiente':n(x.quality_index)+'/100';
  const test=x.test_usable?pct(x.test_rate_pct)+' ('+n(x.test_settled)+' jogos)':
    'Não validado · '+n(x.test_settled)+' desfechos';
  return '<tr><td>'+n(i+1)+'</td><th>'+esc(x.label)+'</th><td>'+n(x.settled)+
    '</td><td>'+pct(x.rate_pct)+'</td><td>'+pct(x.wilson_lower_pct)+'</td><td>'+
    esc(grade)+'</td><td>'+esc(test)+'</td></tr>';
 }).join('');
 const cards=markets.map(m=>'<article class="nexus-v6-market"><small>'+esc(m.label)+'</small>'+
   '<strong>'+pct(m.rate_pct)+'</strong><span>'+n(m.hits)+' acertos / '+
   n(m.misses)+' erros · '+n(m.finished_verified)+' jogos</span>'+
   '<small>Sem odd observada · resultado pelo placar final</small></article>').join('');
 const prices=odds&&typeof odds==='object'?odds:{};
 const provider=[['SofaScore',prices.sofascore_quotes_added],['Coleta de odds',prices.odds_updated]];
 const sourceInfo=provider.map(([label,value])=>'<span>'+esc(label)+': '+
   (Number.isFinite(Number(value))&&value!=null?n(value):'sem contagem')+'</span>').join(' · ');
 host.innerHTML='<div class="nexus-v6-head"><div><h3>◈ NEXUS 6.0 · Radar inteligente</h3>'+
   '<p>Índice histórico descritivo, NÃO previsão de aposta. Primeiro sinal de cada jogo; 40 minutos.</p></div>'+
   '<button id="nexus-v6-compact" type="button" aria-expanded="'+String(!compact)+'">'+
   (compact?'Mostrar detalhes':'Modo compacto')+'</button></div>'+
   '<div class="nexus-v6-kpis"><div><small>Jogos distintos</small><b>'+n(doc.distinct_matches)+'</b></div>'+
   '<div><small>Dias com dados</small><b>'+n(doc.observed_days)+'</b></div>'+
   '<div><small>Janela</small><b>40 min</b></div>'+
   '<div><small>Validação temporal</small><b>'+(doc.split_date?'Separada':'Insuficiente')+'</b></div></div>'+
   '<p class="nexus-v6-meta">Cobertura real: '+esc(first)+' a '+esc(last)+
   ' · últimos 90 dias disponíveis, sem apagar o arquivo anterior. Corte de teste: '+
   esc(doc.split_date||'indisponível')+'.</p>'+
   '<div class="nexus-v6-contents" '+(compact?'hidden':'')+'>'+
   '<div class="nexus-v6-filters"><label>Ranking <select id="nexus-v6-ranking"><option value="signals" '+
   (tab==='signals'?'selected':'')+'>Tipos de alerta</option><option value="leagues" '+
   (tab==='leagues'?'selected':'')+'>Campeonatos</option></select></label>'+
   '<label>Amostra mínima <select id="nexus-v6-sample"><option value="20" '+
   (minSample===20?'selected':'')+'>20 partidas</option><option value="50" '+
   (minSample===50?'selected':'')+'>50 partidas</option><option value="100" '+
   (minSample===100?'selected':'')+'>100 partidas</option></select></label></div>'+
   (rows?'<div class="nexus-v6-scroll"><table><thead><tr><th>#</th><th>Grupo</th>'+
   '<th>Verificados</th><th>Gol ≤40m</th><th>Limite 95%</th><th>Índice*</th><th>Teste posterior</th>'+
   '</tr></thead><tbody>'+rows+'</tbody></table></div>':
   '<p>Sem amostra verificável suficiente para a classificação selecionada.</p>')+
   '<small>*Índice 0–100 = 75% limite inferior Wilson + 25% tamanho da amostra (limitado a 100). '+
   'Não é chance calibrada, nem vantagem sobre casas de apostas.</small>'+
   '<h4>Mercados por placares finais confirmados</h4>'+
   '<div class="nexus-v6-markets">'+(cards||'<p>Sem partidas finalizadas nesta coleta.</p>')+'</div>'+
   '<p>Escopo de mercados: partidas finalizadas presentes no snapshot atual. '+
   'Over 1.5, Over 2.5, BTTS e Lay Goleada contra margem de 3+ gols. '+
   'Sem reconstrução retroativa de odds ou de entradas executadas.</p>'+
   '<div class="nexus-v6-sim"><h4>Laboratório financeiro — cenários fictícios</h4>'+
   '<label>Mercado <select id="nexus-v6-market">'+markets.map(m=>'<option value="'+esc(m.market)+
   '" '+(scenario===m.market?'selected':'')+'>'+esc(m.label)+'</option>').join('')+'</select></label>'+
   '<label>Odd hipotética <input id="nexus-v6-odd" type="number" min="1.01" max="100" step="0.05" value="'+esc(odd)+'"></label>'+
   '<label>Stake / responsabilidade R$ <input id="nexus-v6-stake" type="number" min="1" max="100000" step="1" value="'+esc(stake)+'"></label>'+
   '<p id="nexus-v6-result" role="status"></p>'+
   '<small>Simulação contrafactual, não odd média observada, ROI real, EV calibrado nem recomendação.</small></div>'+
   '<h4>Fontes de odds — situação</h4>'+
   '<p>'+sourceInfo+' · atualização '+esc(prices.updated_at||'não informada')+'</p>'+
   '<p>Fontes gratuitas/permitidas existentes continuam em operação. Sem preços confiáveis, '+
   'o painel mostra indisponível; não inventa cotações nem usa serviços pagos.</p></div>';
 const button=host.querySelector('#nexus-v6-compact');
 button.onclick=()=>{compact=!compact;render(doc,odds)};
 if(compact)return;
 host.querySelector('#nexus-v6-ranking').onchange=e=>{tab=e.target.value;render(doc,odds)};
 host.querySelector('#nexus-v6-sample').onchange=e=>{minSample=Number(e.target.value);render(doc,odds)};
 const simulate=()=>{
  const inputMarket=host.querySelector('#nexus-v6-market'),inputOdd=host.querySelector('#nexus-v6-odd'),inputStake=host.querySelector('#nexus-v6-stake');
  scenario=inputMarket.value;odd=inputOdd.value;stake=inputStake.value;
  const data=historicalScenario(markets.find(x=>x.market===scenario),Number(odd),Number(stake));
  const output=host.querySelector('#nexus-v6-result');
  output.textContent=data?
    'CENÁRIO FICTÍCIO · '+n(data.matches)+' partidas · '+n(data.wins)+' acertos · '+n(data.misses)+
    ' erros · P/L hipotético '+brl(data.profit)+' (mesma odd inventada em todos os jogos; não houve operação).':
    'Não há resultados verificados suficientes ou os valores digitados são inválidos.';
 };
 for(const id of ['nexus-v6-market','nexus-v6-odd','nexus-v6-stake'])host.querySelector('#'+id).oninput=simulate;
 simulate();
}
root.NexusIntelligenceV6={render,historicalScenario};
if(typeof module!=='undefined'&&module.exports)module.exports={historicalScenario};
})(typeof window!=='undefined'?window:globalThis);
