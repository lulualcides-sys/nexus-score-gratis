/* NEXUS 30–70: painel independente. Estimativas experimentais não são
   probabilidades calibradas, odds, EV, nem recomendação de entrada. */
(function(root){
"use strict";
const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const num=x=>x===null||x===undefined||!Number.isFinite(Number(x))?"—":Number(x).toLocaleString("pt-BR",{maximumFractionDigits:1});
const fmt=x=>num(x)+(num(x)==="—"?"":"%");
const texts={
 insufficient_history:"Amostra insuficiente para testar o indicador.",
 no_verified_improvement_over_baseline:"Modelo experimental NÃO superou a previsão-base no teste cronológico.",
 small_or_unconfirmed_historical_gain:"Melhoria histórica pequena ou inconclusiva: porcentagem de gol bloqueada até evidência mais robusta.",
 better_than_constant_baseline_in_historical_holdout:"Superou a previsão-base neste teste histórico; ainda sem validação prospectiva."
};
function interpret(data){
 if(!data||data.schema!==1||data.name!=="NEXUS Gol 30–70")return null;
 const s=data.sample||{},v=data.validation||{},live=Array.isArray(data.live)?data.live:[];
 return {
  status:texts[v.status]||"Aguardando auditoria do indicador.",
  sample:s,validation:v,live,
  percentageAllowed:v.probability_released_for_live===true,
  activeCount:live.length
 };
}
function html(data){
 const view=interpret(data);
 if(!view)return '<h3>Gol 30–70 · dados ainda não disponíveis</h3><p>A coleta publicará o diagnóstico sem estimativas fictícias.</p>';
 const {sample:s,validation:v,live}=view;
 const active=live.slice(0,20).map(x=>{
  const valid=view.percentageAllowed&&Number.isFinite(Number(x.experimental_pct))&&x.experimental_pct!==null;
  const value=valid?fmt(x.experimental_pct):"Sem %";
  const fields=(x.factors||[]).slice(0,4).map(z=>esc(z.field)+": "+esc(z.category)).join(" · ");
  return '<article class="nexus-goal-window-match"><div><strong>'+esc(x.home)+" × "+esc(x.away)+
    '</strong><small>'+esc(x.minute)+"′ · "+esc(x.rule)+"</small>"+
    '<small>'+esc(fields||"Dados limitados; exigir novas observações")+"</small></div>"+
    '<div class="nexus-goal-window-estimate"><strong>'+esc(value)+
    '</strong><small>'+(valid?"Estimativa observacional":"Não estimável")+"</small></div></article>";
 }).join("");
 return '<div class="nexus-goal-window-title"><div><h3>Radar de gol · 30′ a 70′</h3>'+
  '<p>Alertas entre 30′ e 70′. Alvo: gol nos <b>15 minutos seguintes</b>; alerta aos 70′ cobre até os 85′.</p></div>'+
  '<span class="nexus-goal-window-tag">PESQUISA · SEM ODDS</span></div>'+
  '<div class="nexus-goal-window-metrics">'+
  '<div><small>PARTIDAS COM ALERTA INICIAL</small><b>'+esc(s.first_alert_per_match||0)+'</b></div>'+
  '<div><small>DESFECHOS VERIFICÁVEIS</small><b>'+esc(s.settled||0)+'</b></div>'+
  '<div><small>TREINO / TESTE POSTERIOR</small><b>'+esc(s.train||0)+' / '+esc(s.holdout||0)+'</b></div>'+
  '<div><small>JOGOS EM ALERTA AGORA</small><b>'+esc(live.length)+'</b></div></div>'+
  '<p class="nexus-goal-window-status"><b>Validação:</b> '+esc(view.status)+'</p>'+
  (v.brier_model!==null&&v.brier_model!==undefined?
    '<p class="nexus-goal-window-note">Brier teste: modelo '+num(v.brier_model)+
    ' · previsão-base '+num(v.brier_constant_baseline)+
    ' · erro de calibração ECE '+num(v.ece_holdout)+
    ' (menor é melhor). Não demonstra lucro nem vantagem em odds reais.</p>':
    '<p class="nexus-goal-window-note">Sem teste independente suficiente: o indicador não deve exibir uma chance como comprovada.</p>')+
  (v.robustness_exploratory&&v.robustness_exploratory.auc!==null&&v.robustness_exploratory.auc!==undefined?
    '<p class="nexus-goal-window-note">Separação entre jogos com/sem gol (AUC): '+
    num(v.robustness_exploratory.auc)+' · dias no teste: '+
    esc(v.robustness_exploratory.days)+'. Intervalo bootstrap 95% da melhoria no Brier: '+
    esc((v.robustness_exploratory.gain_ci95||[]).map(num).join(' a '))+
    '. Diagnóstico retrospectivo, não certificação prospectiva.</p>':'')+
  (active?'<h4>Alertas recentes em partidas ao vivo</h4>'+active:
  '<p class="nexus-goal-window-empty">Nenhum sinal recente e verificável na faixa 30′–70′. O radar não força previsões quando faltam pressão, scouts ou alertas atualizados.</p>')+
  '<p class="nexus-goal-window-note">Um sinal por jogo no treinamento. Resultados indeterminados não viram derrotas. '+
  'Números, quando disponíveis, são estimativas observacionais experimentais e não probabilidades calibradas. '+
  'Sem evidência de odds, liquidez, EV+ ou retorno financeiro.</p>';
}
function render(data){
 if(typeof document==="undefined")return;
 const el=document.getElementById("cloud-goal-30-70");
 if(el)el.innerHTML=html(data);
}
const api={interpret,html,render};
root.NexusGoalWindow=api;
if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof window!=="undefined"?window:globalThis);
