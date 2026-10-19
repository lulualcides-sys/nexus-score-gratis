import assert from 'node:assert/strict';
import fs from 'node:fs';
import coverage from '../web/nexus-league-coverage.js';
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
assert.match(html,/id="radar-sort"/);
assert.match(html,/id="radar-complete"/);
assert.match(html,/nexus-coverage-completa/);
assert.match(html,/SEM HORÁRIO/);
assert.match(html,/DADOS ANTIGOS/);
assert.match(html,/quality\.stale_live/);
assert.match(html,/coverageEvidence\(d\|\|m\)/);
const now=1792000000;
const recent=new Date((now-120)*1000).toISOString();
const older=new Date((now-4500)*1000).toISOString();
const match={league:'Premier League',phase:'live',home:'A',away:'B',
  observed_at:recent,stats_observed_at:recent,pressure_observed_at:recent,
  stats:{home:{shots_on:4,corners:3},away:{shots_on:2,corners:2}},
  pressure:[{m:1,v:10},{m:2,v:15},{m:3,v:12}]};
assert.equal(coverage.coverageEvidence(match,now).status,'completa');
assert.equal(coverage.coverageEvidence({...match,pressure:[]},now).status,'parcial');
assert.equal(coverage.coverageEvidence({...match,league:'Youth Cup'},now).status,'insuficiente');
assert.equal(coverage.coverageEvidence({...match,pressure_observed_at:older},now).status,'parcial');
assert.equal(coverage.coverageEvidence({...match,stats_observed_at:null},now).status,'parcial');
console.log('NEXUS V545 radar: filtros e qualidade fundamentada OK');
