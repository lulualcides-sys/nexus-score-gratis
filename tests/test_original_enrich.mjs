import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const src=fs.readFileSync(new URL('../web/nexus-original-enrich.js',import.meta.url),'utf8');
const fixture={id:'fotmob-5',home:'Casa',away:'Fora',phase:'finished',
  minute:0,start_timestamp:1791543600,score:'2-1',
  pressure:Array.from({length:30},(_,i)=>({m:i+1,v:i<5?20:80})),
  events:[{m:14,type:'shot_on',side:'home',text:'No gol confirmado'},
          {m:21,type:'shot_off',side:'away',text:'Fora confirmado'},
          {m:25,type:'goal',side:'home',text:'Gol registrado'}],
  form:{home:{available:10,avg_goals_for:1.8,avg_goals_against:1.1,games:[]},
    away:{available:10,avg_goals_for:1.3,avg_goals_against:1.2,games:[]}},
  stats:{home:{shots_on:7,big_chances:2,corners:9},away:{shots_on:2,big_chances:1,corners:3}},
  odds:[]};
const mockBridge={data:async()=>({games:[fixture]})};
const base={...fixture,stats:fixture.stats,scout_pressure:{available:true}};
const callbacks=[];
const mockWindow={
  location:{href:'https://nexus-score-gratis.pages.dev/'},
  fetch:async(request)=>({
    ok:true,clone(){return this},
    async json(){return request.includes('/prelive/')?{available:true}:base}
  }),
  NexusWebBridge:mockBridge
};
const context={window:mockWindow,Response,console,URL};
vm.runInNewContext(src,context);
const x=mockWindow.NexusOriginalEnrichment;
const points=fixture.pressure.map(p=>({minute:p.m,value:p.v}));
assert.equal(x.pressureWindow(points,30,10).level,'CRITICO');
assert.equal(x.pressureWindow(points.slice(0,4),30,10).valid,false);
const forecast=x.forecast(fixture);
assert.equal(forecast.available,true);
const probs=forecast.forecast.one_x_two;
assert.ok(Math.abs(probs.home+probs.draw+probs.away-100)<=.2);
assert.equal(forecast.forecast.top_scores.length,3);
const incomplete={...fixture,form:{home:{available:3},away:{available:10}}};
assert.equal(x.forecast(incomplete).available,false);
const detail=x.instrument(fixture,base);
assert.ok(detail.indicator_board.length>=11);
assert.ok(detail.signal_timeline.some(a=>a.emoji==='🔥'&&a.basis==='graph'));
assert.ok(detail.signal_timeline.some(a=>a.emoji==='🥅'&&a.minute===14&&a.basis==='event'));
const chance=x.instrument({...fixture,events:[{m:32,type:'big_chance_missed',side:'away',text:'Chance perdida'}]},base);
assert.ok(chance.signal_timeline.some(a=>a.emoji==='💣❌'&&a.team==='AWAY'&&a.basis==='event'));
assert.ok(!chance.signal_timeline.some(a=>a.emoji==='💣❌'&&a.team==='HOME'));
assert.ok(detail.signal_timeline.filter(a=>a.basis==='snapshot').every(e=>e.minute===30));
assert.equal(detail.pressure.level,'CRITICO');
for(const n of [5,10,15]){
  const w=detail.scout_pressure.windows[String(n)];
  assert.equal(w.valid,true);
  assert.equal(w.samples,n);
  assert.equal(w.expected,n);
  assert.equal(typeof w.home_force,'number');
  assert.equal(typeof w.away_force,'number');
}
const resp=await mockWindow.fetch('/api/match/fotmob-5');
const payload=await resp.json();
assert.ok(payload.projections?.model_estimate);
assert.ok(payload.indicator_board);
const fb=await (await mockWindow.fetch('/api/prelive/fotmob-5')).json();
assert.equal(fb.forecast.top_scores.length,3);
const lab=await (await mockWindow.fetch('/api/v5/dashboard')).json();
assert.equal(lab.version.includes('5.29'),true);
assert.ok(Array.isArray(lab.quality));
assert.ok(Array.isArray(lab.alerts));
assert.equal(lab.backtest.evaluated_fixtures,0);
assert.ok(Array.isArray(lab.radar));
const cloud=await (await mockWindow.fetch('/api/github-collector')).json();
assert.equal(cloud.connected,true);
assert.ok(Array.isArray(cloud.games));
assert.equal(cloud.platform_snapshot,null);
assert.equal(cloud.audit.trades_verified,0);
assert.ok(!JSON.stringify(cloud).includes('netPl'));
console.log('NEXUS 5.29 bridge: projeções originais, pressão, EV seguro e timeline OK');
