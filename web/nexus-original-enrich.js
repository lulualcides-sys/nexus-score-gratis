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
'red_card':'🟥','shot_on':'🥅','shot_off':'↗️'};
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
function instrument(g,detail){
 const points=samplesFrom(g),minutes=points.length?points.at(-1).minute:0;
 const end=Number(g.minute)>0?Math.max(minutes,Number(g.minute)):minutes;
 const ev=(g.events||[]).filter(e=>e&&iconLabels[e.type]&&safeNumber(e.m)!==null);
 const eventTimeline=ev.filter(e=>e.side==='home'||e.side==='away').map(e=>({
    minute:+e.m,team:e.side.toUpperCase(),emoji:iconLabels[e.type],name:e.type,
    basis:'event',label:'Evento confirmado · '+String(e.text||'').slice(0,100),
    reason:String(e.text||'Evento confirmado na fonte').slice(0,140)
 }));
 const ten=pressureWindow(points,minutes||1,10),five=pressureWindow(points,minutes||1,5);
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
 for(const side of ['home','away']){
   for(const [field,emoji,name] of [['shots_on','🥅','Chutes no gol'],['shots_off','↗️','Chutes para fora'],
     ['big_chances','💣','Grandes chances'],['dangerous_attacks','⚔️','Ataques perigosos']]){
     const count=safeNumber(stats[side]?.[field]);
     if(count===null||count<=0)continue;
     snapshots.push({minute:minutes,team:side.toUpperCase(),emoji,name,basis:'snapshot',
        count,reason:count+' no jogo · total sem minuto de ocorrência',
        label:'Total acumulado; não é incidente histórico neste minuto'});
   }
 }
 const total=points.length;
 const sourcedetail=detail.scout_pressure||{};
 return {...detail,signal_timeline:[...markers,...eventTimeline,...snapshots].sort((a,b)=>a.minute-b.minute),
   indicator_board:board,signals:board.filter(x=>x.state==='active'),
   pressure:{score:ten.score,level:ten.level,dominant:ten.dominant,difference:ten.difference,
             home_recent:ten.home_recent,away_recent:ten.away_recent,minute:end},
   pressure5:{score:five.score,level:five.level,dominant:five.dominant,difference:five.difference},
   scout_pressure:{...sourcedetail,available:total>0,last_graph_minute:minutes,
     windows:{'10':{valid:ten.valid,dominant:ten.dominant,total_force:
                 ten.home_recent!==null&&ten.away_recent!==null?ten.home_recent+ten.away_recent:null}},
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
 if(!fb?.available||!fb.forecast?.one_x_two)return {...detail,projections:null,prelive:fb};
 const f=fb.forecast,p=f.one_x_two;
 return {...detail,projections:{...p,model_estimate:true,verified:false,
   sample_size:Math.min(fb.sample.home.n,fb.sample.away.n),
   periods:f.periods,expected_goals:f.expected_goals,
   top_scores:f.top_scores,source:'NEXUS 5.29 · Poisson experimental não calibrado'},
   prelive:fb};
}
window.fetch=async function(request,options){
 const str=typeof request==='string'?request:request?.url;
 if(typeof str!=='string')return previous(request,options);
 const path=new URL(str,window.location.href).pathname;
 if(!isMatchURL(path))return previous(request,options);
 const res=await previous(request,options);
 if(!res.ok)return res;
 try{
   const payload=await res.clone().json();
   const id=decodeURIComponent(path.split('/').pop());
   const snap=await bridge.data();
   const g=snap.games.find(v=>String(v.id)===id);
   if(!g)return res;
   const fb=forecast(g);
   const out=path.startsWith('/api/prelive/')?fb:addProjection(instrument(g,payload),fb);
   return new Response(JSON.stringify(out),{status:200,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'}});
 }catch(ex){
   console.warn('NEXUS: complemento indisponível, mantendo os dados originais',ex);
   return res;
 }
};
window.NexusOriginalEnrichment={pressureWindow,buildBoard,forecast,instrument};
})();