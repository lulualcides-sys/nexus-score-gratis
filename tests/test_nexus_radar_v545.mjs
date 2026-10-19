import assert from 'node:assert/strict';
import fs from 'node:fs';
import coverage from '../web/nexus-league-coverage.js';
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
assert.match(html,/id="radar-sort"/);
assert.match(html,/id="radar-complete"/);
assert.match(html,/nexus-coverage-completa/);
assert.match(html,/coverageEvidence\(d\|\|m\)/);
const match={league:'Premier League',phase:'live',home:'A',away:'B',
  stats:{home:{shots_on:4,corners:3},away:{shots_on:2,corners:2}},
  pressure:[{m:1,v:10},{m:2,v:15},{m:3,v:12}]};
assert.equal(coverage.coverageEvidence(match).status,'completa');
assert.equal(coverage.coverageEvidence({...match,pressure:[]}).status,'parcial');
assert.equal(coverage.coverageEvidence({...match,league:'Youth Cup'}).status,'insuficiente');
console.log('NEXUS V545 radar: filtros e qualidade fundamentada OK');
