/* NEXUS 5.31 — regras puras, sem histórico e sem dados inventados. */
(function(root){
'use strict';
function finite(v){return v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v))?Number(v):null;}
const superscripts={'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹'};
function exponent(n){return n<=1?'':String(n).split('').map(c=>superscripts[c]||c).join('');}
function groupEvents(events){
 const groups=new Map();
 for(const event of (Array.isArray(events)?events:[])){
  if(!event||typeof event!=='object')continue;
  const minute=finite(event.minute??event.m);
  const side=String(event.team||event.side||'').toUpperCase();
  const kind=String(event.emoji||event.type||'');
  if(minute===null||minute<0||minute>150||!kind||!['HOME','AWAY'].includes(side))continue;
  const key=minute+'|'+side+'|'+kind;
  const old=groups.get(key);
  if(old){old.count++;if(event.text||event.reason)old.details.push(String(event.text||event.reason).slice(0,120));}
  else groups.set(key,{...event,minute,team:side,emoji:kind,count:1,details:[String(event.text||event.reason||'').slice(0,120)]});
 }
 return [...groups.values()].sort((a,b)=>a.minute-b.minute||a.team.localeCompare(b.team)||a.emoji.localeCompare(b.emoji));
}
function hasThermometer(match,detail){
 const points=detail?.thermometer?.points||match?.thermometer?.points;
 return !!(Array.isArray(points)&&points.some(p=>finite(p.minute??p.m)!==null&&finite(p.value??p.v)!==null) ||
   match?.has_saved_thermometer===true || match?.__hasThermo===true);
}
// Frio exige queda REAL, cobertura contínua e observações antes/depois;
// pressão historicamente ausente nunca vira jogo frio.
function coldAt(points,minute){
 const end=finite(minute);
 if(end===null||end<20||!Array.isArray(points))return {active:false,reason:'Janela ainda insuficiente'};
 const map=new Map(points.map(p=>[finite(p.minute??p.m),finite(p.value??p.v)]).filter(([m,v])=>m!==null&&v!==null&&m>=0&&m<=end));
 const windowAt=(to,n)=>{
  const values=[];for(let m=to-n+1;m<=to;m++)if(map.has(m))values.push(Math.abs(map.get(m)));
  return values.length>=Math.ceil(n*.8)?values.reduce((s,v)=>s+v,0)/values.length:null;
 };
 const latest=windowAt(end,10),prior=windowAt(end-10,10),last5=windowAt(end,5);
 const active=latest!==null&&prior!==null&&last5!==null&&prior>=35&&latest<22&&last5<18;
 return {active,latest,prior,last5,reason:active?
  'Queda observada: pressão anterior '+prior.toFixed(1)+' → atual '+latest.toFixed(1)+'; últimos 5 min '+last5.toFixed(1):
  'FRIO não confirmado: exigidos 20 minutos observados, queda de pressão e persistência'};
}
function recommendations(pre,home,away){
 const f=pre?.forecast||{},p=f.one_x_two||{},s=pre?.sample||{};
 if(pre?.available!==true||finite(s.home?.n)<3||finite(s.away?.n)<3)
   return {available:false,items:[],reason:'Amostra insuficiente dos dois times para quatro cenários estatísticos confiáveis.'};
 const h=finite(p.home),d=finite(p.draw),a=finite(p.away),over=finite(f.over_2_5_pct),btts=finite(f.btts_yes_pct);
 if([h,d,a,over,btts].some(v=>v===null||v<0||v>100)||Math.abs(h+d+a-100)>3)
   return {available:false,items:[],reason:'Probabilidades ainda não verificadas pelo modelo.'};
 const results=[{label:home+' vence',prob:h},{label:'Empate',prob:d},{label:away+' vence',prob:a}].sort((x,y)=>y.prob-x.prob);
 const double=[{label:home+' ou empate (1X)',prob:h+d},{label:'Empate ou '+away+' (X2)',prob:d+a},{label:home+' ou '+away+' (12)',prob:h+a}].sort((x,y)=>y.prob-x.prob);
 const items=[
  {market:'Match Odds',label:results[0].label,prob:results[0].prob,basis:'1X2 calculado pelo modelo'},
  {market:'Dupla chance',label:double[0].label,prob:double[0].prob,basis:'Soma dos desfechos 1X2 do mesmo modelo'},
  {market:'Gols 2.5',label:over>=50?'Over 2.5':'Under 2.5',prob:Math.max(over,100-over),basis:'Distribuição Poisson de gols'},
  {market:'Ambas marcam',label:btts>=50?'Sim':'Não',prob:Math.max(btts,100-btts),basis:'Projeção de gols das equipes'}
 ].sort((x,y)=>y.prob-x.prob);
 return {available:true,items,reason:'Estimativas experimentais, não odds, EV+ ou apostas recomendadas. Mercados correlacionados.'};
}
function playerState(player,role,official,phase,events){
 const name=String(player?.name||player?.player||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase();
 const observed=(Array.isArray(events)?events:[]).filter(e=>e?.type==='substitution');
 const same=(value)=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase()===name;
 const out=observed.find(e=>same(e.player_out)),inn=observed.find(e=>same(e.player_in));
 if(out)return 'Saiu aos '+String(out.m??out.minute??'?')+'′ · confirmado';
 if(inn)return 'Entrou aos '+String(inn.m??inn.minute??'?')+'′ · confirmado';
 if(role==='bench')return official?'Reserva · sem entrada confirmada':'Reserva provável · não confirmada';
 if(!official)return 'Titular provável · não confirmado';
 return phase==='scheduled'?'Titular confirmado · aguardando início':'Titular escalado · sem saída registrada; presença atual não verificada';
}
const API={finite,exponent,groupEvents,hasThermometer,coldAt,recommendations,playerState};
root.NexusUpgrade=API;
if(typeof module!=='undefined'&&module.exports)module.exports=API;
})(typeof window!=='undefined'?window:globalThis);
