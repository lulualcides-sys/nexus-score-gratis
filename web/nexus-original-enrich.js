/* NEXUS 5.29 original web — ligação das leituras reais ao motor de interface.
 * Transporta para navegador as regras do engine.py e prelive.py 5.29.
 * Nenhum scout acumulado é colocado em minuto fictício do gráfico.
 */
(function(){
'use strict';
const previous=window.fetch.bind(window);
const bridge=window.NexusWebBridge;
if(!bridge)return;
const safeNumber=x=>x!==null&&x!==undefined&&x!==''&&Number.isFinite(+x)?+x:null;
const cap=(v,min,max)=>Math.max(min,Math.min(max,v));
const round=(v,n=1)=>Number(v.toFixed(n));
const titleFrom={'🧨':'Pressão total','🔥':'Pressão forte','🎯':'Precisão ofensiva',
'🚩':'Cerco por escanteios','⚡':'Pressão ofensiva','💣':'Chance grande',
'⚔️':'Ataques perigosos','🧠':'Value / preço justo','🟥':'Expulsão',
'⏱️':'Tensão tardia','🥶':'Jogo frio','🚨':'Gol próximo (alerta)'};
const iconLabels={'goal':'⚽','penalty_missed':'❌🥅','yellow_card':'🟨',
'red_card':'🟥','shot_on':'🥅','shot_off':'↗️','big_chance_missed':'💣❌'};
const isMatchURL=p=> /^\/api\/(?:match|prelive)\//.test(p);
function samplesFrom(g){
  return [...(g.pressure||[])].map(v=>({minute:safeNumber(v.m),value:safeNumber(v.v)}))
    .filter(v=>v.minute!==null&&v.value!==null&&v.minute>=1&&v.minute<=150&&Math.abs(v.value)<=1000)
    .sort((a,b)=>a.minute-b.minute).reduce((out,item)=>{
       const i=out.findIndex(p=>p.minute===item.minute);
       if(i<0)out.push(item);else out[i]=item;return out;
    },[]);
}
// Copia do criterio de cobertura/intensidade do modulo original free_match_data.thermometer.
function pressureWindow(points,end,n){
  const map=new Map(points.filter(p=>p.minute<=end&&p.minute>end-n).map(p=>[p.minute,p.value]));
  const observed=[...map.values()],expected=Math.min(n,Math.max(1,end));
  if(observed.length<Math.ceil(expected*.8)||!observed.length){
    return {valid:false,score:null,level:'SEM DADOS',dominant:'SEM DADOS',
      difference:null,home_recent:null,away_recent:null,samples:observed.length,expected};
  }
  const h=observed.reduce((a,v)=>a+Math.max(0,v),0)/observed.length;
  const a=observed.reduce((a,v)=>a+Math.max(0,-v),0)/observed.length;
  const intensity=Math.max(h,a),diff=Math.abs(h-a);
  const level=intensity>=62&&diff>=18?'CRITICO':intensity>=43&&diff>=12?'FORTE':intensity>=25?'OBSERVAR':'FRIO';
  const team=h>a+2?'HOME':a>h+2?'AWAY':'EQUILIBRADO';
  return {valid:true,score:Math.round(cap(intensity/80*100,0,100)),level,
    dominant:team,difference:round(diff),home_recent:round(h),
    away_recent:round(a),samples:observed.length,expected};
}
function buildBoard(ten,five,stats,events,end){
  const out=[];
  const add=(emoji,active,available,reason,team=null)=>out.push({emoji,
    name:titleFrom[emoji],state:available?(active?'active':'inactive'):'unavailable',
    reason:String(reason),rule:ruleText[emoji],team});
  const high=['FORTE','CRITICO'].includes(ten.level);
  const picked=['HOME','AWAY'].includes(ten.dominant)?ten.dominant:null;
  add('🧨',high&&five.score!==null&&five.score>=65,ten.valid&&five.valid,
     'Pressão 10 min '+(ten.score??'—')+' / 5 min '+(five.score??'—')+' (mín. 65 na janela curta)',picked);
  add('🔥',high,ten.valid,'Janela observada 10 min: '+ten.level,picked);
  function stat(emoji,name,threshold,label){
    const values=['home','away'].map(s=>({side:s,value:safeNumber(stats[s]?.[name])})).filter(x=>x.value!==null);
    const top=values.sort((a,b)=>b.value-a.value)[0];
    add(emoji,!!top&&top.value>=threshold,!!top,
      top?top.side.toUpperCase()+': '+top.value+' '+label+' (limiar ≥'+threshold+')':'Fonte sem '+label,
      top?top.side.toUpperCase():null);
  }
  stat('🎯','shots_on',5,'chutes no alvo');
  stat('🚩','corners',6,'escanteios');
  add('⚡',['OBSERVAR','FORTE','CRITICO'].includes(ten.level) && ten.difference!==null&&ten.difference>=18,
       ten.valid,'Diferença real '+(ten.difference??'—')+' em 10 minutos; regra ≥18',picked);
  stat('💣','big_chances',3,'chances claras');
  stat('⚔️','dangerous_attacks',25,'ataques perigosos');
  add('🧠',false,false,'Sem probabilidade calibrada e odds pré-entrada não é possível confirmar EV+');
  const reds=['home','away'].map(s=>safeNumber(stats[s]?.red_cards)).filter(v=>v!==null);
  const redHit=events.some(e=>e.type==='red_card')||reds.some(n=>n>=1);
  add('🟥',redHit,reds.length>0||events.length>0,redHit?'Expulsão registrada':'Sem expulsão registrada nos dados disponíveis');
  add('⏱️',end>=70&&high,ten.valid&&end>0,'Minuto '+end+' e pressão 10 min: '+ten.level,picked);
  add('🥶',ten.level==='FRIO',ten.valid,'Janela de pressão real: '+ten.level,picked);
  const own=stats[(picked||'').toLowerCase()]||{};
  const sot=safeNumber(own.shots_on),big=safeNumber(own.big_chances);
  const available=ten.valid&&five.valid&&picked!==null&&sot!==null&&big!==null;
  const alarm=available&&high&&ten.score>=70&&five.score>=65&&sot>=3&&big>=1;
  add('🚨',alarm,available,'Pressão real 10min '+(ten.score??'—')+
    ', 5min '+(five.score??'—')+', chutes no alvo '+(sot??'—')+
    ', chances claras '+(big??'—')+'; alerta heurístico, não P(gol)',picked);
  return out;
}
const ruleText={
'🧨':'10 minutos com pressão FORTE/CRÍTICA + intensidade de 5 minutos ≥65',
'🔥':'Janela de 10 minutos FORTE ou CRÍTICA, com ≥80% de minutos observados',
'🎯':'Chutes no alvo acumulados ≥5, sem atribuir minuto ao total',
'🚩':'Escanteios totais ≥6, sem atribuir minuto ao total',
'⚡':'Diferença de intensidade ≥18 e pressão no mínimo OBSERVAR',
'💣':'Grandes chances acumuladas ≥3; sem inferir minutos',
'⚔️':'Ataques perigosos acumulados ≥25; sem inferir minutos',
'🧠':'Odd real antes da entrada + probabilidade calibrada + custos',
'🟥':'Cartão vermelho confirmado pela fonte',
'⏱️':'Minuto ≥70 e pressão 10min FORTE/CRÍTICA',
'🥶':'Pressão 10min FRIA verificada',
'🚨':'Pressão FORTE, P10 ≥70, P5 ≥65, chutes no alvo ≥3 e chances ≥1 do lado dominante'
};
function headToHead(g){
 const norm=v=>String(v||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
   .toLowerCase().replace(/\b(?:f\.?c\.?|s\.?c\.?|club|clube)\b/g,'')
   .replace(/[^a-z0-9]+/g,' ').trim().replace(/\s+/g,' ');
 const found=new Map();
 // Confrontos diretos recuperados no exportador de históricos da fonte.
 for(const match of (g.head_to_head||[])){
   if(!match||!/^\d{1,2}-\d{1,2}$/.test(String(match.score||'')))continue;
   const home=norm(match.home),away=norm(match.away);
   const direct=home===norm(g.home)&&away===norm(g.away);
   const reverse=home===norm(g.away)&&away===norm(g.home);
   if(!direct&&!reverse)continue;
   const key=[match.date||'',home,away,match.score].join('|');
   found.set(key,{date:match.date,home:match.home,away:match.away,
     score:match.score,competition:match.competition||g.league||'',source:match.source||'FotMob'});
 }
 for(const side of ['home','away']){
   const other=side==='home'?'away':'home';
   for(const m of g.form?.[side]?.games||[]){
     if(norm(m.opponent)!==norm(g[other]))continue;
     if(!['Casa','Fora'].includes(m.venue))continue;
     const gf=safeNumber(m.gf),ga=safeNumber(m.ga);
     if(gf===null||ga===null||gf<0||ga<0)continue;
     const home=m.venue==='Casa'?g[side]:g[other];
     const away=m.venue==='Casa'?g[other]:g[side];
     const hg=m.venue==='Casa'?gf:ga,ag=m.venue==='Casa'?ga:gf;
     const item={date:String(m.day||''),home,away,score:hg+'-'+ag,
         competition:m.league||g.league||'',source:g.form?.[side]?.source||'FotMob/ESPN'};
     const key=[item.date,norm(item.home),norm(item.away),item.score].join('|');
     found.set(key,item);
   }
 }
 return [...found.values()].sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(0,20);
}
function instrument(g,detail){
 const points=samplesFrom(g),minutes=points.length?points.at(-1).minute:0;
 const end=Number(g.minute)>0?Math.max(minutes,Number(g.minute)):minutes;
 const ev=(g.events||[]).filter(e=>e&&iconLabels[e.type]&&safeNumber(e.m)!==null);
 const eventTimeline=ev.filter(e=>e.side==='home'||e.side==='away').map(e=>({
    minute:+e.m,team:e.side.toUpperCase(),emoji:iconLabels[e.type],name:e.type,
    basis:'event',label:'Evento confirmado · '+String(e.text||'').slice(0,100),
    reason:String(e.text||'Evento confirmado na fonte').slice(0,140)
 }));
 // A leitura AO VIVO precisa terminar no minuto atual, não na última
 // barra recebida. Sem amostras atuais, as janelas ficam inválidas.
 const ten=pressureWindow(points,end||1,10),five=pressureWindow(points,end||1,5);
 const fifteen=pressureWindow(points,end||1,15);
 // NEXUS original espera as janelas 5/10/15 com força e cobertura reais.
 const asWindow=(w)=>({
   valid:w.valid,home_force:w.home_recent,away_force:w.away_recent,
   samples:w.samples,expected:w.expected,as_of_minute:end,dominant:w.dominant,
   level:w.level,total_force:w.home_recent!==null&&w.away_recent!==null?w.home_recent+w.away_recent:null
 });
 const stats=detail.stats||{home:{},away:{}};
 const board=buildBoard(ten,five,stats,ev,end);
 const markers=[],previous={},trigger={};
 // Apenas ativações calculadas a partir das amostras OBSERVADAS, como no
 // NEXUS original signal_timeline.py. Nunca usa estatística futura para voltar no tempo.
 const eligible=new Set(['🧨','🔥','⚡','⏱️','🥶']);
 for(let m=10;m<=minutes;m++){
   const t=pressureWindow(points,m,10),f=pressureWindow(points,m,5);
   const prior=buildBoard(t,f,{home:{},away:{}},[],m);
   for(const item of prior){
     if(!eligible.has(item.emoji))continue;
     const active=item.state==='active';
     if(active && (!previous[item.emoji]||m-(trigger[item.emoji]??-999)>=12)){
       if(['HOME','AWAY'].includes(item.team)){
         markers.push({minute:m,team:item.team,emoji:item.emoji,name:item.name,
            basis:'graph',label:'Ativação pela pressão medida',reason:item.reason});
         trigger[item.emoji]=m;
       }
     }
     previous[item.emoji]=active;
   }
 }
 const snapshots=[];
 // Marcadores so usam capturas reais, nunca o ultimo minuto da pressao como
 // se representasse quando uma estatistica acumulada ocorreu.
 const observations=Array.isArray(g.scout_snapshots)?g.scout_snapshots:[];
 const latest=observations.at(-1);
 for(const side of ['home','away']){
   for(const [field,emoji,name] of [['shots_on','🥅','Chutes no gol'],['shots_off','↗️','Chutes para fora'],
     ['big_chances','💣','Grandes chances'],['dangerous_attacks','⚔️','Ataques perigosos']]){
     const count=safeNumber(latest?.stats?.[side]?.[field]);
     const observedMinute=safeNumber(latest?.m);
     if(count===null||count<=0||observedMinute===null||observedMinute<1||observedMinute>130)continue;
     snapshots.push({minute:observedMinute,team:side.toUpperCase(),emoji,name,basis:'snapshot',
        count,reason:count+' no jogo · observado em '+latest.at+'; momento dos eventos desconhecido',
        label:'Total acumulado na coleta; não significa ocorrência neste minuto'});
   }
 }
 const total=points.length;
 const sourcedetail=detail.scout_pressure||{};
 return {...detail,standings:g.standings||null,
    stats_observed_at:g.stats_observed_at||detail.stats_observed_at||null,
    stats_source:g.stats_source||detail.stats_source||g.source||'Fonte pública',
    pressure_observed_at:g.pressure_observed_at||null,
    momentum_diagnostic:g.momentum_diagnostic||null,
    scout_snapshots:observations,
    activity_timeline:g.activity_timeline||null,
    observed_at:g.observed_at||detail.observed_at||null,
   // Termômetro e IARA devem ler a MESMA série usada nas janelas e sinais.
   // Se a fonte não tiver amostras, preservar o detalhe existente sem criar zeros.
   thermometer:points.length?{...(detail.thermometer||{}),points}:detail.thermometer,
   signal_timeline:[...markers,...eventTimeline,...snapshots].sort((a,b)=>a.minute-b.minute),
   indicator_board:board,signals:board.filter(x=>x.state==='active'),
   head_to_head:headToHead(g),
   pressure:{score:ten.score,level:ten.level,dominant:ten.dominant,difference:ten.difference,
             home_recent:ten.home_recent,away_recent:ten.away_recent,minute:end},
   pressure5:{score:five.score,level:five.level,dominant:five.dominant,difference:five.difference},
   scout_pressure:{...sourcedetail,available:total>0,last_graph_minute:minutes,
     windows:{'5':asWindow(five),'10':asWindow(ten),'15':asWindow(fifteen)},
     narrative:total?'Pressão verificada por amostras; critérios idênticos ao engine.py do NEXUS 5.29.':
       'Sem amostras minuto a minuto confirmadas.'}
 };
}
// Correspondência com NEXUS 5.29 prelive.py::predictions:
// regressão de 3 pseudojogos a 1,25 gols + fator mando casa e Poisson completo.
const factorial=n=>{let v=1;for(let k=2;k<=n;k++)v*=k;return v};
const pois=(n,l)=>Math.exp(-l)*Math.pow(l,n)/factorial(n);
function forecast(g){
 const h=g.form?.home||{},a=g.form?.away||{};
 const nh=safeNumber(h.available),na=safeNumber(a.available);
 if(nh===null||na===null||nh<5||na<5){
   return {available:false,reason:'Amostra inferior a cinco partidas encerradas anteriores para uma das equipes.',source:'NEXUS 5.29 original'};
 }
 const hg=safeNumber(h.avg_goals_for),ha=safeNumber(h.avg_goals_against);
 const ag=safeNumber(a.avg_goals_for),aa=safeNumber(a.avg_goals_against);
 if([hg,ha,ag,aa].some(x=>x===null)){
   return {available:false,reason:'As médias reais de gols são insuficientes para o Poisson original.'};
 }
 const ha1=(hg*nh+1.25*3)/(nh+3),ad1=(aa*na+1.25*3)/(na+3);
 const aa1=(ag*na+1.25*3)/(na+3),hd1=(ha*nh+1.25*3)/(nh+3);
 const lh=cap(Math.sqrt(ha1*ad1)*1.10,.25,3.8);
 const la=cap(Math.sqrt(aa1*hd1)*.94,.25,3.8);
 const grid=[];
 for(let i=0;i<14;i++)for(let j=0;j<14;j++)grid.push({i,j,p:pois(i,lh)*pois(j,la)});
 const sum=grid.reduce((n,v)=>n+v.p,0);
 grid.forEach(v=>v.p/=sum);
 const pr=k=>round(grid.filter(k).reduce((n,v)=>n+v.p,0)*100);
 const one_x_two={home:pr(v=>v.i>v.j),draw:pr(v=>v.i===v.j),away:pr(v=>v.i<v.j)};
 const top_scores=grid.slice().sort((x,y)=>y.p-x.p).slice(0,3).map(v=>
   ({score:v.i+'-'+v.j,probability:round(v.p*100)}));
 const btts_yes_pct=pr(v=>v.i>0&&v.j>0);
 const over_2_5_pct=pr(v=>v.i+v.j>=3);
 const expectation={home:round(lh,2),away:round(la,2)};
 const phases={game:[{label:'Over 2.5',value:over_2_5_pct},
                    {label:'Ambas marcam',value:btts_yes_pct},
                    {label:'Pelo menos um gol',value:pr(v=>v.i+v.j>=1)}],
               first:[{label:'Gol no 1º tempo (Poisson proporcional)',value:round((1-Math.exp(-(lh+la)*.45))*100)}],
               second:[{label:'Gol no 2º tempo (Poisson proporcional)',value:round((1-Math.exp(-(lh+la)*.55))*100)}],
               first_goal:[]};
 const estimates={available:true,one_x_two,expected_goals:expectation,top_scores,
   over_2_5_pct,btts_yes_pct,periods:phases,
   model:'NEXUS 5.29 regressão à média + Poisson (experimental, não calibrado)',
   confidence:'EXPERIMENTAL'};
 return {available:true,forecast:estimates,
     sample:{home:{n:nh,gf:hg,ga:ha,recent:h.games||[]},
             away:{n:na,gf:ag,ga:aa,recent:a.games||[]}},
     coverage:{model_confidence:'experimental'},
     source:'NEXUS 5.29 original · ESPN/FotMob',
     note:'Sem backtest de calibração, isto não representa EV+ confirmado.',
     odds:{available:!!g.odds?.length,markets:{'1x2':(g.odds||[]).reduce((o,v)=>{
       if(v.sel&&Number(v.odd)>1)o[v.sel]=+v.odd;return o;},{})}}};
}
function addProjection(detail,fb){
 // O detalhe do termômetro não herda automaticamente prelive.odds.
 // Manter preços live da própria fonte quando explicitamente identificados;
 // caso contrário, mostrar cotações verificadas como PRÉ-JOGO.
 const observed=detail?.odds?.markets?.['1x2']||{};
 const hasLive=detail?.odds?.phase==='live' &&
   ['home','draw','away'].every(side=>Number(observed[side])>1.01);
 const odds=hasLive?detail.odds:(fb?.odds||{available:false,markets:{'1x2':{}},phase:'pregame'});
 if(!fb?.available||!fb.forecast?.one_x_two)
   return {...detail,odds,projections:null,prelive:fb};
 const f=fb.forecast,p=f.one_x_two;
 return {...detail,odds,projections:{...p,model_estimate:true,verified:false,
   sample_size:Math.min(fb.sample.home.n,fb.sample.away.n),
   periods:f.periods,expected_goals:f.expected_goals,
   top_scores:f.top_scores,source:'NEXUS 5.29 · Poisson experimental não calibrado'},
   prelive:fb};
}
function verifiedPrelive(g,model){
 const side=(name)=>{
   const data=(g.lineups||{})[name]||{},roster=(g.roster||{})[name]||[];
   const starters=Array.isArray(data.starters)?data.starters:[];
   const subs=Array.isArray(data.subs)?data.subs:[];
   const official=data.status==='confirmed';
   const people=arr=>arr.map(v=>({name:String(v.name||'').slice(0,90),
     number:String(v.number||'').slice(0,4)})).filter(x=>x.name);
   const fallback=roster.flatMap(section=>section.players||[]).slice(0,26);
   return {xi:people(starters),bench:people(subs),roster:people(fallback),
           formation:String(data.formation||''),official,
           status:starters.length?(official?'confirmada':'provável'):'elenco geral',
           lineup_type:String(data.lineup_type||''),
           updated_at:data.updated_at||null};
 };
 const home=side('home'),away=side('away');
 const select=side=>side.xi.length?[...side.xi,...side.bench]:side.roster;
 const confirmation=home.official&&away.official?'confirmada':
   home.xi.length||away.xi.length?'provável':'aguardando confirmação';
 const lineups={home:select(home),away:select(away),
  home_detail:home,away_detail:away,
  status:confirmation,source:'FotMob',checked_at:g.observed_at||null};
 const cutoff=Number(g.start_timestamp||0);
 const quotes=(Array.isArray(g.odds)?g.odds:[]).filter(q=>{
   if(!q||!['home','draw','away'].includes(q.sel))return false;
   if(safeNumber(q.odd)===null||Number(q.odd)<=1.01||Number(q.odd)>1000)return false;
   const ts=Date.parse(String(q.at||''));
   return Number.isFinite(ts)&&cutoff>0&&ts<cutoff*1000;
 });
 // Recusar pacotes parciais e preços publicados após o início.
 const market={};let source='',bookmaker='',at='';
 const sameCapture=quotes.length===3 &&
   new Set(quotes.map(q=>[q.source||'',q.bookmaker||'',q.at||''].join('|'))).size===1;
 if(sameCapture){
   for(const q of quotes)market[q.sel]=Number(q.odd);
   if(Object.keys(market).length!==3){for(const k of Object.keys(market))delete market[k];}
   else {source=quotes[0].source||'';bookmaker=quotes[0].bookmaker||'';at=quotes[0].at||'';}
 }
 const available=Object.keys(market).length===3;
 return {...model,lineups,head_to_head:headToHead(g),standings:g.standings||null,
  odds:{available,phase:'pregame',markets:{'1x2':market},source:source||null,
   bookmaker:bookmaker||null,fetched_at:at||null,
   reason:available?'':'Nenhum trio 1X2 pré-jogo confirmado (mesma casa, fonte e coleta).'},
  checked_sources:[...new Set(['fotmob',...quotes.map(q=>q.source).filter(Boolean)])]
};
}
function availability(g){
 const s=g.stats||{},h=s.home||{},a=s.away||{};
 const got=k=>h[k]!=null||a[k]!=null;
 const price=(g.odds||[]).length>0;
 const finished=!!g.outcomes?.correct_score;
 return [
  {name:'Over / Under gols',observed:price||finished,coverage:price?'Odd 1X2 registrada, mas O/U sem preço':finished?'Placar final disponível, sem odds O/U':'Sem resultado'},
  {name:'Ambas marcam (BTTS)',observed:finished,coverage:finished?'Placar encerrado; sem preço BTTS':'Sem odds verificadas'},
  {name:'Match Odds (1X2)',observed:price||finished,coverage:price?'Odds 1X2 verificadas':finished?'Resultado conhecido; odd ausente':'Sem preço'},
  {name:'Escanteios',observed:got('corners'),coverage:got('corners')?'Scout confirmado':'Sem scouts'},
  {name:'Finalizações',observed:got('shots_on')||got('shots_off'),coverage:got('shots_on')||got('shots_off')?'Scouts confirmados':'Sem scouts'},
  {name:'Grandes chances',observed:got('big_chances'),coverage:got('big_chances')?'Scout confirmado':'Sem scouts'},
  {name:'Ataques perigosos',observed:got('dangerous_attacks'),coverage:got('dangerous_attacks')?'Scout confirmado':'Sem scouts'},
  {name:'Lay Correct Score',observed:false,coverage:'Sem preço pré-entrada auditado'}
 ];
}
function labDashboard(doc){
 const games=doc.games||[],paper=doc.paper||{},market=doc.market_history||{};
 const settled=Number(paper.settled||0),pl=settled?safeNumber(paper.paper_pl_u):null;
 const signals=games.flatMap(g=>(g.signals||[]).filter(s=>s.ev_pct!=null&&s.odds!=null).map(s=>({
   match_id:g.id,home:g.home,away:g.away,league:g.league,
   market:s.market,selection:s.selection,odds:s.odds,probability:s.probability,
   ev_pct:s.ev_pct,odds_source:g.source,odds_at:s.captured_at
 })));
 const quality=games.map(g=>{
   const stats=(g.stats?.home||{}),away=g.stats?.away||{};
   const count=new Set([...Object.keys(stats),...Object.keys(away)]).size;
   const momentum=g.pressure||[];
   return {match_id:g.home+' × '+g.away,source:g.source,
     state:g.phase==='live'?'AO VIVO':g.phase==='finished'?'ENCERRADO':'PRÉ-JOGO',
     updated_at:g.observed_at,stats_available:count,stats_expected:15,
     momentum_samples:momentum.length,momentum_coverage_pct:round(momentum.length/90*100),
     momentum_source:momentum.length?g.source:'Indisponível'}
 }).sort((a,b)=>(b.momentum_samples-a.momentum_samples)||(b.stats_available-a.stats_available)).slice(0,120);
 const providers={ESPN:'Coleta pública',FotMob:'Coleta pública',
   'Football-Data.co.uk':String(doc.source_status?.providers?.['Football-Data.co.uk']||'desativado'),
   OpenLigaDB:String(doc.source_status?.providers?.OpenLigaDB||'sem dados nesta janela'),
   'OpenFootball CC0':(doc.source_status?.openfootball_cc0?.cross_verified||0)+' placares FT verificados / '+(doc.source_status?.openfootball_cc0?.checked||0)+' conferidos'};
 const markets=market.markets||[];
 const journal=(doc.signal_journal?.items||[]).slice(0,80).map(a=>({
   match_id:a.match_id,created_at:a.captured_at,category:'monitoramento',
   message:[a.icon,a.home+' × '+a.away,a.minute+"'",
     a.rule,'Gol 5m: '+(a.outcomes?.['5']||'pendente'),
     '10m: '+(a.outcomes?.['10']||'pendente'),
     '15m: '+(a.outcomes?.['15']||'pendente'),
     'EV+ indisponível sem odd/modelo calibrado'].join(' · ')
 }));
 const alerts=(doc.alerts||[]).map(a=>({
   match_id:a.match_id,created_at:a.observed_at,
   category:a.kind==='ev_experimental'?'ev':'monitoramento',
   message:a.title+' · '+a.detail
 }));
 const paperMarkets=(paper.markets||[]).map(m=>({
   market:m.market,entries:m.entries,net_units:m.paper_pl_u
 }));
 return {version:'5.29 original · dados GitHub',updated_at:doc.exported_at,
   observations:games.length,radar:signals,alerts:[...journal,...alerts],providers,quality,markets,
   backtest:{evaluated_fixtures:settled,total_net_units:pl,
     wins:paper.won||0,win_rate_pct:settled?round(paper.won/settled*100):null,
     max_drawdown_units:null,by_market:paperMarkets,
     settled_signals:settled,brier_samples:0,brier_score:null,
     calibration:[],
     method:'Somente entradas simuladas registradas antes do jogo, odds verificadas e placar liquidado; não é P/L da Bolsa.'},
   pressure_validation:{records:[],windows:{}},
   stake_100:{evaluated_fixtures:settled,wins:paper.won||0,
     losses:settled-(paper.won||0),net_brl:pl===null?null:pl*100,
     risked_brl:settled*100,roi_pct:pl===null?null:round(pl/settled*100),entries:[],
     method:'Sem apostas executadas: 1 unidade paper = R$ 100 hipotéticos, sem taxas.'}};
}
function cloudCollector(doc){
 const games=doc.games||[],paper=doc.paper||{},settled=Number(paper.settled||0);
 const quotes=games.reduce((n,g)=>n+(g.odds||[]).length,0);
 const rows=games.map(g=>{
   const pts=g.pressure||[],observed=g.odds||[];
   return {id:g.id,day:g.day,home:g.home,away:g.away,score:g.score,minute:g.minute,
     phase:g.phase,league:g.league,source:(g.sources||[g.source]).join(' + '),
     collected_at:g.observed_at,stats:g.stats,
     thermometer:{points:pts.map(p=>({minute:p.m,value:p.v})),samples:pts.length},
     scout_snapshots:g.scout_snapshots||[],
     observations:pts.length||1,
     odds_available:observed.length>0,ev_available:(g.signals||[]).some(x=>x.ev_pct!=null),
     markets:availability(g),
     quotes:observed.map(o=>({market:'1x2',selection:o.sel,odds:o.odd,source:o.source,
       captured_at:o.at}))};
 });
 const selected=(paper.markets||[]).map(m=>({market:m.market,settled_paper:m.entries,
   paper_units:m.paper_pl_u,operations:0,actual_net_pl_brl:null,priced_games:0,
   experimental_ev_plus:0}));
 return {connected:true,source:'FotMob · ESPN · Football-Data · OpenLigaDB',
   status:{updated_at:doc.exported_at,sources:['FotMob','ESPN','Football-Data','OpenLigaDB']},
   sync:{connected:true,last_sync:doc.exported_at},
   market_policy:'Somente dados esportivos e operações paper. Informações financeiras pessoais permanecem privadas.',
   updated_at:doc.exported_at,games:rows,
   audit:{stake_brl:100,quotes_registered:quotes,
      trades_verified:0,actual_net_pl_brl:null,
      settled_paper:settled,paper_profit_loss_brl:settled?Number(paper.paper_pl_u||0)*100:null,
      markets:selected,
      note:'Sem operações pessoais publicadas. EV+ só com preço pré-entrada e calibração; paper não é lucro recebido.'},
   platform_snapshot:null,signal_journal:doc.signal_journal||{items:[],diagnostics:{}},
   historical_xg:doc.historical_xg||{available:false,matches_verified:0,live_xg:false,ev_plus:false}};
}
window.fetch=async function(request,options){
 const str=typeof request==='string'?request:request?.url;
 if(typeof str!=='string')return previous(request,options);
 const path=new URL(str,window.location.href).pathname;
 if(path==='/api/v5/dashboard'||path==='/api/github-collector'){
   try{
     const doc=await bridge.data();
     const output=path==='/api/v5/dashboard'?labDashboard(doc):cloudCollector(doc);
     return new Response(JSON.stringify(output),{status:200,headers:{
       'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'}});
   }catch(error){console.warn('NEXUS laboratório sem snapshot',error);return previous(request,options)}
 }
 if(!isMatchURL(path))return previous(request,options);
 const res=await previous(request,options);
 if(!res.ok)return res;
 try{
   const payload=await res.clone().json();
   const id=decodeURIComponent(path.split('/').pop());
   const snap=await bridge.data();
   const g=snap.games.find(v=>String(v.id)===id);
   if(!g)return res;
   const fb=verifiedPrelive(g,forecast(g));
   const out=path.startsWith('/api/prelive/')?fb:addProjection(instrument(g,payload),fb);
   return new Response(JSON.stringify(out),{status:200,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'}});
 }catch(ex){
   console.warn('NEXUS: complemento indisponível, mantendo os dados originais',ex);
   return res;
 }
};
window.NexusOriginalEnrichment={pressureWindow,buildBoard,forecast,instrument};
})();