import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const audit=require('../web/nexus-audit-v532.js');
const stamp=new Date().toISOString(),now=Date.now();
assert.equal(audit.freshness({
 phase:'live',minute:47,observed_at:stamp,pressure_observed_at:stamp,
 thermometer:{points:[{minute:45,value:60},{minute:47,value:65}]}
},now).pressureFresh,true);
assert.equal(audit.freshness({
 phase:'live',minute:47,observed_at:stamp,pressure_observed_at:stamp,
 thermometer:{points:[{minute:12,value:60}]}
},now).pressureFresh,false);
assert.equal(audit.freshness({
 phase:'live',minute:47,
 observed_at:'2020-01-01T00:00:00Z',
 pressure_observed_at:'2020-01-01T00:00:00Z',
 thermometer:{points:[{minute:47,value:90}]}
},now).pressureFresh,false);
const forecast={captured_at:stamp,model:'experimental',model_status:'experimental_uncalibrated',
 indications:[
 {market:'1x2',selection:'home',probability:48},
 {market:'double_chance',selection:'1X',probability:78},
 {market:'over_under_25',selection:'over',probability:55},
 {market:'btts',selection:'yes',probability:52}
 ],odds:null,settlement:null,forecast:{one_x_two:{home:48,draw:30,away:22}}};
assert.match(audit.report(forecast,{phase:'live'}),/PRÉ-LIVE QUE FICOU SALVO/);
assert.match(audit.report(forecast,{phase:'live'}),/EV INDISPONÍVEL/);
assert.match(audit.report(forecast,{phase:'live'}),/AGUARDANDO/);
const ended={...forecast,settlement:{score:'2-1',hits:3,count:4,
 checks:[{market:'1x2',selection:'home',result:'hit'},
 {market:'double_chance',selection:'1X',result:'hit'},
 {market:'over_under_25',selection:'over',result:'hit'},
 {market:'btts',selection:'yes',result:'miss'}]}};
assert.match(audit.report(ended,{phase:'finished'}),/3 de 4/);
assert.match(audit.report(ended,{phase:'finished'}),/ERROU/);
assert.match(audit.archive([{home:'Time A',away:'Time B',day:'2026-10-17',league:'Liga',pregame_baseline:ended}]),/Time A/);
assert.doesNotMatch(audit.report({...forecast,model:'<script>x</script>'},{}),/<script>/);
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
for(const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)){
 if(match[1].trim()) new vm.Script(match[1]);
}
assert.match(html,/src="\.\/nexus-audit-v532\.js"/);
assert.match(html,/d\.pregame_baseline\?NexusMarketQuality\.render\(d\.pregame_baseline,d\)/);
assert.match(html,/data-lab-tab="pregame"/);
console.log('NEXUS: freshness, EV status, pregame archive and inline syntax OK');
