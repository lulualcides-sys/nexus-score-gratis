/* NEXUS | Auditoria dos sinais observados (não é EV+, backtest de apostas ou P/L).
 * Compatível com o painel cloud web e o NEXUS original via journal existente.
 */
(function(root){
  "use strict";
  const H=['5','10','15','20','25','30','35','40'];
  const dims={by_signal:'Tipo de sinal',by_team:'Equipe',by_league:'Campeonato',
              by_minute_band:'Faixa de minuto',by_minute:'Minuto exato'};
  const cleanHTML=x=>String(x??'').replace(/[&<>"']/g,ch=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const band=m=>m>90?'91+′':(Math.floor((m-1)/15)*15+1)+'–'+(Math.floor((m-1)/15)*15+15)+'′';
  const dayBR=value=>{
    const d=new Date(value);
    if(!Number.isFinite(d.valueOf()))return null;
    const p=Object.fromEntries(new Intl.DateTimeFormat('en-US',{
      timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'
    }).formatToParts(d).filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
    return p.year+'-'+p.month+'-'+p.day;
  };
  function fallback(journal){
    const uniq=new Set(),entries=[];
    for(const x of Array.isArray(journal?.items)?journal.items:[]){
      const m=Number(x?.minute),d=dayBR(x?.captured_at);
      if(!x||!x.id||uniq.has(x.id)||!x.match_id||!x.rule||!d||!Number.isInteger(m)||m<1||m>120)continue;
      uniq.add(x.id);
      const team=x.team==='home'?x.home:x.team==='away'?x.away:null;
      entries.push({day:d,match_id:String(x.match_id),minute:m,
        signal:String((x.icon||'')+' '+x.rule).trim(),
        team:String(team||'Equipe não definida'),
        league:String(x.league||'Campeonato não informado'),band:band(m),
        outcomes:x.outcome_conflict?{}:(x.outcomes||{})});
    }
    function rollup(arr,h){
      const hits=arr.filter(x=>x.outcomes[h]==='gol_confirmado').length;
      const misses=arr.filter(x=>x.outcomes[h]==='sem_gol_confirmado').length;
      const settled=hits+misses;
      return {observations:arr.length,matches:new Set(arr.map(x=>x.match_id)).size,
        settled,hits,misses,
        pending:arr.filter(x=>!x.outcomes[h]||x.outcomes[h]==='pendente').length,
        unknown:arr.filter(x=>x.outcomes[h]==='indeterminado').length,
        incomplete:arr.filter(x=>x.outcomes[h]==='janela_incompleta').length,
        rate_pct:settled?Math.round(hits/settled*1000)/10:null,
        sample_quality:settled>=50?'amostra_maior':settled>=20?'em_observacao':'amostra_pequena'};
    }
    const grouping=(h,field)=>{
      const groups=new Map();
      for(const x of entries){
        const key=x[field];
        if(!groups.has(key))groups.set(key,[]);
        groups.get(key).push(x);
      }
      const vals=Array.from(groups,([key,arr])=>({
        label:field==='minute'?key+"'":key,...rollup(arr,h)}));
      if(field==='minute')vals.sort((a,b)=>parseInt(a.label)-parseInt(b.label));
      else if(field==='band'){const order=['1–15′','16–30′','31–45′','46–60′','61–75′','76–90′','91+′'];
        vals.sort((a,b)=>order.indexOf(a.label)-order.indexOf(b.label));}
      else vals.sort((a,b)=>b.settled-a.settled||b.observations-a.observations||a.label.localeCompare(b.label));
      return vals.slice(0,field==='team'||field==='league'?100:150);
    };
    const horizons=Object.fromEntries(H.map(h=>[h,rollup(entries,h)]));
    const views={};
    for(const h of H){
      const dates=[...new Set(entries.map(x=>x.day))].sort(),seen=[];
      const evolution=dates.map(day=>{
        const daily=entries.filter(x=>x.day===day);
        seen.push(...daily);
        const a=rollup(seen,h),d=rollup(daily,h);
        return {day,daily_observations:d.observations,daily_settled:d.settled,
          daily_hits:d.hits,daily_rate_pct:d.rate_pct,
          cumulative_observations:a.observations,cumulative_matches:a.matches,
          cumulative_settled:a.settled,cumulative_hits:a.hits,
          cumulative_misses:a.misses,cumulative_rate_pct:a.rate_pct};
      });
      views[h]={by_signal:grouping(h,'signal'),by_team:grouping(h,'team'),
                by_league:grouping(h,'league'),by_minute:grouping(h,'minute'),
                by_minute_band:grouping(h,'band'),evolution};
    }
    return {schema:1,summary:horizons['10'],horizons,views,updated_at:journal?.updated_at,
      scope:'subamostra_sincronizada',money_status:'unavailable_without_entry_odds_and_trade_results'};
  }
  const fmtPct=x=>x===null||x===undefined||!Number.isFinite(Number(x))?'—':
    Number(x).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%';
  let horizon='10',dimension='by_signal';
  function render(stored,journal){
    if(typeof document==='undefined')return;
    const host=document.getElementById('cloud-signal-evaluation');
    if(!host)return;
    const data=stored?.views?.['40']?stored:fallback(journal||{});
    const complete=Boolean(stored?.views?.['40']);
    const summary=data.horizons?.[horizon]||{};
    const view=data.views?.[horizon]||{};
    const rows=Array.isArray(view[dimension])?view[dimension]:[];
    const evolution=Array.isArray(view.evolution)?view.evolution:[];
    const pct=fmtPct(summary.rate_pct);
    const maxN=Math.max(1,...evolution.map(v=>Number(v.cumulative_settled)||0));
    const graph=evolution.slice(-45).map(r=>{
      const width=Math.max(0,Math.min(100,(Number(r.cumulative_settled)||0)/maxN*100));
      return '<div class="nexus-evolution-row"><small>'+cleanHTML(r.day)+
        '</small><span class="nexus-evolution-track"><i style="width:'+width.toFixed(2)+'%"></i></span>'+
        '<b>'+Number(r.cumulative_settled||0)+' verificados</b><em>'+fmtPct(r.cumulative_rate_pct)+'</em></div>';
    }).join('');
    const lines=rows.slice(0,100).map(r=>'<tr><th>'+cleanHTML(r.label)+'</th>'+
      '<td>'+Number(r.observations||0)+'</td><td>'+Number(r.matches||0)+'</td>'+
      '<td>'+Number(r.settled||0)+'</td><td>'+Number(r.hits||0)+'</td>'+
      '<td>'+Number(r.misses||0)+'</td><td><b>'+fmtPct(r.rate_pct)+'</b>'+
      (Number(r.settled||0)<20?'<small class="nexus-small-sample"> amostra pequena</small>':'')+
      '</td></tr>').join('');
    host.innerHTML='<div class="nexus-evaluation-heading"><div><h3>Avaliação histórica por sinais</h3>'+
     '<p>Gols confirmados após alertas, com contagem por equipe, campeonato e minuto.</p></div>'+
     '<small>'+(complete?'Resumo de todo o diário disponível':'Subamostra dos alertas sincronizados')+'</small></div>'+
     '<div class="nexus-evaluation-controls"><label>Janela de verificação '+
     '<select id="nexus-eval-horizon">'+H.map(h=>'<option value="'+h+'" '+(h===horizon?'selected':'')+'>'+h+' minutos</option>').join('')+
     '</select></label><label>Agrupar por <select id="nexus-eval-dimension">'+
     Object.entries(dims).map(([id,name])=>'<option value="'+id+'" '+(dimension===id?'selected':'')+'>'+name+'</option>').join('')+
     '</select></label></div>'+
     '<div class="nexus-evaluation-kpis"><div><small>OBSERVAÇÕES</small><b>'+Number(summary.observations||0)+'</b></div>'+
     '<div><small>RESULTADOS VERIFICÁVEIS</small><b>'+Number(summary.settled||0)+'</b></div>'+
     '<div><small>COM GOL / SEM GOL</small><b>'+Number(summary.hits||0)+' / '+Number(summary.misses||0)+'</b></div>'+
     '<div><small>TAXA OBSERVADA</small><b>'+pct+'</b></div></div>'+
     '<p class="nexus-evaluation-meta">'+Number(summary.matches||0)+' partidas distintas · '+
     Number(summary.pending||0)+' pendentes · '+Number(summary.incomplete||0)+' incompletos · '+
     Number(summary.unknown||0)+' indeterminados</p>'+
     (lines?'<div class="nexus-evaluation-scroll"><table><thead><tr><th>Grupo</th><th>Obs.</th><th>Jogos</th>'+
     '<th>Verificados</th><th>Gol</th><th>Sem gol</th><th>Taxa</th></tr></thead><tbody>'+lines+
     '</tbody></table></div>':'<p>Nenhum alerta válido nesta amostra.</p>')+
     '<h4>Evolução da amostra · '+horizon+' min</h4>'+
     (graph?'<div class="nexus-evolution">'+graph+'</div>':'<p>Sem datas de captura verificáveis.</p>')+
     '<p class="nexus-evaluation-disclaimer">Taxa = gols ÷ (gols + sem gol). Exclui resultados não verificáveis;'+
     ' alertas no mesmo jogo são correlacionados. Não é probabilidade calibrada nem EV+. '+
     'Sem odd de entrada, stake/risco e liquidação por operação não há lucro real em unidades. '+
     'P/L paper de entradas prévias é contabilizado separadamente.</p>';
    host.querySelector('#nexus-eval-horizon').onchange=e=>{horizon=e.target.value;render(stored,journal)};
    host.querySelector('#nexus-eval-dimension').onchange=e=>{dimension=e.target.value;render(stored,journal)};
  }
  root.NexusSignalEvaluation={render};
  if(typeof module!=='undefined'&&module.exports)module.exports={fallback,cleanHTML,minuteBand:band};
})(typeof window!=='undefined'?window:globalThis);
