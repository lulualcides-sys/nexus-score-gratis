import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const start=html.indexOf('function sourceHealthHTML(h){');
const end=html.indexOf('function modelValidationHTML(r){',start);
assert.ok(start>0&&end>start);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ctx={esc,Number,Array,String};
vm.runInNewContext(html.slice(start,end)+'this.show=sourceHealthHTML;',ctx);
assert.match(ctx.show(null),/indisponível/);
const h={scope:'observed_data_quality_not_ev',live_fresh:10,live_games_in_feed:14,
 fresh_live_with_recent_scouts:6,fresh_live_with_recent_pressure:2,
 scouts_pct_of_fresh_live:60,pressure_pct_of_fresh_live:20,
 collector_details_with_scouts:9,collector_details_queried:12,
 collector_scout_yield_pct:75,pregame_matches_with_price_comparison:4,
 live_matches_with_price_comparison:0,
 providers:{oddspapi:{status:'waiting_free_slot'},sofascore:{status:'blocked_403'}},
 warnings:['<img src=x onerror=alert(1)>']};
const view=ctx.show(h);
assert.match(view,/QUALIDADE DAS FONTES/);
assert.match(view,/60%/);
assert.match(view,/waiting_free_slot/);
assert.match(view,/blocked_403/);
assert.ok(!view.includes('<img'));
assert.match(view,/&lt;img/);
assert.match(html,/id="cloud-source-health"/);
assert.match(html,/sourceHealthHTML\(cloudData.source_health\)/);
console.log('NEXUS 5.47 quality feed: source status, missing info and XSS guards OK');
