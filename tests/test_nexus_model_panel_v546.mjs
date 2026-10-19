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
console.log('NEXUS V546: auditoria de calibracao exibida sem liberar EV OK');
