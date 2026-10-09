(() => {
  "use strict";
  const $ = sel => document.querySelector(sel);
  const state = { payload:null, games:[], search:"", phase:"all", market:"all" };
  const ESC = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c=>ESC[c]);
  const date = value => {
    if(!value) return 'não informado';
    const d=new Date(value);
    return Number.isNaN(d.getTime()) ? 'não informado' : d.toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  };
  const int = v => Number.isFinite(Number(v)) ? Number(v) : 0;
  const some = (game,stat) => ['home','away'].some(side => game.stats?.[side]?.[stat] != null);
  const hasOdds = game => Array.isArray(game.odds) && game.odds.length;
  const pressure = game => Array.isArray(game.pressure) ? game.pressure : [];
  const phaseLabel = g => g.phase==='live' ? ('● AO VIVO'+(g.minute ? ' · '+esc(g.minute)+"′":'')) : g.phase==='finished'?'ENCERRADO':'PRÉ-JOGO';
  const escTitle = game => esc(game.home) + ' × ' + esc(game.away);
  const filterMarket = game => state.market==='all' ||
       (state.market==='shots' && some(game,'shots_on')) ||
       (state.market==='corners' && some(game,'corners')) ||
       (state.market==='pressure' && pressure(game).length>0) ||
       (state.market==='odds' && hasOdds(game));
  function card(g,index) {
    const tags=[
      pressure(g).length ? '<span class="tag good">▥ Pressão '+pressure(g).length+' min</span>' : '<span class="tag">Sem termômetro</span>',
      some(g,'shots_on')?'<span class="tag good">● Chutes</span>':'',
      some(g,'corners')?'<span class="tag good">⌁ Escanteios</span>':'',
      hasOdds(g)?'<span class="tag good">1X2 Odds</span>':''
    ].filter(Boolean).join('');
    return '<article class="match-card"><div class="match-top"><span class="league">'+esc(g.league||g.source||'Campeonato')+'</span>'+
      '<span class="'+(g.phase==='live'?'live-tag':'phase-tag')+'">'+phaseLabel(g)+'</span></div>'+
      '<div class="teams"><div class="team">'+esc(g.home)+'</div><div class="score">'+esc(g.score||'—')+'</div><div class="team away">'+esc(g.away)+'</div></div>'+
      '<div class="match-bottom"><div class="market-tags">'+tags+'</div><button class="details" data-id="'+index+'">Ver dados →</button></div></article>';
  }
  function render() {
    const all=state.games;
    const query=state.search.trim().toLocaleLowerCase('pt-BR');
    const matches=all.map((game,index)=>({game,index})).filter(({game})=>
      (state.phase==='all' || state.phase===game.phase) &&
      filterMarket(game) && (!query || (game.home+' '+game.away+' '+game.league).toLocaleLowerCase('pt-BR').includes(query)));
    $('#shown-count').textContent=matches.length+' partidas';
    $('#games').innerHTML=matches.length?matches.map(({game,index})=>card(game,index)).join(''):'<div class="empty">Nenhum jogo encontrado com esses filtros. Tente outra combinação.</div>';
    $('#games').querySelectorAll('[data-id]').forEach(btn=>btn.addEventListener('click',()=>openMatch(state.games[Number(btn.dataset.id)])));
  }
  const pressureHTML = pts => {
    if(!pts.length)return '<p class="small-note">O coletor ainda não registrou minutos de pressão para esta partida. Sem gráfico fictício.</p>';
    const max=Math.max(25,...pts.map(p=>Math.abs(Number(p.v)||0)));
    const ticks=pts.map(pt=>{
      const v=Number(pt.v)||0, h=Math.max(1,Math.min(49,Math.abs(v)/max*48));
      const y=v>=0 ? 'bottom:50%' : 'top:50%';
      return '<div class="tick" title="'+esc(pt.m)+' min · '+esc(pt.v)+'"><div class="bar '+(v<0?'neg':'')+'" style="'+y+';height:'+h+'%"></div></div>';
    }).join('');
    return '<div class="pressure-graph" role="img" aria-label="Histórico registrado de pressão em '+pts.length+' minutos">'+ticks+'</div><div class="chart-foot"><span>Verde: casa ↑</span><span>'+esc(pts.length)+' pontos registrados</span><span>Roxo: fora ↓</span></div>';
  };
  const scouts=(g)=>{
    const names=[['shots_on','Chutes no alvo'],['shots_off','Chutes para fora'],['big_chances','Grandes chances'],['corners','Escanteios'],['dangerous_attacks','Ataques perigosos']];
    const result=names.filter(([k])=>some(g,k)).map(([k,n])=>
      '<div class="scout"><strong>'+esc(g.stats?.home?.[k]??'—')+'</strong><span>'+n+'</span><strong>'+esc(g.stats?.away?.[k]??'—')+'</strong></div>');
    return result.length?'<div class="scout-table">'+result.join('')+'</div>':'<p class="small-note">Scouts não fornecidos nesta coleta.</p>';
  };
  function openMatch(g) {
    if(!g)return;
    const oddLabels={home:'CASA',draw:'EMPATE',away:'FORA'};
    const odds=(g.odds||[]).map(v=>'<div class="odd-pill">'+esc(oddLabels[v.sel]||v.sel)+'<b>'+esc(v.odd)+'</b><small>'+esc(v.source||'Fonte')+' · '+date(v.at)+'</small></div>').join('');
    $('#detail-content').innerHTML='<div class="detail-league">'+esc(g.league||'')+' · '+esc(g.source||'')+'</div>'+
     '<div class="detail-score">'+escTitle(g)+' &nbsp; '+esc(g.score||'—')+'</div>'+
     '<p class="small-note">'+phaseLabel(g)+' · Última observação: '+date(g.observed_at)+' · '+esc(g.day||'')+'</p>'+
     '<h3 class="detail-title">▥ Termômetro · pressão registrada</h3>'+pressureHTML(pressure(g))+
     '<h3 class="detail-title">◉ Estatísticas confirmadas</h3>'+scouts(g)+
     '<h3 class="detail-title">◇ Odds 1X2 verificadas</h3>'+
     (odds?'<div class="odds-list">'+odds+'</div>':'<p class="small-note">Nenhuma cotação 1X2 disponível para esta partida.</p>')+
     '<h3 class="detail-title">Mercados possíveis de acompanhar</h3><p class="small-note">Over/Under, BTTS, Match Odds e Lay Correct Score dependem de odds reais e critérios de entrada. Este painel não gera apostas, lucros, probabilidades nem sinais EV+ automaticamente.</p>';
    $('#detail').showModal();
  }
  async function load() {
    $('#message').textContent='Consultando último arquivo da nuvem...';
    $('#message').className='notice';
    try {
      const resp=await fetch('./data.json?ts='+Date.now(),{cache:'no-store'});
      if(!resp.ok)throw Error('Dados ainda não publicados ('+resp.status+').');
      const obj=await resp.json();
      if(!obj || !Array.isArray(obj.games))throw Error('Formato inválido do arquivo.');
      state.payload=obj;
      state.games=obj.games.filter(x=>x&&typeof x.home==='string'&&typeof x.away==='string');
      $('#last-updated').textContent=date(obj.exported_at);
      $('#last-source').textContent='Fonte: '+((obj.collector?.sources||[]).join(', ') || 'não confirmada');
      $('#metric-games').textContent=state.games.length;
      $('#metric-live').textContent=state.games.filter(x=>x.phase==='live').length;
      $('#metric-pressure').textContent=state.games.filter(x=>pressure(x).length>0).length;
      $('#metric-odds').textContent=state.games.filter(hasOdds).length;
      const age=Date.now()-new Date(obj.exported_at).getTime();
      if(age>4*3600000){
        $('#message').textContent='Atenção: dados com mais de 4 horas. Última exportação: '+date(obj.exported_at)+'. Não utilize para operações ao vivo.';
        $('#message').className='notice warn';
      } else {
        $('#message').textContent='Dados esportivos públicos. Coleta periódica (não são cotações ao vivo). '+(state.games.length===0?'Ainda não há jogos no arquivo.':'Última exportação: '+date(obj.exported_at)+'.');
        $('#message').className='notice ok';
      }
      render();
    } catch(err) {
      $('#message').textContent='O painel ainda não recebeu o primeiro snapshot. '+String(err.message||err);
      $('#message').className='notice warn';
      $('#games').innerHTML='<div class="empty">Aguardando o primeiro arquivo de coletas web.</div>';
    }
  }
  $('#search').addEventListener('input',ev=>{state.search=ev.target.value;render()});
  $('#phase').addEventListener('change',ev=>{state.phase=ev.target.value;render()});
  $('#market').addEventListener('change',ev=>{state.market=ev.target.value;render()});
  $('#refresh').addEventListener('click',load);
  $('#close-dialog').addEventListener('click',()=>$('#detail').close());
  $('#detail').addEventListener('click',ev=>{if(ev.target===$('#detail'))$('#detail').close()});
  load();
  setInterval(load,5*60*1000);
})();
