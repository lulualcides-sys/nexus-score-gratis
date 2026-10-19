import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import fs from 'node:fs';
import vm from 'node:vm';
const require=createRequire(import.meta.url);
const c=require('../web/nexus-league-coverage.js');
for(const name of ['Premier League','La Liga','Serie A','Bundesliga','Ligue 1','UEFA Champions League','Brasileirão Série A','Brazilian Serie B','Copa do Brasil','Copa Libertadores','Copa Sudamericana','Primeira Liga','Eredivisie','Liga MX','MLS'])assert.equal(c.category(name),true,name+' is major');
for(const name of ['English League Two','J2 League','K League 2','Primera B','Conference North','Women Premier League','U20 Bundesliga','friendly match','Swiss Super League','Romanian Superliga','Liga 1 Peru','liga expansion'])assert.equal(c.category(name),false,name+' is minor');
const match={league:'Premier League',phase:'live',stats:{home:{shots_on:0},away:{shots_on:3}},home:'Home',away:'Away'};
const agenda={league:'Copa do Brasil',phase:'scheduled',start_timestamp:1792500000,home:'Casa',away:'Fora',source:'ESPN'};
const noCoverage={league:'La Liga',phase:'live',stats:{home:{},away:{}}};
assert.equal(c.level(match),2);
assert.equal(c.coverageStatus(match),'parcial');
assert.equal(c.coverageStatus({...match,pressure:[{m:1,v:40},{m:2,v:42},{m:3,v:45}],
  stats:{home:{shots_on:2,corners:3},away:{shots_on:0,corners:1}}}),'completa');
assert.equal(c.coverageStatus(noCoverage),'insuficiente');
assert.equal(c.level(agenda),1);
assert.equal(c.visible(noCoverage),false);
assert.equal(c.visible({...match,league:'League Two'}),false);
assert.equal(c.leagueStats([match,agenda,noCoverage]).length,2);
const clock=1792000000;
const observed=new Date(clock*1000-3*60000).toISOString();
const complete={...match,observed_at:observed,
 stats_observed_at:observed,pressure_observed_at:observed,
 pressure:[{m:1,v:40},{m:2,v:42},{m:3,v:45}],
 stats:{home:{shots_on:2,corners:3},away:{shots_on:0,corners:1}}};
const higher=c.analysisPriority(complete,clock);
const lower=c.analysisPriority(match,clock);
assert.equal(c.coverageStatus(complete,clock),'completa');
assert.equal(c.analysisPriority(complete,clock).freshness,'fresh');
const stale={...complete,observed_at:new Date((clock-3600)*1000).toISOString(),
 stats_observed_at:new Date((clock-3600)*1000).toISOString(),
 pressure_observed_at:new Date((clock-3600)*1000).toISOString()};
assert.equal(c.coverageStatus(stale,clock),'parcial');
assert.equal(c.analysisPriority(stale,clock).freshness,'stale');
assert.ok(c.analysisPriority(stale,clock).score<=10);
assert.equal(c.coverageEvidence(stale,clock).stale_live,true);
assert.match(c.coverageEvidence(stale,clock).reason,/sem horário recente/);
const undated={...complete,observed_at:undefined,stats_observed_at:undefined,
 pressure_observed_at:undefined};
assert.equal(c.coverageStatus(undated,clock),'parcial');
assert.equal(c.analysisPriority(undated,clock).freshness,'unknown');
assert.equal(c.observationFreshness(new Date((clock+3600)*1000).toISOString(),clock),'future');
assert.equal(c.observationFreshness('invalid',clock),'unknown');
const withOldPrice={...stale,odds:[{odd:2.3,source:'Betano'}]};
assert.equal(c.analysisPriority(withOldPrice,clock).score,c.analysisPriority(stale,clock).score);
assert.ok(higher.score>lower.score);
assert.equal(higher.kind,'data_quality_not_betting_signal');
assert.match(fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8'),/NexusLeagueCoverage\.analysisPriority\(/);
assert.equal(c.analysisPriority(noCoverage).status,'insuficiente');
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
assert.match(html,/NexusLeagueCoverage\.visible\(m\)/);
assert.match(html,/leagueStats\(state\.list\)/);
assert.match(html,/nexus-league-coverage\.js/);
assert.doesNotMatch(html,/id="league-scope-toggle"/);
for(const m of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi))if(m[1].trim())new vm.Script(m[1]);
console.log('NEXUS curated competitions: coverage based, unmodified historical data, UI smoke OK');
