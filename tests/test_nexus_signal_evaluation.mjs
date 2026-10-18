import { createRequire } from 'node:module';
const require=createRequire(import.meta.url);
const assert=require('node:assert/strict');
const model=require('../web/nexus-signal-evaluation.js');
const items=[
 {id:'a',match_id:'g1',rule:'strong',icon:'🔥',minute:22,team:'home',
  home:'Casa',away:'Fora',league:'Liga',captured_at:'2026-10-09T03:00:00Z',
  outcomes:{'10':'gol_confirmado'}},
 {id:'b',match_id:'g2',rule:'strong',icon:'🔥',minute:55,team:'away',
  home:'Casa',away:'Fora',league:'Liga',captured_at:'2026-10-09T04:00:00Z',
  outcomes:{'10':'sem_gol_confirmado'}},
 {id:'c',match_id:'g3',rule:'strong',icon:'🔥',minute:66,team:'away',
  home:'Casa',away:'Fora',league:'Liga',captured_at:'2026-10-09T04:00:00Z',
  outcomes:{'10':'pendente'}},
];
const a=model.fallback({items:[items[0],items[0],items[1],items[2]]});
assert.equal(a.summary.observations,3);
assert.equal(a.summary.settled,2);
assert.equal(a.summary.rate_pct,50);
assert.equal(a.views['10'].by_team.length,2);
assert.equal(a.views['10'].by_minute_band.length,3);
assert.equal(a.views['10'].evolution.at(-1).cumulative_settled,2);
assert.equal(model.cleanHTML('<img src=x>'),'&lt;img src=x&gt;');
assert.equal(model.fallback({items:[]}).summary.rate_pct,null);
assert.equal(model.fallback({items:[{...items[0],outcomes:{'40':'gol_confirmado'}}]}).horizons['40'].hits,1);
assert.equal(model.fallback({items:[{...items[0],outcomes:{'40':'pendente'}}]}).horizons['40'].settled,0);
const fs=require('node:fs');
const source=fs.readFileSync(new URL('../web/nexus-signal-evaluation.js',import.meta.url),'utf8');
assert.match(source,/nexus-eval-unit/);
assert.match(source,/Primeiro alerta de cada jogo/);
assert.match(source,/market==='goal'/);
console.log('NEXUS avaliação de sinais 5 a 40 min: ok');