import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const oldFile=fs.readFileSync(new URL('../web/nexus-web-polish.js',import.meta.url),'utf8');
const context={window:{}};
vm.runInNewContext(oldFile,context);
const i=html.indexOf('function classicProjection57(d){');
const j=html.indexOf('\nfunction preliveV5Card(p){',i);
assert.ok(i>=0&&j>i,'renderizador clássico encontrado');
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const classic=new Function('window','esc','liveProjection53','projectionsHTML',
 html.slice(i,j)+'\nreturn classicProjection57;')(
 context.window,esc,()=>'<section>ATUALIZAÇÃO AO VIVO EXPERIMENTAL</section>',
 ()=>'<section>SEM MODELO VERIFICADO</section>');

const frozen={
 captured_at:'2026-10-17T20:00:00+00:00',
 source:'Histórico esportivo verificado',
 model_status:'experimental_uncalibrated',
 forecast:{
  expected_goals:{home:1.61,away:0.88},
  one_x_two:{home:53,draw:26,away:21},
  over_2_5_pct:56,btts_yes_pct:48,
  top_scores:[{score:'1-0',probability:12.5},{score:'2-1',probability:10.2}]},
 sample:{home:{n:8,gf:1.8,ga:0.9},away:{n:8,gf:0.8,ga:1.4}}
};
const d={
 home:'Vélez Sarsfield',away:'Gimnasia Mendoza',
 score:'0-0',home_score:0,away_score:0,phase:'live',minute:39,
 start_timestamp:Date.parse('2026-10-17T21:00:00+00:00')/1000,
 pregame_baseline:frozen,
 prelive:{available:true,forecast:{...frozen.forecast,one_x_two:{home:8,draw:8,away:84}},sample:frozen.sample},
 stats:{home:{xg:0.44,shots_on:1},away:{xg:0.27,shots_on:0}}};
const saved=classic(d);
assert.match(saved,/VISUAL CLÁSSICO/);
assert.match(saved,/PRÉ-LIVE ORIGINAL · REGISTRADO/);
assert.match(saved,/Probabilidades de resultado · Match Odds/);
assert.match(saved,/53,0%/);
assert.match(saved,/Gols esperados · mandante/);
assert.match(saved,/Gols esperados · visitante/);
assert.match(saved,/Total esperado/);
assert.match(saved,/Over 2.5 FT/);
assert.match(saved,/Under 2.5 FT/);
assert.match(saved,/Ambas marcam · SIM/);
assert.match(saved,/Placares com maior probabilidade/);
assert.match(saved,/1-0/);
assert.match(saved,/xG observado/);
assert.match(saved,/Chutes no alvo/);
assert.match(saved,/ATUALIZAÇÃO AO VIVO EXPERIMENTAL/);
assert.match(saved,/nexus-prob-track/);
assert.doesNotMatch(saved,/84,0%/,'não trocar pré-live congelado por odds do modelo recalculado');
assert.doesNotMatch(saved,/NaN|undefined/);

const noBaseline=classic({...d,pregame_baseline:null});
assert.match(noBaseline,/SEM PRÉ-LIVE REGISTRADO/);
assert.match(noBaseline,/Modelo histórico ilustrativo/);
assert.doesNotMatch(noBaseline,/PRÉ-LIVE ORIGINAL · REGISTRADO/);
const oldFinished=classic({...d,pregame_baseline:null,phase:'finished'});
assert.match(oldFinished,/RECONSTRUÇÃO RETROSPECTIVA/);
assert.match(oldFinished,/Simulação retrospectiva/);
const withoutData=classic({...d,pregame_baseline:null,prelive:{available:false}});
assert.match(withoutData,/Amostra insuficiente|projeção|modelo/i);
const brokenStamp=classic({...d,pregame_baseline:{...frozen,captured_at:'2026-10-17T22:00:00+00:00'}});
assert.match(brokenStamp,/SEM PRÉ-LIVE REGISTRADO/);

assert.match(html,/case 'projections':html\+=classicProjection57\(d\)/);
assert.match(html,/NexusMarketQuality\.render\(d\.pregame_baseline,d\)/);
assert.match(html,/halftime:g\.halftime===true/);
assert.doesNotMatch(oldFile,/window\.comparisonProjection56\s*=/);
for(const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)){
 if(match[1].trim())new vm.Script(match[1]);
}
console.log('NEXUS 5.34: barras antigas, placares, gols esperados, pré-live imutável, comparativo e sintaxe OK');
