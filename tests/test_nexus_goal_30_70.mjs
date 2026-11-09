import {createRequire} from "node:module";
import assert from "node:assert/strict";
const require=createRequire(import.meta.url);
const {interpret,html}=require("../web/nexus-goal-30-70.js");

const payload={
 schema:1,name:"NEXUS Gol 30–70",
 sample:{first_alert_per_match:200,settled:120,train:80,holdout:40},
 validation:{status:"no_verified_improvement_over_baseline",
     probability_released_for_live:false,brier_model:.245,brier_constant_baseline:.242,ece_holdout:.09},
 live:[{match_id:"a",home:"<img src=x onerror=alert(1)>",away:"Clube",
        minute:58,rule:"pressao",experimental_pct:72,factors:[{field:"regra",category:"forte"}]}]
};
let doc=html(payload);
assert.match(doc,/NEXUS|Radar de gol/);
assert.match(doc,/Sem %/);
assert.doesNotMatch(doc,/>72%/);
assert.match(doc,/NÃO superou/);
assert.ok(!doc.includes("<img src=x"));
assert.match(doc,/&lt;img/);
assert.equal(interpret(payload).percentageAllowed,false);
const validated={...payload,validation:{...payload.validation,
  probability_released_for_live:true,status:"better_than_constant_baseline_in_historical_holdout"}};
assert.match(html(validated),/72%/);
assert.match(html(validated),/experimental|observacional/i);
assert.match(html(null),/dados ainda não disponíveis/);
console.log("NEXUS indicador gol 30-70: interface de auditoria OK");
