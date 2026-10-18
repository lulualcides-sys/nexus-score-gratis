import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const iaraSource=fs.readFileSync(new URL('../web/nexus-iara.js',import.meta.url),'utf8');
const auditSource=fs.readFileSync(new URL('../web/nexus-audit-v532.js',import.meta.url),'utf8');
const window={};
vm.runInNewContext(iaraSource,{window,Date,console});
vm.runInNewContext(auditSource,{window,Date,console});
const start=html.indexOf('function hotGameSignal(d){'),end=html.indexOf('function renderDetail(){',start);
assert.ok(start>=0&&end>start,'mecanismo de alertas encontrado');
const state={demo:false,reference:false,settings:{alerts_enabled:true,threshold:55},lastAlert:new Map()};
const notifications=[];
const ctx={state,window,NexusAudit:window.NexusAudit,
 notify:(...args)=>notifications.push(args),Date,console};
vm.runInNewContext(html.slice(start,end),ctx);
const now=new Date().toISOString();
const base={id:'fotmob-1000',home:'Vélez',away:'Gimnasia',phase:'live',minute:35,live:true,
 score:'0-0',home_score:0,away_score:0,start_timestamp:Math.floor(Date.now()/1000)-35*60,
 observed_at:now,pressure_observed_at:now,
 pressure:{score:81,dominant:'HOME'},
 thermometer:{points:Array.from({length:15},(_,i)=>({minute:21+i,value:60}))},
 incidents:[{minute:34,type:'shot_on',emoji:'🥅',team:'HOME',text:'No gol confirmado'}],
 stats:{home:{shots_on:3,big_chances:1},away:{shots_on:1,big_chances:0}},
 indicator_board:[{emoji:'🔥',state:'active',team:'HOME'}]};
const s=ctx.hotGameSignal(base);
assert.ok(s,'leitura recente com pressão e chute deve sinalizar');
ctx.maybeAlert(base);
assert.equal(notifications.length,1);
assert.match(notifications[0][0],/JOGO|pressão forte/);
assert.equal(notifications[0][3],base.id,'ID do jogo enviado ao toast clicável');
ctx.maybeAlert(base);
assert.equal(notifications.length,1,'deduplicação em 8 minutos');
assert.equal(ctx.hotGameSignal({...base,observed_at:'2025-01-01T01:00:00Z'}),null);
assert.equal(ctx.hotGameSignal({...base,thermometer:{points:[{minute:11,value:90}]}}),null);
assert.equal(ctx.hotGameSignal({...base,incidents:[]}),null,
 'Não chamar de gol próximo usando só scouts acumulados');
state.settings.threshold=90;
assert.equal(ctx.hotGameSignal(base),null);
state.settings.threshold=55;
state.demo=true;
assert.equal(ctx.hotGameSignal(base),null);
assert.doesNotMatch(html,/src="\.\/nexus-activity\.js"/);
assert.doesNotMatch(html,/href="\.\/nexus-activity\.css"/);
assert.match(html,/font=type==='🟨'\|\|type==='🟥'\?12\.75/);
assert.match(html,/case 'projections':html\+=classicProjection57\(d\)/);
assert.match(html,/function notify\(message,type='normal',title='',matchId=null\)/);
assert.match(html,/document\.createElement\(clickable\?'button':'div'\)/);
const polish=fs.readFileSync(new URL('../web/nexus-web-polish.js',import.meta.url),'utf8');
assert.doesNotMatch(polish,/window\.comparisonProjection56\s*=/,
 'acabamento não pode sobrescrever o prognóstico congelado');
assert.match(polish,/window\.comparisonProjectionLegacy/);
for(const m of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)){
 if(m[1].trim())new vm.Script(m[1]);
}
console.log('NEXUS 5.33: alertas apenas com fonte recente e chute confirmado, clicáveis, sem gráfico extra e pré-live intacto OK');
