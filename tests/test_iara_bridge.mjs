import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const enrich=fs.readFileSync(new URL('../web/nexus-original-enrich.js',import.meta.url),'utf8');
const iara=fs.readFileSync(new URL('../web/nexus-iara.js',import.meta.url),'utf8');
const kickoff=Math.floor(Date.now()/1000)-35*60;
const time=new Date((kickoff-10*60)*1000).toISOString();
const points=Array.from({length:15},(_,i)=>({m:21+i,v:64}));
const teamForm=(gf,ga)=>({available:10,avg_goals_for:gf,
  avg_goals_against:ga,games:Array.from({length:10},()=>({gf:2,ga:1}))});
const game={
 id:'fotmob-123',home:'Mandante',away:'Visitante',phase:'live',minute:35,
 start_timestamp:kickoff,score:'1-0',source:'FotMob',
 pressure:points,events:[{m:23,type:'shot_on',side:'home',text:'Finalização no alvo'}],
 stats:{home:{shots_on:6,shots_off:4,big_chances:2,corners:7},
        away:{shots_on:1,shots_off:2,big_chances:0,corners:1}},
 form:{home:teamForm(1.9,1.0),away:teamForm(1.2,1.5)},
 odds:[{sel:'home',odd:2.3,at:time,source:'ESPN',bookmaker:'Casa A'},
       {sel:'draw',odd:3.25,at:time,source:'ESPN',bookmaker:'Casa A'},
       {sel:'away',odd:3.7,at:time,source:'ESPN',bookmaker:'Casa A'}],
 standings:{source:'FotMob',updated_at:new Date().toISOString(),
   home:{position:17,points:27,played:27,total_teams:20,level:'alta',
      reasons:[{kind:'sair_z4',label:'Sair da zona de rebaixamento',
      detail:'17º com 27 pontos; primeiro fora do Z4 com 28.'}]},
   away:{position:4,points:46,played:27,total_teams:20,level:'moderada',
      reasons:[{kind:'defender_g4',label:'Defender o G4',
      detail:'4º com 46 pontos; 5º tem 45.'}]}}
};
const base={id:game.id,home:game.home,away:game.away,phase:'live',
  live:true,minute:35,start_timestamp:kickoff,score:'1-0',
  home_score:1,away_score:0,stats:game.stats,incidents:[],
  thermometer:{points:points.map(p=>({minute:p.m,value:p.v}))}};
const window={
 location:{href:'https://nexus-score-gratis.pages.dev/'},
 fetch:async()=>new Response(JSON.stringify(base),{status:200,headers:{'Content-Type':'application/json'}}),
 NexusWebBridge:{data:async()=>({games:[game]})}
};
vm.runInNewContext(enrich,{window,Response,console,URL});
vm.runInNewContext(iara,{window,Response,console,URL});
const result=await (await window.fetch('/api/match/fotmob-123')).json();
const reading=window.NexusIara.evaluate(result);
assert.equal(reading.active,true);
assert.equal(result.standings.home.position,17);
assert.match(reading.intro,/Mandante está pressionando/);
assert.match(reading.intro,/sair da zona de rebaixamento/);
assert.equal(reading.motivation.list.length,2);
assert.equal(reading.motivation.list[1].label,'Defender o G4');
assert.ok(reading.value?.ev!==undefined,'EV teórico requer odd, hora e amostra pré-jogo');
const card=window.NexusIara.render(result);
assert.match(card,/EV teórico/);
assert.match(card,/não calibrado/);
assert.match(card,/Must Win|MUST WIN/);
assert.match(card,/Pode sair mais um gol/);
const stale={...game,pressure:points.map((p,i)=>({...p,m:i+1}))};
const w2={...window,fetch:async()=>new Response(JSON.stringify(base),{status:200}),NexusWebBridge:{data:async()=>({games:[stale]})}};
vm.runInNewContext(enrich,{window:w2,Response,console,URL});
vm.runInNewContext(iara,{window:w2,Response,console,URL});
const d2=await (await w2.fetch('/api/match/fotmob-123')).json();
assert.match(w2.NexusIara.evaluate(d2).intro,/curva de pressão parou/);
console.log('NEXUS IARA: dados de jogo → motor 5.29 → Must Win/EV+ → comentário web OK');
