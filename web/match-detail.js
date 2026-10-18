/* NEXUS SCORE — Match detail 6.0 | Painel esportivo, mobile-first.
   Nenhuma probabilidade, evento ou cotação é inventada. */
(function () {
  'use strict';
  const pt=(n) => String(n == null ? '—' : n);
  const entities={'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
  const esc=(v)=>pt(v).replace(/[&<>"']/g,(c)=>entities[c]);
  const percent=(v)=>Number.isFinite(Number(v)) ? Number(v).toFixed(0)+'%' : '—';
  const data=(v)=>{
    const d=new Date(v);return Number.isNaN(d.getTime())?'—':d.toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit'});
  };
  const kickoff=(v)=>{
    const num=Number(v);if(!Number.isFinite(num)||num<=0)return 'Horário indisponível';
    return new Date(num*1000).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  };
  const logo=(url,name)=>{
    const safe=typeof url==='string' &&
      (/^https:\/\/a1?\.espncdn\.com\/i\/teamlogos\//.test(url) ||
       /^https:\/\/images\.fotmob\.com\/image_resources\/logo\/teamlogo\/\d{1,12}\.png$/.test(url));
    return '<span class="md-crest">'+(safe?'<img src="'+esc(url)+'" alt="'+esc('Escudo do '+name)+'" loading="lazy" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'block\'">':'')+
      '<span class="md-crest-fallback"'+(safe?' style="display:none"':'')+'>'+esc(String(name||'?').slice(0,2).toUpperCase())+'</span></span>';
  };
  const source=(g)=>Array.from(new Set((g.sources||[g.source]).filter(Boolean))).join(' · ')||'Fonte não informada';
  const currentState=(g)=>g.phase==='live'?'AO VIVO · '+(g.minute||'—')+'′':g.phase==='finished'?'ENCERRADO':'PRÉ-JOGO';
  const stats=[
    ['shots_on','Finalizações no gol'],['shots_off','Finalizações para fora'],
    ['shots_total','Chutes totais'],['big_chances','Grandes chances'],
    ['corners','Escanteios'],['dangerous_attacks','Ataques perigosos'],
    ['possession','Posse de bola (%)'],['xg','Gols esperados (xG)'],
    ['yellow_cards','Cartões amarelos'],['red_cards','Cartões vermelhos'],
    ['fouls','Faltas'],['offsides','Impedimentos'],
    ['saves','Defesas'],['passes','Passes'],['pass_accuracy','Precisão passes (%)']
  ];
  const eventNames={goal:'Gol',shot_on:'Chute no alvo',shot_off:'Chute para fora',
    penalty_missed:'Pênalti perdido',yellow_card:'Amarelo',red_card:'Vermelho'};
  const eventIcons={goal:'⚽',shot_on:'●',shot_off:'⊗',penalty_missed:'❌🥅',yellow_card:'🟨',red_card:'🟥'};
  let game=null,tab='thermo';
  const tabs=[['thermo','Termômetro'],['stats','Estatísticas'],['projections','Projeções'],
    ['form','Confronto'],['squads','Elencos'],['indicators','Indicadores'],['markets','Mercados']];
  const noData=(txt)=>'<p class="md-empty">'+esc(txt)+'</p>';
  const number=(v)=>v!=null && Number.isFinite(Number(v)) ? Number(v) : null;
  const paired=(g,key)=>{
    const h=number((g.stats||{}).home && g.stats.home[key]);
    const a=number((g.stats||{}).away && g.stats.away[key]);
    return [h,a];
  };
  const topStats=(g)=>{
    const chosen=['shots_on','shots_off','corners','big_chances','possession'];
    const rows=chosen.filter(k=>paired(g,k).some(x=>x!==null));
    return rows.length?'<div class="md-quick-grid">'+rows.slice(0,4).map(key=>{
      const name=(stats.find(s=>s[0]===key)||[])[1]||key;
      const x=paired(g,key);
      return '<div class="md-quick"><small>'+esc(name)+'</small><strong>'+esc(x[0]===null?'—':x[0])+' <i>×</i> '+esc(x[1]===null?'—':x[1])+'</strong></div>';
    }).join('')+'</div>':'';
  };
  function chart(g){
    const points=(Array.isArray(g.pressure)?g.pressure:[]).filter(p=>Number.isFinite(Number(p.m))&&Number.isFinite(Number(p.v))&&Number(p.m)>=0&&Number(p.m)<=135);
    const events=(Array.isArray(g.events)?g.events:[]).filter(e=>Number.isFinite(Number(e.m))&&Number(e.m)>=0&&Number(e.m)<=135);
    if(!points.length&&!events.length){
      const state=g?.momentum_diagnostic?.state;
      const reason=state==='not_provided'?'A fonte informou que não disponibiliza pressão minuto a minuto nesta partida.':
        state==='missing'?'A fonte consultada não disponibilizou a curva de pressão nesta coleta.':
        state==='unsupported_shape'?'O formato da curva mudou e os valores ainda não foram validados.':
        state==='no_valid_points'?'A resposta trouxe dados de pressão sem valores válidos.':
        'Ainda não há pressão por minuto nem eventos individuais confirmados nesta partida.';
      return noData(reason);
    }
    const end=Math.max(90, ...points.map(p=>Number(p.m)), ...events.map(e=>Number(e.m)));
    const scale=end>90?135:90;
    const values=new Map(points.map(p=>[Math.round(Number(p.m)),Math.max(-100,Math.min(100,Number(p.v)))]));
    const marks=Array.from({length:scale},(_,i)=>{
      const m=i+1,v=values.has(m)?values.get(m):null;
      const h=v===null?0:Math.max(2,Math.abs(v)*.39);
      return '<span class="md-bar'+(v===null?' md-missing':v<0?' md-visitor':' md-home')+
        '" style="--h:'+h.toFixed(2)+'%"></span>';
    }).join('');
    const used={};
    const compact=window.NexusUpgrade?.groupEvents ? window.NexusUpgrade.groupEvents(events.slice(0,130)) : events.slice(0,130);
    const markerHTML=compact.map(e=>{
      const m=Math.max(0,Math.min(scale,Number(e.m)));
      const side=e.side==='home'?'home':e.side==='away'?'away':'unknown';
      const type=eventIcons[e.type]?e.type:'other';
      const key=side+'-'+Math.floor(m/3);
      const shift=used[key]||0;used[key]=shift+1;
      const height=(shift%3)*16;
      const label=(eventNames[e.type]||'Evento')+' · '+m+'′ · '+(e.text||'');
      return '<span class="md-event md-event-'+esc(type)+' md-side-'+side+
        '" style="left:'+(m/scale*100).toFixed(2)+'%;--stack:'+height+'px" title="'+esc(label)+
        '" aria-label="'+esc(label)+'">'+(eventIcons[e.type]||'•')+(e.count>1?'<sup>'+esc(window.NexusUpgrade.exponent(e.count))+'</sup>':'')+'</span>';
    }).join('');
    const ticks=[0,15,30,45,60,75,90];
    if(scale===135)ticks.push(105,120,135);
    const axes=ticks.map(n=>'<span style="left:'+(n/scale*100)+'%">'+n+'′</span>').join('');
    const period=scale===90?50:(45/scale*100);
    return '<div class="md-chart-head"><span><b class="md-swatch md-green"></b>Mandante acima</span>'+
      '<span><b class="md-swatch md-purple"></b>Visitante abaixo</span></div>'+
      '<div class="md-pressure-wrap"><div class="md-pressure-plot" role="img" aria-label="'+
      esc('Termômetro de pressão com '+points.length+' minutos observados e '+events.length+' eventos confirmados')+'">'+
      '<div class="md-upper"></div><div class="md-lower"></div><div class="md-zero"></div>'+
      '<div class="md-bars">'+marks+'</div><span class="md-ht" style="left:'+period+'%">INTERVALO</span>'+
      '<div class="md-events">'+markerHTML+'</div></div><div class="md-scale">'+axes+'</div></div>'+
      '<div class="md-chart-foot"><span>'+points.length+' minutos observados</span>'+
      '<span>'+events.length+' eventos confirmados</span></div>';
  }
  function scoutHistory(g){
    const rows=(Array.isArray(g.scout_snapshots)?g.scout_snapshots:[])
      .filter(s=>s&&Number.isInteger(Number(s.m))&&Number(s.m)>=1&&Number(s.m)<=130&&
        Number.isFinite(Date.parse(s.at))&&s.stats&&typeof s.stats==='object')
      .sort((a,b)=>Date.parse(a.at)-Date.parse(b.at)||Number(a.m)-Number(b.m));
    if(!rows.length){
      return noData('Ainda não há capturas cronológicas de scouts para esta partida. Números acumulados continuam na aba Estatísticas.');
    }
    const latest=rows[rows.length-1], labels=[
      ['shots_on','No gol'],['shots_off','Para fora'],['corners','Escanteios'],
      ['big_chances','Grandes chances'],['xg','xG']
    ];
    const num=(item,side,field)=>number(item?.stats?.[side]?.[field]);
    const headline='<p class="md-muted">Valores acumulados registrados na coleta; o minuto informado é o da observação, não o momento exato de cada chute.</p>'+
      '<div class="md-quick-grid">'+labels.filter(([key])=>num(latest,'home',key)!==null||
      num(latest,'away',key)!==null).map(([key,label])=>
        '<div class="md-quick"><small>'+esc(label)+'</small><strong>'+
        esc(num(latest,'home',key)??'—')+' <i>×</i> '+
        esc(num(latest,'away',key)??'—')+'</strong></div>').join('')+'</div>'+
      '<p class="md-muted">Observado aos '+esc(latest.m)+'′ · '+esc(data(latest.at))+
      ' BRT · '+esc(latest.source||'Fonte')+' · '+rows.length+' captura(s)</p>';
    const intervals=[];
    for(let i=Math.max(1,rows.length-7);i<rows.length;i++){
      const prev=rows[i-1],now=rows[i];
      if(Number(now.m)<=Number(prev.m))continue;
      const changes=[];
      for(const [field,label] of labels){
        if(field==='xg')continue;
        const home=num(now,'home',field),h0=num(prev,'home',field);
        const away=num(now,'away',field),a0=num(prev,'away',field);
        if(home!==null&&h0!==null&&home>=h0&&home>h0)
          changes.push(esc(label)+' casa +'+(home-h0));
        if(away!==null&&a0!==null&&away>=a0&&away>a0)
          changes.push(esc(label)+' fora +'+(away-a0));
      }
      intervals.push('<div class="md-event-row"><span class="md-event-time">'+
        esc(prev.m)+'′–'+esc(now.m)+'′</span><span>'+
        (changes.length?changes.join(' · '):'Sem aumento confirmável dos campos comparáveis')+
        '</span></div>');
    }
    return headline+(intervals.length?
      '<p class="md-muted">Variação ENTRE capturas; não atribuímos o evento a um minuto individual.</p>'+
      '<div class="md-events-list">'+intervals.join('')+'</div>':'');
  }
  function eventsList(g){
    const events=(Array.isArray(g.events)?g.events:[]);
    if(!events.length)return noData('Sem registro individual de chutes, cartões ou gols nesta coleta.');
    return '<div class="md-events-list">'+events.map(e=>'<div class="md-event-row">'+
      '<span class="md-event-time">'+esc(e.m)+'′</span><span class="md-event-symbol md-event-'+esc(e.type)+'">'+
      (eventIcons[e.type]||'•')+'</span><span><b>'+esc(eventNames[e.type]||e.type)+'</b>'+
      '<small>'+esc(e.side==='home'?g.home:e.side==='away'?g.away:'Equipe não identificada')+
      (e.type==='goal' && !e.text && !e.player?' · Autor não identificado pela fonte':'')+
      (e.type==='goal' && e.player?' · '+esc(e.player):'')+
      (e.text?' · '+esc(e.text):'')+
      (e.type==='goal'&&e.assist?' · Assistência: '+esc(e.assist):'')+
      (e.type==='goal'&&e.own_goal?' · Gol contra':'')+
      '</small></span></div>').join('')+'</div>';
  }
  function statistics(g){
    const available=stats.filter(([key])=>paired(g,key).some(v=>v!==null));
    if(!available.length)return noData('Scouts indisponíveis nesta coleta. Não usamos números estimados como se fossem reais.');
    return '<p class="md-muted">Estatísticas observadas de '+esc(g.stats_source||g.source||'fonte disponível')+
      (g.stats_observed_at?' · última coleta '+esc(g.stats_observed_at):'')+
      '. Campos ausentes ficam sem valor; não são transformados em zero.</p>'+
      '<div class="md-stats-head"><span>'+logo(g.home_logo,g.home)+' Casa</span><span>Fora '+logo(g.away_logo,g.away)+'</span></div>'+
      available.map(([key,label])=>{
        const [h,a]=paired(g,key), left=h===null?'—':h,right=a===null?'—':a;
        const max=Math.max((h||0)+(a||0),1);
        const hp=h!==null?(h/max*100):0,ap=a!==null?(a/max*100):0;
        return '<div class="md-stat-row"><div class="md-stat-values"><b>'+esc(left)+'</b><span>'+esc(label)+'</span><b>'+esc(right)+'</b></div>'+
          '<div class="md-stat-bars"><div class="md-stat-left"><i style="width:'+hp.toFixed(1)+'%"></i></div>'+
          '<div class="md-stat-right"><i style="width:'+ap.toFixed(1)+'%"></i></div></div></div>';
      }).join('');
  }
  const formSummary=(f)=>{
    if(!f||!Number(f.available))return '<small>Sem histórico suficiente</small>';
    return '<div class="md-form-summary"><span><b>'+esc(f.wins??'—')+'</b> V</span><span><b>'+
      esc(f.draws??'—')+'</b> E</span><span><b>'+esc(f.losses??'—')+'</b> D</span></div>'+
      '<div class="md-form-rate">Média gols '+esc(f.avg_goals_for??'—')+' / '+esc(f.avg_goals_against??'—')+
      ' · Over 2.5 '+percent(f.over25_pct)+' · BTTS '+percent(f.btts_pct)+'</div>';
  };
  function form(g){
    return '<div class="md-form-grid">'+['home','away'].map(side=>{
      const f=(g.form||{})[side]||{},name=g[side],games=Array.isArray(f.games)?f.games.slice(0,10):[];
      return '<article class="md-form-team"><div class="md-team-row">'+logo(g[side+'_logo'],name)+
        '<div><b>'+esc(name)+'</b><small>'+esc(f.available||0)+' de 10 jogos anteriores · '+esc(f.source||'fonte não informada')+'</small></div></div>'+
        formSummary(f)+(games.length?'<div class="md-form-list">'+games.map(item=>
        '<div class="md-form-game"><span class="md-form-result md-result-'+esc(item.result)+'">'+
        esc(item.result)+'</span><span>'+esc(item.opponent)+'<small>'+esc(item.day)+
        ' · '+esc(item.venue)+'</small></span><b>'+esc(item.gf)+'–'+esc(item.ga)+'</b></div>').join('')+'</div>':
        noData('Nenhum resultado anterior verificado para esta equipe na fonte conectada.'))+'</article>';
    }).join('')+'</div>';
  }
  function squads(g){
    const lineups=g.lineups||{};
    const details=['home','away'].map(side=>{
      const team=g[side],lineup=lineups[side]||null,groups=(g.roster||{})[side]||[];
      const heading='<div class="md-team-row">'+logo(g[side+'_logo'],team)+'<b>'+esc(team)+'</b></div>';
      const leaders=(g.team_leaders||{})[side]||{};
      const star=(g.match_stars||{})[side]||{};
      const badges=['goals','assists','rating'].map(key=>{
        const x=leaders[key];return x?.name?'<p class="md-muted">'+
          esc(key==='goals'?'⚽ Artilheiro':key==='assists'?'🅰 Assistências':'⭐ Nota da temporada')+
          ': '+esc(x.name)+' · '+esc(x.value)+'</p>':'';
      }).join('');
      const missing= !leaders.goals?.name&&!leaders.assists?.name&&!star.player?'<p class="md-muted">Artilheiro, líder de assistências ou destaque não confirmados nesta coleta.</p>':'';
      const highlight=star.player?'<p class="md-muted">★ '+esc(star.label)+
        ': '+esc(star.player)+'</p>':'';
      if(lineup&&(lineup.starters||[]).length){
        const formation=lineup.formation?' · Formação '+esc(lineup.formation):'';
        const section=(name,players)=>'<div class="md-roster-section"><h4>'+esc(name)+'</h4>'+
          players.map(p=>'<div class="md-roster-player"><b>'+esc(p.number||'•')+
          '</b><span>'+esc(p.name)+'</span></div>').join('')+'</div>';
        return '<article class="md-form-team">'+heading+badges+highlight+missing+
          '<p class="md-muted">'+esc(lineup.status==='confirmed'?'Escalação OFICIAL':'Escalação não confirmada')+
          ' · FotMob'+formation+'. Sem saída registrada não garante presença atual.</p>'+
          section(lineup.status==='confirmed'?'Titulares confirmados':'Jogadores informados (não confirmados)',lineup.starters||[])+
          ((lineup.subs||[]).length?section('Reservas',lineup.subs):'')+'</article>';
      }
      if(!groups.length)return '<article class="md-form-team">'+heading+badges+highlight+
        noData('Elenco ou escalação não disponível na coleta desta equipe.')+'</article>';
      return '<article class="md-form-team">'+heading+badges+highlight+
        groups.map(group=>'<div class="md-roster-section"><h4>'+esc(group.section)+'</h4>'+
          (group.players||[]).map(p=>'<div class="md-roster-player"><b>'+esc(p.number||'•')+
          '</b><span>'+esc(p.name)+'</span></div>').join('')+'</div>').join('')+'</article>';
    });
    return '<div class="md-note">Escalação quando fornecida pelo FotMob; caso contrário, elenco geral do clube. Plantel não significa escalação titular confirmada.</div>'+
      '<div class="md-form-grid">'+details.join('')+'</div>';
  }
  function projections(g){
    const f=(g.form||{}),h=f.home||{},a=f.away||{};
    if(!h.available&&!a.available)return noData('Para projeções confiáveis precisamos de amostras históricas dos dois times. Não há modelo probabilístico validado para esta partida.');
    return '<div class="md-note">Indicadores descritivos dos últimos jogos disponíveis; não são probabilidades calibradas, EV+ ou recomendação de aposta.</div>'+
      '<div class="md-proj-grid">'+['home','away'].map(side=>{
        const obj=f[side]||{};
        return '<div class="md-proj-card"><strong>'+esc(g[side])+'</strong><small>Amostra '+esc(obj.available||0)+'/10</small>'+
        '<div>Over 2.5 <b>'+percent(obj.over25_pct)+'</b></div><div>BTTS <b>'+percent(obj.btts_pct)+'</b></div>'+
        '<div>Gols/jogo <b>'+esc(obj.avg_goals_for??'—')+'</b></div></div>';
      }).join('')+'</div>';
  }
  function odds(g){
    const kickoff=Number(g.start_timestamp);
    const list=(g.odds||[]).filter(x=>{
      const price=Number(x.odd),at=Date.parse(x.at||x.captured_at||'');
      return Number.isFinite(price)&&price>1&&price<1000&&
        Number.isFinite(at)&&Number.isFinite(kickoff)&&kickoff>0&&at<kickoff*1000&&
        !!(x.bookmaker||x.source);
    });
    const historical=(g.closing_odds||[]).filter(x=>Number(x.odd)>1);
    const label={home:'Casa',draw:'Empate',away:'Fora'};
    const format=(items,mode)=>items.map(o=>
      '<div class="md-odd"><small>'+esc(label[o.sel]||o.sel)+'</small><b>'+esc(o.odd)+'</b>'+
      '<span>'+esc(o.bookmaker||o.source||'Fonte')+' · '+esc(o.at||o.captured_at||'horário não informado')+'</span></div>').join('');
    return '<div class="md-subtitle">Cotações pré-jogo registradas</div>'+
      (list.length?'<div class="md-odds">'+format(list)+'</div>':noData('Nenhuma odd pré-jogo verificada nesta partida (exige fonte, horário anterior ao início e preço íntegro).'))+
      (historical.length?'<div class="md-subtitle">Odds históricas de fechamento · não são preços atuais</div>'+
      '<div class="md-odds">'+format(historical)+'</div>'+
      '<p class="md-muted">Não foram observadas como entrada pré-jogo e não compõem P/L experimental.</p>':'');
  }
  function outcomes(g){
    const o=g.outcomes||{};
    if(!o.correct_score)return noData('Mercados pendentes até a confirmação do placar final.');
    const sh=g.home_score==null?null:Number(g.home_score),sa=g.away_score==null?null:Number(g.away_score);
    const margin=g.phase==='finished'&&Number.isFinite(sh)&&Number.isFinite(sa)?Math.abs(sh-sa):null;
    const items=[['Over 1.5 FT',o.over_15],['Over 2.5 FT',o.over_25],
      ['Over 3.5 FT',o.over_35],['BTTS — Sim',o.btts],...(margin===null?[]:[['Lay goleada (margem 3+)',margin<3]])];
    return '<div class="md-market-grid">'+items.map(([name,hit])=>
      '<div class="md-market '+(hit?'md-hit':'md-miss')+'"><small>'+name+'</small><b>'+(hit?'SIM':'NÃO')+'</b></div>'
      ).join('')+'</div><p class="md-muted">Lay goleada aqui é uma regra descritiva: contra vitória por 3+ gols de diferença. Resultado do mercado, não P/L de uma operação executada. Não representa odd de Lay, lucro ou aposta executada.</p>';
  }
  function mustWin(g){
 const m=g.must_win||g.mustWin||null;
 if(!m||typeof m!=='object'||!m.source||!m.table_verified){
  return '<div class="md-note">Must Win: indisponível sem classificação verificada e contexto competitivo; não inferir urgência pela posição isolada.</div>';
 }
 return '<div class="md-note">Must Win · '+esc(m.label||m.status||'Contexto disponível')+
   ' · Fonte '+esc(m.source)+' · '+esc(m.updated_at||'data não informada')+
   '</div>';
}
function indicators(g){
    const entries=Array.isArray(g.signals)?g.signals:[];
    const validated=entries.filter(signal=>{
      const ev=Number(signal.ev_pct),price=Number(signal.odds);
      const captured=Date.parse(signal.captured_at||signal.at||'');
      const kickoff=Number(g.start_timestamp);
      return signal.model_calibrated===true&&signal.odds_verified===true&&
        Number.isFinite(ev)&&Number.isFinite(price)&&price>1&&price<1000&&
        Number.isFinite(captured)&&Number.isFinite(kickoff)&&kickoff>0&&
        captured<kickoff*1000;
    });
    const head=mustWin(g)+'<div class="md-note">EV+ exige probabilidade validada e odd registrada antes da entrada. O resultado de mercado, sozinho, não comprova valor esperado.</div>';
    if(!validated.length)return head+noData('Nenhum sinal com modelo calibrado, preço verificado e captura anterior ao início; sinais experimentais não são rotulados como EV+ validado.');
    return head+validated.map(s=>'<div class="md-signal"><b>'+esc(s.selection||'Mercado')+'</b>'+
       '<span>Odd '+esc(s.odds)+' · EV estimado '+esc(s.ev_pct)+'% · Amostra '+esc(s.sample_size||'—')+
       '</span><small>'+esc(s.status||'Pendente')+
       (s.paper_pl_u!=null?' · Teste '+esc(s.paper_pl_u)+'u':'')+'</small></div>').join('');
  }
  function bodyFor(g,t){
    if(t==='thermo')return chart(g)+'<h3 class="md-subtitle">Scouts observados e evolução</h3>'+scoutHistory(g)+'<h3 class="md-subtitle">Resumo do jogo</h3>'+topStats(g)+
      '<h3 class="md-subtitle">Eventos confirmados</h3>'+eventsList(g);
    if(t==='stats')return statistics(g);
    if(t==='projections')return projections(g);
    if(t==='form')return form(g);
    if(t==='squads')return squads(g);
    if(t==='indicators')return indicators(g);
    if(t==='markets')return outcomes(g)+'<h3 class="md-subtitle">Odds verificadas</h3>'+odds(g);
    return '';
  }
  function select(t){
    if(!game||!tabs.some(x=>x[0]===t))return;
    tab=t;
    const panel=document.getElementById('md-content');
    if(!panel)return;
    panel.innerHTML=bodyFor(game,tab);
    const controls=document.querySelectorAll('.md-tab');
    controls.forEach(btn=>{
      const active=btn.dataset.tab===tab;btn.classList.toggle('active',active);
      btn.setAttribute('aria-selected',String(active));
      btn.tabIndex=active?0:-1;
    });
    const section=document.getElementById('md-scroll');
    if(section)section.scrollTop=0;
  }
  function show(g){
    const dialog=document.getElementById('detail'),slot=document.getElementById('detail-content');
    if(!dialog||!slot||!g)return false;
    game=g;tab='thermo';
    slot.innerHTML='<div class="md-shell"><div class="md-sticky"><div class="md-topline"><span>'+
      esc(g.league||'Campeonato')+(g.round?' · '+esc(g.round):'')+'</span>'+
      '<span class="md-match-status '+(g.phase==='live'?'md-status-live':'')+'">'+esc(currentState(g))+'</span></div>'+
      '<div class="md-scoreboard"><div class="md-club">'+logo(g.home_logo,g.home)+'<b>'+esc(g.home)+'</b></div>'+
      '<div class="md-scorebox"><strong>'+esc(g.phase==='scheduled'?'×':g.score||'—')+
      '</strong><span>'+esc(g.phase==='live'?'EM ANDAMENTO':g.phase==='finished'?'FINAL':'AGENDADO')+
      '</span></div><div class="md-club">'+logo(g.away_logo,g.away)+'<b>'+esc(g.away)+'</b></div></div>'+
      '<div class="md-meta"><span>◷ '+esc(kickoff(g.start_timestamp))+' · BRT</span>'+
      '<span>Fonte: '+esc(source(g))+'</span></div>'+
      '<div class="md-tabs" role="tablist" aria-label="Dados da partida">'+tabs.map(([key,name])=>
      '<button class="md-tab" type="button" role="tab" data-tab="'+key+'" aria-selected="false">'+name+'</button>'
      ).join('')+'</div></div><div id="md-scroll" class="md-scroll"><section id="md-content" role="tabpanel"></section>'+
      '<p class="md-disclaimer">Dados públicos sujeitos a atraso. Pressão, scouts e eventos só aparecem quando registrados; sem informação inventada.</p></div></div>';
    if(!dialog.open)dialog.showModal();
    slot.querySelectorAll('.md-tab').forEach(btn=>btn.addEventListener('click',()=>select(btn.dataset.tab)));
    select('thermo');
    return true;
  }
  window.NexusMatchDetail={show,select,scoutHistory};
})();