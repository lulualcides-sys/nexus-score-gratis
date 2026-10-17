/* Regressões isoladas para o NEXUS 5.31: apenas dados confirmados. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const ui=require('../web/nexus-v531.js');
const grouped=ui.groupEvents([
 {minute:52,team:'HOME',emoji:'🟨',text:'A'},
 {minute:52,team:'HOME',emoji:'🟨',text:'B'},
 {minute:52,team:'AWAY',emoji:'🟨',text:'C'},
 {minute:52,team:'HOME',emoji:'🥅',text:'Chute 1'},
 {minute:52,team:'HOME',emoji:'🥅',text:'Chute 2'},
 {minute:53,team:'HOME',emoji:'↗️',text:'Chute fora'}
]);
assert.equal(grouped.length,4);
assert.equal(grouped.find(g=>g.emoji==='🟨'&&g.team==='HOME').count,2);
assert.equal(grouped.find(g=>g.emoji==='🥅').count,2);
assert.equal(grouped.find(g=>g.team==='AWAY').count,1);
assert.equal(ui.exponent(2),'²');
assert.equal(ui.exponent(13),'¹³');
assert.equal(ui.exponent(1),'');
assert.equal(ui.hasThermometer({has_saved_thermometer:true}),true);
assert.equal(ui.hasThermometer({pressure:{score:45}}),false);
assert.equal(ui.hasThermometer({}, {thermometer:{points:[{minute:3,value:45}]}}),true);
const pressure=Array.from({length:30},(_,i)=>({minute:i+1,value:i<20?46:8}));
assert.equal(ui.coldAt(pressure,30).active,true);
assert.equal(ui.coldAt(pressure.slice(0,11),30).active,false);
assert.equal(ui.coldAt([],30).active,false);
assert.equal(ui.coldAt(Array.from({length:30},(_,i)=>({minute:i+1,value:6})),30).active,false);
const forecast={available:true,forecast:{one_x_two:{home:46,draw:30,away:24},over_2_5_pct:57,btts_yes_pct:55},sample:{home:{n:10},away:{n:10}}};
const rec=ui.recommendations(forecast,'Mandante','Visitante');
assert.equal(rec.available,true);
assert.equal(rec.items.length,4);
assert.ok(rec.items.every(x=>x.prob>=0&&x.prob<=100));
assert.equal(ui.recommendations({...forecast,sample:{home:{n:2},away:{n:10}}},'H','A').available,false);
assert.match(ui.playerState({name:'João'},'starter',true,'live',[{type:'substitution',player_out:'Joao',m:63}]),/Saiu aos 63/);
assert.match(ui.playerState({name:'João'},'starter',true,'live',[]),/presença atual não verificada/);
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
assert.match(html,/id="only-thermometer"/);
assert.match(html,/fourPreliveSuggestions/);
assert.match(html,/nexus-v531\.js/);
let inline=0;
for(const m of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)){
 if(m[1].trim()){new vm.Script(m[1],{filename:'index-inline-'+(++inline)+'.js'});}
}
assert.ok(inline>0);
console.log('NEXUS 5.31: agrupamento, queda de pressão, pré-live, escalações e sintaxe OK');
