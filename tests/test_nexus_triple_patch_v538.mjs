import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const hub=require('../web/nexus-alert-center-v537.js');
const market=require('../web/nexus-market-quality-v538.js');
const evidence=require('../web/nexus-evidence-v535.js');
for(const m of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)){
 if(m[1].trim())new vm.Script(m[1]);
}

const input={id:'match-4',home:'Mandante',away:'Visitante',phase:'live',
 day:'2026-10-17',minute:53,score:'0-0',league:'Liga',
 pressure:[{m:50,v:22},{m:51,v:25}],stats:{home:{shots_on:1},away:{shots_on:2}},
 form:{home:{available:0},away:{available:0}}};
const lite={schema:3,format:'listing_only',exported_at:new Date().toISOString(),
 games:[input]};
let liteReads=0,fullReads=0;
const originalFetch=async url=>{
 const address=String(url);
 if(address.includes('listing.json')){liteReads++;return new Response(JSON.stringify(lite));}
 if(address.includes('data.json')){fullReads++;return new Response(JSON.stringify({games:[input],exported_at:new Date().toISOString()}));}
 throw new Error('URL not expected '+address);
};
const store=new Map();
const localStorage={getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)};
const fakeWindow={fetch:originalFetch,location:{href:'https://nexus.example/'},NexusUpgrade:null};
const sandbox={window:fakeWindow,location:fakeWindow.location,
 localStorage,URL,Response,Date,Intl,Math,Number,console,
 NexusUpgrade:{coldAt:()=>({active:false,latest:null,reason:'Sem dados'})}};
const inline=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)]
 .map(x=>x[1]).find(x=>x.includes('const realFetch=window.fetch'));
assert.ok(inline,'static snapshot bridge exists');
vm.runInNewContext(inline,sandbox);
const first=await fakeWindow.fetch('/api/live');
const list=await first.json();
assert.equal(list.matches.length,1);
assert.equal(liteReads,1);
assert.equal(fullReads,0,'list must not download 10MB historical data');
const favorite=await fakeWindow.fetch('/api/favorites');
assert.equal((await favorite.json()).favorites.length,0);
assert.equal(fullReads,0,'favorites must not download history');
const match=await fakeWindow.fetch('/api/match/match-4');
assert.equal((await match.json()).home,'Mandante');
assert.equal(fullReads,1,'open match fetches full data only on demand');
assert.match(html,/window\.NexusWebBridge=\{data,listingData,details,listing,makeForecast\}/);

const now=Date.now();
const record={match_id:'match-4',title:'🔥 JOGO PEGANDO FOGO',message:'Gol pode estar próximo.',kind:'hot'};
const entries=hub.add([],record,now);
assert.equal(entries.length,1);
assert.equal(hub.add(entries,record,now+60000).length,1,'cooldown móvel de 8min');
const crossingBoundary=Math.floor(now/(8*60000))*(8*60000)-1000;
const priorToBoundary=hub.add([],record,crossingBoundary);
assert.equal(hub.add(priorToBoundary,record,crossingBoundary+60000).length,1,
 'notificação não duplica ao cruzar o limite do bucket');
assert.equal(hub.add(priorToBoundary,record,crossingBoundary+8*60000).length,2,
 'após 8 minutos completos um novo alerta pode ser emitido');
assert.equal(hub.clean(entries,now+49*3600000).length,0,'expire stale');
assert.match(hub.render(entries).html,/ABRIR PARTIDA/);
assert.equal(hub.mark(entries,entries[0].id)[0].read,true);
assert.doesNotMatch(hub.render(hub.add([],{...record,message:'<script>attack</script>'},now)).html,/<script>/);
assert.match(html,/id="nexus-alert-center"/);
assert.match(html,/function bindAlertHub\(/);

const frozen={
 model_status:'experimental_uncalibrated',captured_at:'2026-10-17T18:00:00Z',
 indications:[
 {market:'1x2',selection:'home',probability:57},
 {market:'double_chance',selection:'1X',probability:80},
 {market:'over_under_25',selection:'over',probability:54},
 {market:'btts',selection:'yes',probability:51}],
 odds:{source:'ESPN',bookmaker:'DraftKings',captured_at:'2026-10-17T19:40:00Z',
 recent_at_check:true,prices:{home:2.12,draw:3.1,away:4.1}},
 settlement:{checks:[{market:'1x2',selection:'home',result:'hit'},
 {market:'btts',selection:'yes',result:'miss'}]}
};
const fixture={start_timestamp:Date.parse('2026-10-17T20:00:00Z')/1000};
const evaluated=market.analyse(frozen,fixture);
assert.equal(evaluated.items.length,4);
assert.equal(evaluated.items[0].ev_state,'theory_positive');
assert.equal(evaluated.items[0].result,'hit');
assert.equal(evaluated.items[1].odd,null,'other markets have no live market prices');
assert.match(market.render(frozen,fixture),/EV TEÓRICO/);
assert.doesNotMatch(market.render(frozen,fixture),/R\$ 100|Stake simulado/);
const noQuotes=market.analyse({...frozen,odds:null},fixture);
assert.equal(noQuotes.items[0].ev_pct,null);
assert.match(market.render({...frozen,odds:null},fixture),/EV INDISPONÍVEL/);
const late=market.analyse({...frozen,odds:{...frozen.odds,captured_at:'2026-10-17T20:10:00Z'}},fixture);
assert.equal(late.items[0].ev_pct,null,'late odds do not count');
const health=market.coverageHTML({fixtures_with_frozen_forecast:20,
 fixtures_with_verified_pregame_1x2:4,
 markets:[{market:'1x2',label:'Match Odds',forecasts:20,with_price:4,
 settled:6,hits:3}]},{odds_updated:0,api_football:{status:'not_configured'},
 the_odds_api:{status:'not_configured'},errors:['SofaScore HTTP 403']},
 {tables_received:0,cache_tables_present:4,fixtures_enriched:12,unqueried_leagues:150});
assert.match(health,/4 de 20 partidas/);
assert.match(health,/SofaScore: 403/);
assert.match(health,/150 ligas/);
assert.match(health,/Match Odds/);
assert.match(html,/case 'projections':html\+=classicProjection57\(d\)\+\(d\.pregame_baseline\?NexusMarketQuality\.render/);
assert.doesNotMatch(html,/notify\(radarOpportunityText\(r\)/,'no unvalidated EV popups');

assert.ok(evidence.uncertainty(5,10).low<50);
assert.ok(evidence.uncertainty(5,10).high>50);
const summary=evidence.calibrationHTML({views:{'10':{
 by_signal:[{label:'🔥 PRESSÃO FORTE',settled:25,hits:10,observations:27}],
 by_minute_band:[{label:'31–45′',settled:5,hits:2}]}}});
assert.match(summary,/Amostra|Em observação/);
assert.match(summary,/PRESSÃO FORTE/);
assert.match(summary,/Wilson 95%/);
console.log('NEXUS 5.36/5.37/5.38: feed parcial, alertas, classificação EV, fontes e sintaxe OK');
