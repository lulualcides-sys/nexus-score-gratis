import assert from 'node:assert/strict';
import fs from 'node:fs';
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const css=fs.readFileSync(new URL('../web/nexus-simple.css',import.meta.url),'utf8');
const src=html.slice(html.indexOf('function nexusReconcileFixtures(games){'),html.indexOf('function baseMatches'));
const NexusLeagueCoverage={profile:c=>({'ita.1':{label:'Serie A · Itália'}})[c]||null};
const f=new Function('NexusLeagueCoverage',src+';return {nexusReconcileFixtures,nexusLeagueLabel,nexusTeamCore};')(NexusLeagueCoverage);
const t=1795960800;
const out=f.nexusReconcileFixtures([
 {id:'espn',league:'arg.1',home:'Gimnasia La Plata',away:"Newell's Old Boys",start_timestamp:t,phase:'live'},
 {id:'fm',league:'Liga Profesional',home:'Gimnasia LP',away:"Newell's Old Boys",start_timestamp:t+180,phase:'live',pressure:[1]},
 {id:'other',league:'Liga Profesional',home:'Gimnasia Mendoza',away:'Chacarita',start_timestamp:t,phase:'live'}]);
assert.equal(out.length,2,'mesmo jogo de ESPN e FotMob vira um');
assert.equal(out[0].league,'Liga Profesional','nome legível vence o código');
assert.equal(f.nexusLeagueLabel({league:'ita.1'}),'Serie A · Itália');
assert.equal(f.nexusLeagueLabel({league:'Premier League'}),'Premier League');
assert.match(html,/Math\.round\(\+v\)/,'posse arredondada');
assert.match(html,/nx-pre-odds/);
for(const sel of ['.iara-ev','.pressure-scoreboard-odds','#detail-body>.scout-main','.thermo-badge'])assert.ok(css.includes(sel),sel);
console.log('NEXUS lista e detalhe limpos: OK');
