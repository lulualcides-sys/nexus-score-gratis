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
 live_by_league:[{league:'Brasileirão Série A',fresh_live_games:3,
   with_recent_scouts:2,with_recent_pressure:1,
   scouts_coverage_pct:66.7,pressure_coverage_pct:33.3},
  {league:'<img onerror=1>',fresh_live_games:1,with_recent_scouts:0,
   with_recent_pressure:0,scouts_coverage_pct:0,pressure_coverage_pct:0}],
 odds_budget_health:{monthly_limit_conservative:186,used_this_month:3,
  remaining_this_month:183,next_collection_window_utc:'2026-10-19T21:00:00+00:00',
  historical_collected:0,historical_attempts:0,historical_status:'not_yet_recorded'},
 warnings:['<img src=x onerror=alert(1)>']};
const view=ctx.show(h);
assert.match(view,/QUALIDADE DAS FONTES/);
assert.match(view,/60%/);
assert.match(view,/waiting_free_slot/);
assert.match(view,/blocked_403/);
assert.match(view,/Cobertura ao vivo por campeonato/);
assert.match(view,/Brasileirão Série A/);
assert.match(view,/66,7%/);
assert.match(view,/3\/186/);
assert.match(view,/183 requisições/);
assert.match(view,/not_yet_recorded/);
assert.match(view,/21:00:00/);
assert.ok(!view.includes('<img'));
assert.match(view,/&lt;img/);
assert.match(html,/id="cloud-source-health"/);
assert.match(html,/sourceHealthHTML\(cloudData.source_health\)/);
console.log('NEXUS 5.47 quality feed: source status, missing info and XSS guards OK');
