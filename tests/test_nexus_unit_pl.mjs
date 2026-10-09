const assert=require('node:assert/strict');
const a=require('../web/nexus-unit-pl.js');
assert.deepEqual(a.normalize({status:'insufficient_data',settled:0,paper_pl_u:null}),{
  available:false,settled:0,pending:0,markets:[]});
const snapshot=a.normalize({status:'with_settlements',settled:3,pending:2,won:1,lost:2,
  profit_u:2.5,loss_u:2,paper_pl_u:.5,roi_pct:16.67,
  markets:[{market:'1x2',paper_pl_u:.5,profit_u:2.5,loss_u:2}]});
assert.equal(snapshot.available,true);
assert.equal(snapshot.profit,2.5);
assert.equal(snapshot.loss,2);
assert.equal(snapshot.net,.5);
assert.equal(snapshot.markets.length,1);
assert.equal(a.formatted(-1.5),'-1,50u');
assert.equal(a.formatted(null),'—');
assert.equal(a.escapeHTML('<script>alert(1)</script>'),'&lt;script&gt;alert(1)&lt;/script&gt;');
console.log('NEXUS unidades paper: ok');
