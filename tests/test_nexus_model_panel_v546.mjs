import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const start=source.indexOf('function modelValidationHTML(r){');
const stop=source.indexOf('function renderCloud(){',start);
assert.ok(start>0&&stop>start);
const context={Number,Object,String,esc:x=>String(x??'').replaceAll('<','&lt;')};
vm.runInNewContext(source.slice(start,stop)+';this.show=modelValidationHTML;',context);
const v=context.show({eligible:12,minimum_for_review:200,validated:false,
 overall:{n:12,brier:.53,log_loss:1.04,top_pick_accuracy_pct:48.2},by_league:[]});
assert.match(v,/EXPERIMENTAL/);
assert.match(v,/Brier/);
assert.match(v,/EV\+/);
assert.match(context.show(null),/EV\+ indisponível/);
const binary=context.show({eligible:28,minimum_for_review:200,validated:false,
 overall:{n:28,brier:.51,log_loss:1.03,top_pick_accuracy_pct:42},
 by_league:[],binary_markets:{markets:[
  {market:'over_under_25',label:'Mais de 2,5 gols',n:25,
   brier:.214,calibration_error_pct:5.4,validated:false,
   chronological:{evaluated:1,brier:.217,baseline_brier:.248}},
  {market:'btts',label:'Ambas marcam · Sim',n:22,brier:.243,
   calibration_error_pct:9.1,validated:false,
   chronological:{evaluated:0,brier:null,baseline_brier:null}}
 ]}});
assert.match(binary,/Mais de 2,5 gols/);
assert.match(binary,/Ambas marcam/);
assert.match(binary,/não validada para EV\+/);
assert.match(binary,/Teste cronológico/);
const injected=context.show({eligible:1,validated:false,overall:{},
 by_league:[],binary_markets:{markets:[{label:'<img onerror=1>',n:1}]}});
assert.ok(!injected.includes('<img'));
assert.match(injected,/&lt;img/);

console.log('NEXUS V546: auditoria de calibracao exibida sem liberar EV OK');
