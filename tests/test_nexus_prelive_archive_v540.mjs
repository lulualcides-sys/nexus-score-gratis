import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const audit=require('../web/nexus-audit-v532.js');
const b=(n,settled=false)=>({
 captured_at:'2026-10-17T20:39:00Z',model:'Poisson não calibrado',
 forecast:{one_x_two:{home:n,draw:25,away:75-n}},
 indications:[
  {market:'1x2',selection:'home',probability:n},
  {market:'double_chance',selection:'12',probability:75},
  {market:'over_under_25',selection:'under',probability:56},
  {market:'btts',selection:'no',probability:55}],
 settlement:settled?{score:'2-0',hits:3,count:4,
  checks:[{market:'1x2',selection:'home',result:'hit'},
          {market:'double_chance',selection:'12',result:'hit'},
          {market:'over_under_25',selection:'under',result:'hit'},
          {market:'btts',selection:'no',result:'hit'}]}:null});
const grouped=[{
 id:'espn-1',home:'São Paulo',away:'Vasco da Gama',day:'2026-10-17',
 league:'Série A',phase:'finished',score:'2-0',variant_count:2,
 forecast_divergence:true,variants:[
  {id:'espn-1',source:'ESPN',league:'bra.1',pregame_baseline:b(37,true)},
  {id:'fotmob-1',source:'FotMob',league:'Série A',pregame_baseline:b(46,true)}]
}];
const out=audit.archive(grouped);
assert.match(out,/1<\/strong> partidas distintas/);
assert.match(out,/2 versões originais/);
assert.match(out,/São Paulo/);
assert.match(out,/PREVISÕES DIFERENTES/);
assert.match(out,/Versão 1 · ESPN/);
assert.match(out,/Versão 2 · FotMob/);
assert.match(out,/37%/);
assert.match(out,/46%/);
assert.match(out,/FT 2-0/);
assert.equal((out.match(/class="nexus-audit-archive-row"/g)||[]).length,1);
assert.match(out,/<details class="nexus-audit-list-toggle">/);
assert.match(out,/Mostrar \/ ocultar lista/);
const conflict=audit.archive([{...grouped[0],result_conflict:true,
 phase:'scheduled',score:'',variants:[
  {...grouped[0].variants[0],pregame_baseline:b(37)}]}]);
assert.match(conflict,/PLACARES CONFLITANTES/);
assert.match(conflict,/avaliação fica suspensa/);
assert.doesNotMatch(conflict,/FT 2-0/);
const old=audit.archive([{home:'Casa',away:'Fora',day:'2026-10-17',
 league:'liga',pregame_baseline:b(37)}]);
assert.match(old,/Casa/);
assert.match(old,/1 versões originais/);
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
assert.match(html,/nexus-journal-toggle/);
assert.match(html,/Mostrar \/ ocultar lista de alertas/);
for(const x of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)){
 if(x[1].trim())new vm.Script(x[1]);
}
console.log('NEXUS v5.40: confronto único, versões preservadas, lista recolhível e sintaxe OK');
