import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const src=fs.readFileSync(new URL('../web/nexus-original-enrich.js',import.meta.url),'utf8');
const fixture={
 id:'fotmob-111',home:'Mandante',away:'Visitante',phase:'scheduled',
 minute:0,start_timestamp:1792000000,score:null,pressure:[],events:[],
 form:{home:{available:10,avg_goals_for:1.5,avg_goals_against:1.2,games:[]},
       away:{available:10,avg_goals_for:1.1,avg_goals_against:1.5,games:[]}},
 stats:{home:{},away:{}},
 lineups:{
  home:{formation:'4-3-3',status:'confirmed',starters:[{name:'Titular Mandante',number:'9'}],
        subs:[{name:'Reserva Mandante',number:'12'}],lineup_type:'standard'},
  away:{formation:'4-4-2',status:'predicted',starters:[{name:'Provável Visitante',number:'10'}],
        subs:[],lineup_type:'expected'}},
 odds:[
  {sel:'home',odd:2.05,at:'2026-10-09T11:00:00Z',source:'ESPN',bookmaker:'Casa A'},
  {sel:'draw',odd:3.20,at:'2026-10-09T11:00:00Z',source:'ESPN',bookmaker:'Casa A'},
  {sel:'away',odd:3.70,at:'2026-10-09T11:00:00Z',source:'ESPN',bookmaker:'Casa A'}
 ]};
const base={...fixture,stats:fixture.stats,lineups:{},odds:{markets:{}}};
const mockWindow={
 location:{href:'https://nexus-score-gratis.pages.dev/'},
 fetch:async()=>({ok:true,clone(){return this},async json(){return base}}),
 NexusWebBridge:{data:async()=>({games:[fixture]})}
};
vm.runInNewContext(src,{window:mockWindow,Response,console,URL});
const fb=await (await mockWindow.fetch('/api/prelive/fotmob-111')).json();
assert.equal(fb.odds.available,true);
assert.equal(fb.odds.markets['1x2'].home,2.05);
assert.equal(fb.odds.markets['1x2'].draw,3.20);
assert.equal(fb.odds.markets['1x2'].away,3.70);
assert.equal(fb.odds.bookmaker,'Casa A');
assert.equal(fb.lineups.home_detail.official,true);
assert.equal(fb.lineups.away_detail.official,false);
assert.equal(fb.lineups.home_detail.xi[0].name,'Titular Mandante');
assert.equal(fb.lineups.home_detail.bench[0].name,'Reserva Mandante');
assert.equal(fb.lineups.away_detail.status,'provável');
const empty={...fixture,odds:[],lineups:{},form:{home:{available:0},away:{available:0}}};
const w2={...mockWindow,
 fetch:async()=>({ok:true,clone(){return this},async json(){return base}}),
 NexusWebBridge:{data:async()=>({games:[empty]})}};
vm.runInNewContext(src,{window:w2,Response,console,URL});
const p2=await (await w2.fetch('/api/prelive/fotmob-111')).json();
assert.equal(p2.odds.available,false);
assert.equal(p2.lineups.status,'aguardando confirmação');
assert.equal(p2.available,false);
console.log('NEXUS: odds 1/X/2 e escalações confirmadas/prováveis no pré-jogo OK');
