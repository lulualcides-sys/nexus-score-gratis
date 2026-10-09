import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const script=readFileSync(new URL('../web/nexus-web-polish.js',import.meta.url),'utf8');
const context={window:{}};
vm.runInNewContext(script,context);
const {projection,confrontation}=context.window.NexusWebPolish;
assert.equal(typeof projection,'function');
assert.equal(typeof confrontation,'function');
const historical={
 available:true,source:'FotMob · histórico',
 sample:{
   home:{n:10,gf:1.8,ga:0.9,avg_goals_for:1.8,avg_goals_against:0.9,
         recent:[{opponent:'X',result:'V',gf:2,ga:1,venue:'Casa'}]},
   away:{n:10,gf:1.3,ga:1.4,avg_goals_for:1.3,avg_goals_against:1.4,
         recent:[{opponent:'Y',result:'D',gf:0,ga:2,venue:'Fora'}]}},
 forecast:{
  expected_goals:{home:1.8,away:1.2},
  one_x_two:{home:50.4,draw:23.6,away:26},
  over_2_5_pct:55.7,btts_yes_pct:58.9,
  top_scores:[{score:'1-1',probability:11.5},{score:'2-1',probability:10.3}],
  periods:{first:[{label:'Gol no primeiro tempo',value:72}],
           second:[{label:'Gol no segundo tempo',value:68}]}}
};
const g={id:'sample',home:'A',away:'B',phase:'finished',
 home_score:2,away_score:1,start_timestamp:1750000000,
 prelive:historical,stats:{home:{shots_on:8,xg:1.9},away:{shots_on:3,xg:0.8}},
 head_to_head:[
  {home:'B',away:'A',score:'0-2',date:'2026-01-02'},
  {home:'A',away:'B',score:'1-1',date:'2025-01-03'},
  {home:'A',away:'B',score:'3-0',date:'2024-01-03'}
 ]};
const p=projection(g,historical);
assert.match(p,/Simulação retrospectiva/);
assert.match(p,/50,4%/);
assert.match(p,/58,9%/);
assert.match(p,/2-1/);
assert.match(p,/Over 2.5/);
assert.match(p,/Não é|não é|NÃO previsão/);
const matchup=confrontation(g);
assert.match(matchup,/Histórico direto/);
assert.match(matchup,/3 partidas verificadas/);
assert.match(matchup,/A/);
assert.match(matchup,/B/);
assert.match(matchup,/Sequência recente/);
const noData=confrontation({...g,head_to_head:[]});
assert.match(noData,/Nenhum confronto direto confiável/);
const noProjection=projection({...g,prelive:{available:false,reason:'Amostra insuficiente'}},{available:false,reason:'Amostra insuficiente'});
assert.match(noProjection,/Amostra insuficiente/);
assert.ok(!/undefined%|NaN%/.test(noProjection));
const scheduled=projection({...g,phase:'scheduled'},historical);
assert.match(scheduled,/Modelo Poisson experimental/);
assert.doesNotMatch(scheduled,/Simulação retrospectiva/);
console.log('NEXUS refinamentos: projeções, forma e confronto OK');
