(() => {
  "use strict";
  const $ = sel => document.querySelector(sel);
  const state = { payload:null, games:[], search:"", phase:"all", market:"all", day:"all", isPrivate:false };
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
  // O servidor privado usa nomes de campos distintos do snapshot publico.
  // Normalizar evita exibir valores vazios apesar de haver dados reais.
  const normalizePrivate = raw => ({
    exported_at: raw.collection?.updated_at || null,
    collector: raw.collection || {},
    games: (raw.games || []).map(g => ({
      ...g,
      observed_at: g.last_seen || null,
      pressure: (Array.isArray(g.pressure) ? g.pressure : []).map(p => ({
        m: Number(p.m ?? p.minute), v: Number(p.v ?? p.value)
      })).filter(p => Number.isFinite(p.m) && Number.isFinite(p.v)),
      odds: (Array.isArray(g.odds) ? g.odds : []).filter(q => q.market === '1x2' || q.sel).map(q => ({
        sel: q.sel || q.selection, odd: q.odd ?? q.odds,
        source: q.source || q.bookmaker, at: q.at || q.captured_at
      })),
      signals: Array.isArray(g.signals) ? g.signals : []
    }))
  });
  const phaseLabel = g => g.phase==='live' ? ('● AO VIVO'+(g.minute ? ' · '+esc(g.minute)+"′":'')) : g.phase==='finished'?'ENCERRADO':'PRÉ-JOGO';
  const escTitle = game => esc(game.home) + ' × ' + esc(game.away);
  const filterMarket = game => state.market==='all' ||
       (state.market==='shots' && some(game,'shots_on')) ||
       (state.market==='corners' && some(game,'corners')) ||
       (state.market==='pressure' && pressure(game).length>0) ||
       (state.market==='odds' && hasOdds(game)) ||
       (state.market==='ev' && Array.isArray(game.signals) && game.signals.length>0) ||
       (state.market==='events' && Array.isArray(game.events) && game.events.length>0);
  const kickoff = g => {
    const v=Number(g.start_timestamp);
    if(!Number.isFinite(v)||v<=0)return 'Horário não informado';
    const dt=new Date(v*1000);
    if(!Number.isFinite(dt.getTime()))return 'Horário não informado';
    return dt.toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',hour:'2-digit',minute:'2-digit',hour12:false});
  };
  const matchDate = g => {
    const v=Number(g.start_timestamp);
    return Number.isFinite(v)&&v>0?
      new Date(v*1000).toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit'}):
      (g.day?.split('-').reverse().slice(0,2).join('/')||'');
  };
  const logoHTML=(url,name)=>{
    const host='https://a.espncdn.com/';
    const alt=esc('Escudo '+name);
    const ok=typeof url==='string' &&
      (/^https:\/\/a1?\.espncdn\.com\/i\/teamlogos\//.test(url) ||
       /^https:\/\/images\.fotmob\.com\/image_resources\/logo\/teamlogo\/\d{1,12}\.png$/.test(url));
    return '<span class="club-badge">'+
      (ok?'<img loading="lazy" decoding="async" referrerpolicy="no-referrer" src="'+esc(url)+
          '" alt="'+alt+'" onerror="this.hidden=true;this.nextElementSibling.hidden=false">'+
          '<span class="club-initials" hidden>'+esc(String(name||'?').slice(0,2).toUpperCase())+'</span>':
          '<span class="club-initials">'+esc(String(name||'?').slice(0,2).toUpperCase())+'</span>')+
      '</span>';
  };
  const chronOrder=(a,b)=>{
    // Hoje e exibido antes dos dias passados; dentro de cada dia o primeiro horario vem primeiro.
    if(a.day!==b.day)return String(b.day||'').localeCompare(String(a.day||''));
    const x=Number(a.start_timestamp),y=Number(b.start_timestamp);
    const ax=Number.isFinite(x)&&x>0?x:Infinity;
    const by=Number.isFinite(y)&&y>0?y:Infinity;
    return ax-by || String(a.league||'').localeCompare(String(b.league||'')) ||
      String(a.home||'').localeCompare(String(b.home||''));
  };
  function card(g,index) {
    const tags=[
      pressure(g).length ? '<span class="tag good">▥ Pressão '+pressure(g).length+' min</span>' : '<span class="tag">Sem termômetro</span>',
      some(g,'shots_on')?'<span class="tag good">● Chutes</span>':'',
      some(g,'corners')?'<span class="tag good">⌁ Escanteios</span>':'',
      hasOdds(g)?'<span class="tag good">1X2 Odds</span>':'',
      g.signals?.length?'<span class="tag good">EV experimental '+g.signals.length+'</span>':'',
      g.events?.length?'<span class="tag">◉ Eventos '+g.events.length+'</span>':'',
      g.outcomes?.correct_score?'<span class="tag">FT '+esc(g.outcomes.correct_score)+'</span>':''
    ].filter(Boolean).join('');
    return '<article class="match-card"><div class="match-top"><span class="league">'+esc(g.league||g.source||'Campeonato')+
      (g.round?' · '+esc(g.round):'')+'</span>'+
      '<span class="'+(g.phase==='live'?'live-tag':'phase-tag')+'">'+phaseLabel(g)+'</span></div>'+
      '<div class="match-time"><span class="match-time-symbol">◷</span> '+matchDate(g)+' · '+kickoff(g)+
      ' <span class="match-tz">Brasília</span></div>'+
      '<div class="teams"><div class="team">'+logoHTML(g.home_logo,g.home)+'<span class="team-name">'+esc(g.home)+'</span></div>'+
      '<div class="score-block"><div class="score">'+(g.phase==='scheduled'?'×':esc(g.score||'—'))+
      '</div><small>'+ (g.phase==='scheduled'?'A iniciar':g.phase==='live'?'AO VIVO':'Final')+'</small></div>'+
      '<div class="team away">'+logoHTML(g.away_logo,g.away)+'<span class="team-name">'+esc(g.away)+'</span></div></div>'+
      '<div class="match-bottom"><div class="market-tags">'+tags+'</div><button class="details" data-id="'+index+'">Ver dados →</button></div></article>';
  }
  function render() {
    const all=state.games;
    const query=state.search.trim().toLocaleLowerCase('pt-BR');
    const matches=all.map((game,index)=>({game,index})).filter(({game})=>
      (state.phase==='all' || state.phase===game.phase) &&
      (state.day==='all' || game.day===state.day) &&
      filterMarket(game) && (!query || (game.home+' '+game.away+' '+game.league).toLocaleLowerCase('pt-BR').includes(query)));
    $('#shown-count').textContent=matches.length+' partidas';
    let lastDay='';
    const items=matches.map(({game,index})=>{
      let group='';
      if(game.day!==lastDay){
        lastDay=game.day;
        const [yr,mo,dd]=String(game.day||'').split('-');
        group='<div class="match-day-separator"><span>'+esc(dd&&mo?dd+'/'+mo+'/'+yr:'Data não informada')+
          '</span><small>Horários do primeiro ao último • Brasília</small></div>';
      }
      return group+card(game,index);
    });
    $('#games').innerHTML=matches.length?items.join(''):'<div class="empty">Nenhum jogo encontrado com esses filtros. Tente outra combinação.</div>';
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
    const names=[['shots_on','Chutes no alvo'],['shots_off','Chutes para fora'],['shots_total','Chutes totais'],
      ['big_chances','Grandes chances'],['corners','Escanteios'],['dangerous_attacks','Ataques perigosos'],
      ['possession','Posse de bola (%)'],['xg','xG'],['yellow_cards','Cartões amarelos'],
      ['red_cards','Cartões vermelhos'],['fouls','Faltas'],['offsides','Impedimentos'],
      ['saves','Defesas'],['passes','Passes'],['pass_accuracy','Precisão de passe (%)']];
    const result=names.filter(([k])=>some(g,k)).map(([k,n])=>
      '<div class="scout"><strong>'+esc(g.stats?.home?.[k]??'—')+'</strong><span>'+n+'</span><strong>'+esc(g.stats?.away?.[k]??'—')+'</strong></div>');
    return result.length?'<div class="scout-table">'+result.join('')+'</div>':'<p class="small-note">Scouts não fornecidos nesta coleta.</p>';
  };
  const eventIcon={goal:'⚽',red_card:'🟥',yellow_card:'🟨',penalty_missed:'❌🥅',
    shot_on:'●',shot_off:'⊗'};
  const eventName={goal:'Gol',red_card:'Vermelho',yellow_card:'Amarelo',
    penalty_missed:'Pênalti perdido',shot_on:'Chute no gol',shot_off:'Chute fora'};
  const eventHTML=g=>{
    const events=Array.isArray(g.events)?g.events:[];
    if(!events.length)return '<p class="small-note">Sem eventos individuais confirmados para este jogo. Não preenchemos eventos imaginários.</p>';
    return '<div class="event-line">'+events.map(e=>
      '<div class="event-chip"><span class="event-icon '+(e.type==='shot_on'?'shot-on':e.type==='shot_off'?'shot-off':'')+'">'+
      (eventIcon[e.type]||'◉')+'</span><b>'+esc(e.m)+'′</b><span>'+
      esc(eventName[e.type]||e.type)+(e.side==='home'?' · Casa':e.side==='away'?' · Fora':'')+
      '</span><small>'+esc(e.text||'')+'</small></div>').join('')+'</div>';
  };
  const resultHTML=g=>{
    const o=g.outcomes||{};
    if(!o.correct_score)return '<p class="small-note">Mercados ainda sem liquidação: jogo não encerrado ou placar final não confirmado.</p>';
    const labels=[['over_15','Over 1.5 FT'],['over_25','Over 2.5 FT'],
      ['over_35','Over 3.5 FT'],['btts','Ambas marcam (BTTS)']];
    const indicators=labels.map(([k,name])=>'<span class="outcome '+(o[k]?'hit':'miss')+'">'+
      esc(name)+' · '+(o[k]?'SIM':'NÃO')+'</span>').join('');
    const result={home:'Casa',draw:'Empate',away:'Fora'};
    return '<div class="outcomes">'+indicators+
      '<span class="outcome">Match Odds: '+esc(result[o.result]||'—')+'</span>'+
      '<span class="outcome">Placar final: '+esc(o.correct_score)+'</span></div>'+
      '<p class="small-note">Resultado observado do mercado, não lucro de aposta. Para P/L, é necessária odd e entrada anterior ao jogo.</p>';
  };
  function drawAlerts(payload){
    const items=Array.isArray(payload.alerts)?payload.alerts:[];
    const box=$('#alert-feed');if(!box)return;
    $('#alert-count').textContent=items.length+' alertas';
    box.innerHTML=items.length?items.map((a,i)=>
      '<button type="button" class="alert-item" data-alert="'+i+'">'+
      '<b>'+esc(a.title)+'</b><small>'+esc(a.detail)+'</small>'+
      '<span>'+date(a.observed_at)+' · '+(a.kind==='ev_experimental'?'EV EXPERIMENTAL':a.kind==='odds_watch'?'ODDS MONITORADAS (SEM EV)':'MONITORAMENTO ESTATÍSTICO')+
      '</span></button>').join(''):
      '<p class="small-note">Nenhum alerta validado por enquanto. Sem probabilidade calibrada não existe EV+ demonstrado. Alertas de scouts não são recomendações de entrada.</p>';
    box.querySelectorAll('[data-alert]').forEach(el=>el.addEventListener('click',()=>{
      const alert=items[Number(el.dataset.alert)];
      const match=state.games.find(g=>g.id===alert.match_id&&g.day===alert.day);
      if(match)openMatch(match);
    }));
  }
  function drawHistory(payload){
    const box=$('#history-market-summary');if(!box)return;
    const doc=payload.market_history||{},rows=Array.isArray(doc.markets)?doc.markets:[];
    const count=Number(doc.matches)||0;
    $('#history-market-count').textContent=count+' jogos encerrados';
    box.innerHTML=rows.length?rows.map(r=>
      '<div class="history-market"><b>'+esc(r.market)+'</b><span>'+esc(r.occurred)+'/'+
      esc(r.matches)+'</span><strong>'+esc(r.rate_pct)+'%</strong></div>').join(''):
      '<p class="small-note">Aguardando jogos encerrados nos três dias anteriores.</p>';
  }
  function drawPaper(payload){
    const summary=payload.paper||{};
    const total=Number(summary.settled)||0;
    const box=$('#paper-pnl');if(!box)return;
    const pl=summary.paper_pl_u;
    const val=total && pl!=null && Number.isFinite(Number(pl))?
      (Number(pl)>=0?'+':'')+Number(pl).toFixed(2)+'u':'—';
    box.textContent=val;
    box.className='paper-value '+(total?(Number(pl)>=0?'pl-positive':'pl-negative'):'');
    $('#paper-settled').textContent=String(total);
    $('#paper-pending').textContent=String(summary.pending||0);
    const markets=Array.isArray(summary.markets)?summary.markets:[];
    $('#paper-market-lines').innerHTML=markets.length?markets.map(m=>
       '<div class="paper-market"><strong>'+esc(m.market==='1x2'?'Match Odds 1X2':m.market)+'</strong>'+
       '<span>'+esc(m.entries)+' operações · '+esc(m.wins)+' acertos</span><b>'+
       (Number(m.paper_pl_u)>=0?'+':'')+esc(Number(m.paper_pl_u).toFixed(2))+'u</b></div>').join(''):
       '<p class="small-note">Ainda não existem entradas experimentais liquidadas com odds pré-jogo verificadas. Sem lucro ou prejuízo mensurável.</p>';
  }
  function formHTML(g){
    const forms=g.form||{}, colors={V:'win',E:'draw',D:'loss'};
    return '<div class="team-form-grid">'+['home','away'].map(side=>{
      const d=forms[side]||{}, name=side==='home'?g.home:g.away;
      const games=Array.isArray(d.games)?d.games:[];
      const n=Number(d.available)||0;
      const sample=n?'<p class="small-note">'+
        esc(d.wins??'?')+'V · '+esc(d.draws??'?')+'E · '+esc(d.losses??'?')+
        'D · Gols '+esc(d.goals_for??'—')+'-'+esc(d.goals_against??'—')+
        ' · Over 2.5 '+esc(d.over25_pct??'—')+'% · BTTS '+esc(d.btts_pct??'—')+'%</p>':'';
      const items=games.map(m=>
        '<div class="form-match"><span class="form-result '+(colors[m.result]||'')+'">'+
        esc(m.result)+'</span><span class="form-opponent">'+esc(m.opponent)+
        '<small>'+esc(m.day)+' · '+esc(m.venue)+'</small></span><strong>'+
        esc(m.gf)+'-'+esc(m.ga)+'</strong></div>').join('');
      return '<div class="team-form"><h4>'+esc(name)+'</h4><p class="small-note">'+
        n+'/10 partidas anteriores encontradas · ESPN mesma competição'+
        (n<10?' · histórico incompleto':'')+'</p>'+sample+
        (items||'<p class="small-note">Sem histórico suficiente nesta fonte. Não completamos com placares fictícios.</p>')+
        '</div>';
    }).join('')+'</div>'+
    '<p class="small-note">Amostras anteriores ao início desta partida, não os 10 jogos da janela de três dias. Pode haver menos de 10 se a ESPN não fornecer o histórico da competição; forma histórica não comprova EV+.</p>';
  }
  function openMatch(g) {
    if(!g)return;
    if(window.NexusMatchDetail?.show(g))return;
    const oddLabels={home:'CASA',draw:'EMPATE',away:'FORA'};
    const odds=(g.odds||[]).map(v=>'<div class="odd-pill">'+esc(oddLabels[v.sel]||v.sel)+'<b>'+esc(v.odd)+'</b><small>'+esc(v.source||'Fonte')+' · '+date(v.at)+'</small></div>').join('');
    const trio=['home','draw','away'].map(sel=>(g.odds||[]).find(o=>o.sel===sel));
    const hasTrio=trio.every(o=>o&&Number(o.odd)>1);
    const marketMargin=hasTrio?(trio.reduce((n,o)=>n+1/Number(o.odd),0)-1)*100:null;
    const implied=hasTrio?'<div class="implied"><strong>Probabilidades implícitas nas odds</strong><div class="implied-grid">'+
      trio.map((o,i)=>'<div><small>'+esc(['CASA','EMPATE','FORA'][i])+'</small><b>'+
      (100/Number(o.odd)).toFixed(1)+'%</b></div>').join('')+'</div>'+
      '<p class="small-note">Soma das probabilidades: '+(100+marketMargin).toFixed(1)+'% · margem bruta: '+
      marketMargin.toFixed(1)+'%. Isso não é previsão de acerto nem EV+.</p></div>':'';
    const close=(g.closing_odds||[]).map(v=>'<div class="odd-pill">'+
      esc(oddLabels[v.sel]||v.sel)+'<b>'+esc(v.odd)+'</b><small>'+esc(v.bookmaker||'')+
      ' · Football-Data.co.uk · FECHAMENTO HISTÓRICO</small></div>').join('');
    const signals = (g.signals||[]).filter(s=>Number.isFinite(Number(s.ev_pct)) && Number.isFinite(Number(s.odds)));
    const signalRows = signals.map(s => '<div class="scout"><strong>'+esc(oddLabels[s.selection]||s.selection||'—')+'</strong><span>'+
      'EV estimado '+esc(s.ev_pct)+'% · p='+esc(s.probability)+'% · odd '+esc(s.odds)+'<br>'+
      esc(s.model||'Modelo experimental')+' · n='+esc(s.sample_size??'?')+' · '+esc(s.status||'pendente')+
      '</span><strong>'+((s.status==='settled')?((Number(s.paper_pl_u)>=0?'+':'')+esc(s.paper_pl_u)+'u'):'PENDENTE')+'</strong></div>').join('');
    $('#detail-content').innerHTML='<div class="detail-league">'+esc(g.league||'')+' · '+esc((g.sources||[g.source]).filter(Boolean).join(' / '))+'</div>'+
     '<div class="detail-score">'+escTitle(g)+' &nbsp; '+esc(g.score||'—')+'</div>'+
     '<p class="small-note">'+phaseLabel(g)+' · Início '+matchDate(g)+' às '+kickoff(g)+' (Brasília) · Última observação: '+date(g.observed_at)+
     (g.round?' · Rodada '+esc(g.round):'')+(g.venue?' · '+esc(g.venue):'')+'</p>'+
     '<h3 class="detail-title">▥ Termômetro · pressão registrada</h3>'+pressureHTML(pressure(g))+
     '<h3 class="detail-title">◉ Estatísticas confirmadas</h3>'+scouts(g)+
     '<h3 class="detail-title">▣ Últimos 10 jogos anteriores de cada equipe</h3>'+formHTML(g)+
     '<h3 class="detail-title">⚽ Eventos reais da partida</h3>'+eventHTML(g)+
     '<h3 class="detail-title">Mercados · resultado esportivo</h3>'+resultHTML(g)+
     '<h3 class="detail-title">◇ Odds 1X2 verificadas</h3>'+
     (odds?'<div class="odds-list">'+odds+'</div>':'<p class="small-note">Nenhuma cotação 1X2 pré-jogo capturada para esta partida.</p>')+implied+
     (close?'<h3 class="detail-title">Histórico · odds de fechamento (não utilizadas para EV+)</h3><div class="odds-list">'+close+
     '</div><p class="small-note">Cotações históricas coletadas depois do jogo; não são odds de entrada previamente registradas nem autorizam P/L simulado.</p>':'')+
     '<h3 class="detail-title">EV+ · modelo experimental público</h3>'+
     (signalRows?'<div class="scout-table">'+signalRows+'</div>':'<p class="small-note">EV+ indisponível: sem probabilidade validada e odds pré-jogo verificadas. Nenhuma aposta fictícia foi registrada.</p>')+
     '<h3 class="detail-title">Mercados possíveis de acompanhar</h3><p class="small-note">Over/Under, BTTS, Match Odds e Lay Correct Score requerem odds reais e critérios específicos. EV calculado não é lucro realizado, e um sinal experimental não valida lucratividade.</p>';
    $('#detail').showModal();
  }
  async function load() {
    $('#message').textContent='Consultando último arquivo da nuvem...';
    $('#message').className='notice';
    try {
      // Tenta o servidor privado primeiro; Cloudflare Pages serve apenas o JSON publico.
      let resp=null, obj=null;
      try {
        resp=await fetch('/api/dashboard',{cache:'no-store',credentials:'same-origin'});
        if(resp.ok) {
          obj=normalizePrivate(await resp.json());
          state.isPrivate=true;
        }
      } catch(_) { /* modo estatico, sem servidor privado */ }
      if(!obj) {
        state.isPrivate=false;
        resp=await fetch('./data.json?ts='+Date.now(),{cache:'no-store'});
        if(!resp.ok)throw Error('Dados ainda não publicados ('+resp.status+').');
        obj=await resp.json();
      }
      if(!obj || !Array.isArray(obj.games))throw Error('Formato inválido do arquivo.');
      state.payload=obj;
      state.games=obj.games.filter(x=>x&&typeof x.home==='string'&&typeof x.away==='string').sort(chronOrder);
      const days=[...new Set(state.games.map(g=>g.day).filter(Boolean))].sort().reverse();
      const picker=$('#day');const before=picker.value;
      picker.replaceChildren(new Option('Todos os dias','all'),...days.map(d=>new Option(d.split('-').reverse().join('/'),d)));
      picker.value=days.includes(before)?before:'all';state.day=picker.value;
      drawAlerts(obj);drawPaper(obj);drawHistory(obj);
      $('#last-updated').textContent=date(obj.exported_at);
      const extras=obj.source_status||{};
      const prov=extras.providers||{};
      const labels=[(obj.collector?.sources||[]).join(', ') || 'ESPN',
        extras.files_checked!=null?'Football-Data ('+Number(extras.files_checked||0)+' arquivos)':'',
        prov.OpenLigaDB?'OpenLigaDB ('+String(prov.OpenLigaDB)+')':'',
        prov.FotMob?'FotMob: '+(String(prov.FotMob).includes('tentativa')?'verificação':'disponível'):''];
      $('#last-source').textContent='Fontes: '+labels.filter(Boolean).join(' · ')+
        (extras.cross_verified?' · '+extras.cross_verified+' cruzamentos':'');
      $('#metric-games').textContent=state.games.length;
      $('#metric-live').textContent=state.games.filter(x=>x.phase==='live').length;
      $('#metric-pressure').textContent=state.games.filter(x=>pressure(x).length>0).length;
      $('#metric-odds').textContent=state.games.filter(hasOdds).length;
      const age=obj.exported_at ? Date.now()-new Date(obj.exported_at).getTime() : Infinity;
      if(!Number.isFinite(age) || age>4*3600000){
        $('#message').textContent='Atenção: dados com mais de 4 horas. Última exportação: '+date(obj.exported_at)+'. Não utilize para operações ao vivo.';
        $('#message').className='notice warn';
      } else {
        $('#message').textContent=(state.isPrivate?'Servidor privado autenticado. ':'Dados esportivos públicos. ')+'Coleta periódica (não são cotações ao vivo). '+(state.games.length===0?'Ainda não há jogos no arquivo.':'Última coleta: '+date(obj.exported_at)+'.');
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
  $('#day').addEventListener('change',ev=>{state.day=ev.target.value;render()});
  $('#market').addEventListener('change',ev=>{state.market=ev.target.value;render()});
  $('#refresh').addEventListener('click',load);
  $('#close-dialog').addEventListener('click',()=>$('#detail').close());
  $('#detail').addEventListener('click',ev=>{if(ev.target===$('#detail'))$('#detail').close()});
  load();
  setInterval(load,5*60*1000);
})();


/* Audit independent of sports feed: PRIVATE route; never copied into web/data.json */
(async function nexusBolsaPrivate(){
  const box=document.getElementById('bolsa-summary');
  const table=document.getElementById('bolsa-markets');
  const date=document.getElementById('bolsa-date');
  if(!box||!table)return;
  const money=v=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v)||0);
  const names={'OVER_UNDER_15':'Over/Under 1.5 FT','OVER_UNDER_25':'Over/Under 2.5 FT',
    'OVER_UNDER_35':'Over/Under 3.5 FT','OVER_UNDER_05':'Over/Under 0.5 FT',
    'FIRST_HALF_GOALS_05':'Over/Under 0.5 HT','FIRST_HALF_GOALS_15':'Over/Under 1.5 HT',
    'FIRST_HALF_GOALS_25':'Over/Under 2.5 HT','MATCH_ODDS':'Match Odds',
    'CORRECT_SCORE':'Correct Score','BOTH_TEAMS_TO_SCORE':'BTTS','HALF_TIME':'Resultado HT'};
  try {
    const result=await fetch('/api/dashboard',{credentials:'same-origin',cache:'no-store'});
    if(!result.ok)throw new Error('sem dados autorizados');
    const all=await result.json();
    const bolsa=all.bolsa||{};
    const rows=Array.isArray(bolsa.markets)?bolsa.markets:[];
    if(!rows.length)throw new Error('histórico ainda não disponível');
    document.getElementById('bolsa-private').hidden=false;
    box.textContent=String(bolsa.operations||0).replace(/\B(?=(\d{3})+(?!\d))/g,'.')+
      ' operações reais | P/L total: '+money(bolsa.net_pl);
    const d=new Date(bolsa.observed_at);
    date.textContent=Number.isNaN(d.getTime())?'sem horário':d.toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
    const t=document.createElement('table');
    t.style.cssText='width:100%;border-collapse:collapse;min-width:400px;font-size:13px';
    const head=document.createElement('tr');
    for(const name of ['Mercado','Operações','P/L líquido','Média/op.']){
      const th=document.createElement('th');
      th.textContent=name;th.style.cssText='text-align:left;color:#8ea5c3;padding:11px;border-bottom:1px solid #34465c';
      head.append(th);
    }
    t.append(head);
    for(const row of rows){
      const tr=document.createElement('tr');
      for(const val of [names[row.market]||row.market||'—',String(row.operations||0),money(row.net_pl),
        Number(row.operations)>0?money(Number(row.net_pl)/Number(row.operations)):'—']){
        const td=document.createElement('td');
        td.textContent=val;td.style.cssText='padding:10px;border-bottom:1px solid #34465c';
        if(val===money(row.net_pl))td.style.color=Number(row.net_pl)>=0?'#26d2a5':'#ff7f9a';
        tr.append(td);
      }
      t.append(tr);
    }
    table.replaceChildren(t);
  } catch(e){document.getElementById('bolsa-private').hidden=true;table.replaceChildren()}
})();
