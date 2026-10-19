import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const h=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const start=h.indexOf('function historicalPriceAuditHTML(d){');
const end=h.indexOf('function renderDetailBody(){',start);
assert.ok(start>0&&end>start);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ctx={esc,Number,Array};vm.runInNewContext(h.slice(start,end)+'this.render=historicalPriceAuditHTML;',ctx);
const q={type:'historical_price_movement_not_ev',bookmaker:'Pinnacle',selection:'home',
captured_odd:2.4,historical_last_odd:2.2,movement_pct:9.09,last_at:'2026-10-19T12:00:00Z'};
assert.equal(ctx.render({phase:'live',odds_historical_audit:[q]}),'');
assert.match(ctx.render({phase:'finished',odds_historical_audit:[q]}),/Pinnacle/);
assert.match(ctx.render({phase:'finished',odds_historical_audit:[q]}),/Não significa EV\+/);
assert.ok(!ctx.render({phase:'finished',odds_historical_audit:[{...q,bookmaker:'<img onerror=1>'}]}).includes('<img'));
console.log('NEXUS historical quote audit: finished only, no EV, HTML escaping OK');
