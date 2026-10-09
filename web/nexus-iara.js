/* NEXUS SCORE · IARA
 * Leitura editorial dos dados OBSERVADOS. Não solicita modelo pago, não
 * confunde pressão com probabilidade calibrada, não extrapola amostras velhas.
 * A tela recebe atualização quando a coleta GitHub fornece novo snapshot.
 */
(function(){
'use strict';
const safe=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=x=>x===null||x===undefined||x===''||typeof x==='boolean'?null:
  Number.isFinite(Number(x))?Number(x):null;
const sign=x=>Math.max(0,Math.min(100,Number(x)||0));
const name=(d,side)=>String(d?.[side]|| (side==='home'?'Mandante':'Visitante')).slice(0,100);
function points(d){
 const raw=d?.thermometer?.points||d?.pressure||[];
 if(!Array.isArray(raw))return [];
 const byMinute=new Map();
 for(const p of raw){
   if(!p||typeof p!=='object')continue;
   const minute=num(p.minute??p.m),value=num(p.value??p.v);
   if(minute===null||value===null||minute<1||minute>130||Math.abs(value)>1000)continue;
   byMinute.set(Math.floor(minute),Math.max(-100,Math.min(100,value)));
 }
 return [...byMinute].sort((a,b)=>a[0]-b[0]).map(([minute,value])=>({minute,value}));
}
function windowPressure(points,end,width){
 if(!end||end<1)return {valid:false,samples:0,expected:0};
 const expected=Math.min(width,end);
 const vals=points.filter(p=>p.minute<=end&&p.minute> end-width).map(p=>p.value);
 if(vals.length<Math.max(1,Math.ceil(expected*.8)))return {valid:false,samples:vals.length,expected};
 const home=vals.reduce((s,v)=>s+Math.max(0,v),0)/vals.length;
 const away=vals.reduce((s,v)=>s+Math.max(0,-v),0)/vals.length;
 const difference=Math.abs(home-away);
 const dominant=home>away*1.12&&difference>5?'home':
     away>home*1.12&&difference>5?'away':'even';
 const intensity=Math.max(home,away);
 return {valid:true,samples:vals.length,expected,home,away,intensity,difference,dominant,
   strength:intensity>=44&&difference>=12?'forte':
     intensity>=25?'moderada':intensity<12?'baixa':'moderada'};
}
function readingOfStats(d){
 const h=d?.stats?.home||{},a=d?.stats?.away||{};
 const pair=k=>{const x=num(h[k]),y=num(a[k]);return x===null||y===null?null:[x,y];};
 const on=pair('shots_on'),big=pair('big_chances'),corners=pair('corners'),xg=pair('xg');
 const shot=on, evidence=[];
 if(on)evidence.push('Finalizações no gol '+on[0]+'×'+on[1]);
 if(big)evidence.push('Grandes chances '+big[0]+'×'+big[1]);
 if(corners)evidence.push('Escanteios '+corners[0]+'×'+corners[1]);
 if(xg)evidence.push('xG '+xg[0]+'×'+xg[1]);
 const dangerous=pair('dangerous_attacks');
 if(dangerous)evidence.push('Ataques perigosos '+dangerous[0]+'×'+dangerous[1]);
 return {on,big,corners,xg,reds:pair('red_cards'),dangerous,evidence};
}
function favourite(d){
 const pre=d?.prelive?.odds||{};
 const market=pre?.markets?.['1x2']||d?.odds?.markets?.['1x2']||{};
 const home=num(market.home),away=num(market.away),draw=num(market.draw);
 const kickoff=num(d?.start_timestamp);
 const date=pre?.fetched_at||d?.odds?.fetched_at||null;
 const recorded=date?Date.parse(String(date)):NaN;
 if(![home,away,draw].every(v=>v!==null&&v>1.01&&v<1000))return null;
 if(!kickoff||!Number.isFinite(recorded)||recorded>kickoff*1000||recorded<=0)return null;
 const ratio=Math.max(home,away)/Math.min(home,away);
 if(ratio<1.20)return null;
 return {side:home<away?'home':'away', source:pre?.source||d?.odds?.source||'odds pré-jogo'};
}
function verifiedEvents(d,min,max){
 const ev=d?.incidents||[];
 if(!Array.isArray(ev))return [];
 return ev.filter(x=>{
   const m=num(x?.minute);
   return m!==null&&m>min&&m<=max;
 });
}
function details(d){
 const h=num(d?.home_score),a=num(d?.away_score);
 if(h!==null&&a!==null)return {home:h,away:a};
 const p=String(d?.score||'').match(/(\d+)\s*[-–:]\s*(\d+)/);
 return p?{home:+p[1],away:+p[2]}:null;
}
function evaluate(d){
 const phase=String(d?.phase||'').toLowerCase();
 const minuteRaw=num(d?.minute);
 const minute=minuteRaw===null?0:Math.max(0,Math.min(130,Math.floor(minuteRaw)));
 const live=phase==='live'||(d?.live===true&&phase!=='finished');
 const teamHome=name(d,'home'),teamAway=name(d,'away');
 const obs=points(d),last=obs.length?obs[obs.length-1].minute:0;
 const stale=last>0&&minute>0&&(minute-last)>8;
 const w5=windowPressure(obs,minute,5);
 const w10=windowPressure(obs,minute,10);
 const previous5=windowPressure(obs,Math.max(0,minute-5),5);
 const current=!stale?(w10.valid?w10:w5.valid?w5:null):null;
 const stats=readingOfStats(d),score=details(d),fav=favourite(d);
 const indicators=Array.isArray(d?.indicator_board)?d.indicator_board.filter(x=>x&&x.state==='active'):[];
 const names={home:teamHome,away:teamAway};
 const tags=[];
 const evidence=stats.evidence.slice(0,3);
 const confidence=current?.valid&&w10.valid&&stats.evidence.length>=2?'MÚLTIPLOS DADOS':
   current?.valid?'PRESSÃO MEDIDA':stats.evidence.length?'SCOUTS ACUMULADOS':'SEM DADOS RECENTES';
 if(!live)return {active:false,heading:'Aguardando partida ao vivo',intro:'A IARA começa a leitura quando a partida estiver ao vivo.',confidence:'AGUARDANDO',tags:[],evidence:[],next:'',method:''};
 let intro='',next='',context='';
 if(stale){
   intro='A curva de pressão parou no '+last+"′, enquanto o jogo está no "+minute+
       '′. Não é seguro afirmar quem pressiona agora com uma leitura antiga.';
   tags.push('CURVA ATRASADA');
 }else if(current){
   const side=current.dominant;
   if(side==='even'){
     intro=current.strength==='baixa'?
       'Ritmo ofensivo baixo nas amostras mais recentes; nenhuma das equipes sustenta uma pressão clara.':
       'O jogo está dividido no termômetro, sem domínio claro nos minutos mais recentes.';
     tags.push(current.strength==='baixa'?'JOGO FRIO':'JOGO EQUILIBRADO');
   }else{
     const leader=names[side],trailer=names[side==='home'?'away':'home'];
     intro=current.strength==='forte'?
       leader+' está pressionando com intensidade forte nos minutos mais recentes. '+trailer+' vem cedendo espaço no termômetro.':
       current.strength==='moderada'?
       leader+' está mais presente no ataque e mantém uma pressão moderada. '+trailer+' aparece menos nas ações ofensivas medidas.':
       leader+' aparece ligeiramente melhor na pressão recente, mas a intensidade continua baixa.';
     tags.push(current.strength==='forte'?'PRESSÃO FORTE':current.strength==='moderada'?'PRESSÃO MODERADA':'RITMO BAIXO');
     tags.push(side==='home'?'MANDANTE POR CIMA':'VISITANTE POR CIMA');
   }
   if(w5.valid&&previous5.valid){
     const now=w5.home-w5.away,prev=previous5.home-previous5.away;
     const delta=now-prev;
     if(delta>=12)context+=' O mandante aumentou a força relativa em comparação aos cinco minutos anteriores.';
     else if(delta<=-12)context+=' O visitante cresceu em relação aos cinco minutos anteriores.';
   }
 }else{
   intro=obs.length?
     'A pressão foi registrada, mas faltam amostras consecutivas suficientes para uma leitura confiável dos últimos minutos.':
     'O jogo está em andamento, mas a fonte ainda não entregou uma curva de pressão recente.';
   tags.push('AGUARDANDO MOMENTUM');
 }
 if(score){
   if(score.home===score.away){context+=' O placar permanece empatado.';}
   else{
     const leader=score.home>score.away?'home':'away';
     context+=' '+names[leader]+' está à frente por '+score.home+'–'+score.away+'.';
     if(fav){
       if(fav.side!==leader)context+=' O favorito pré-jogo está atrás; a zebra está vencendo neste momento.';
       else if(current?.valid&&current.dominant!==leader&&current.dominant!=='even'){
         context+=' Mesmo à frente, o favorito está sofrendo pressão do adversário.';
       }
     }
   }
 }
 if(stats.reds&&(stats.reds[0]||stats.reds[1])){
   if(stats.reds[0]>stats.reds[1])context+=' O mandante tem mais expulsões, o que pode alterar a dinâmica.';
   else if(stats.reds[1]>stats.reds[0])context+=' O visitante tem mais expulsões, o que pode alterar a dinâmica.';
 }
 let contender=current?.dominant==='home'||current?.dominant==='away'?current.dominant:null;
 const evidenceSide=contender==='home'?0:contender==='away'?1:-1;
 const shots=evidenceSide<0?null:stats.on?.[evidenceSide];
 const big=evidenceSide<0?null:stats.big?.[evidenceSide];
 const recentEvents=verifiedEvents(d,Math.max(0,minute-10),minute);
 const freshThreat=recentEvents.some(e=>{
   const label=String(e.type||e.emoji||'').toLowerCase();
   const team=String(e.team||'').toUpperCase();
   return (team===(contender==='home'?'HOME':'AWAY'))&&
       (['shot_on','big_chance','goal'].includes(label)||/[⚽💣]/.test(label));
 });
 const strong=current?.strength==='forte';
 const corroborated=shots!==null&&shots>=3||big!==null&&big>=1||freshThreat;
 if(stale||!current){
   next='Sobre mais um gol: sem pressão recente confiável, a IARA não consegue apontar uma tendência atual.';
 }else if(contender&&strong&&corroborated){
   next=names[contender]+' apresenta pressão forte com apoio de ações ofensivas confirmadas. O cenário merece atenção para uma nova chance de gol, mas não garante que a bola entre.';
   tags.push('ATENÇÃO A NOVO GOL');
 }else if(contender&&strong){
   next=names[contender]+' pressiona, mas faltam finalizações ou chances confirmadas para sustentar uma leitura de gol próximo.';
 }else if(current.strength==='baixa'){
   next='A movimentação recente não sugere um cerco consistente. Não há base para destacar um próximo gol.';
 }else if(contender){
   next='A iniciativa é de '+names[contender]+', mas o ritmo observado ainda não é suficiente para tratar outro gol como provável.';
 }else{
   next='O equilíbrio atual não permite apontar qual equipe deve criar a próxima oportunidade.';
 }
 if(minute>=75)next+=' Reta final: menos tempo disponível para uma reação.';
 if(stats.evidence.length){
   evidence.push('Termômetro: '+(current?.samples||0)+'/'+(current?.expected||10)+' min recentes');
 }else if(current){
   evidence.push('Termômetro: '+current.samples+'/'+current.expected+' min recentes');
 }
 if(fav&&score)evidence.push('Favorito pré-jogo: '+names[fav.side]+' (odds verificadas)');
 if(indicators.length)evidence.push('Indicadores ativos: '+indicators.slice(0,2).map(x=>String(x.emoji||x.name||'')).join(' '));
 const method='Leitura por regras sobre dados públicos; coleta periódica, não transmissão segundo a segundo. Pressão não é probabilidade de gol nem EV+.';
 const commentary=(intro+context).trim();
 return {active:true,heading:'IARA · Visão ao vivo',minute,intro:commentary,next,
   tags:[...new Set(tags)].slice(0,3),confidence,
   evidence:evidence.slice(0,5),method,observedThrough:last,stale,
   fingerprint:[minute,last,score?.home,score?.away,current?.dominant,current?.strength,stats.evidence.join('/'),indicators.length].join('|')};
}
function render(d){
 const v=evaluate(d);
 if(!v.active)return '';
 const age=v.observedThrough?
   ' · última pressão observada: '+v.observedThrough+'′':' · aguardando pressão';
 const tagHTML=v.tags.map(x=>'<span class="iara-pill">'+safe(x)+'</span>').join('');
 const facts=v.evidence.length?
   '<div class="iara-evidence">'+v.evidence.map(x=>'<span>'+safe(x)+'</span>').join('')+'</div>':'';
 return '<section class="iara-card" aria-label="IARA análise do jogo ao vivo" data-iara-fingerprint="'+safe(v.fingerprint)+'">'+
   '<header class="iara-header"><div><span class="iara-bot">◈ IARA</span>'+
   '<h3>Análise do jogo ao vivo</h3><small>'+safe(v.minute)+'′ · '+safe(v.confidence)+safe(age)+'</small></div>'+
   '<span class="iara-live-tag">● LEITURA ATUALIZÁVEL</span></header>'+
   '<div class="iara-body"><div class="iara-tags">'+tagHTML+'</div>'+
   '<p class="iara-comment">'+safe(v.intro)+'</p>'+
   '<div class="iara-goal"><strong>⚽ Pode sair mais um gol?</strong><p>'+safe(v.next)+'</p></div>'+
   facts+'<p class="iara-footnote">'+safe(v.method)+'</p></div></section>';
}
window.NexusIara={render,evaluate,windowPressure,points};
})();