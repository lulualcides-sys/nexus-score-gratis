import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const full=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const start=full.indexOf('function oddsComparisonHTML(d,live=false){');
const end=full.indexOf('function preliveOddsHTML(p,d){',start);
assert.ok(start>0&&end>start,'renderer de odds instalado');
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({
 '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));
const context={esc,Date,Number,Array,Object,String};
vm.runInNewContext(full.slice(start,end)+';this.render=oddsComparisonHTML;',context);
const b={market:'btts',selection:'yes',best:{odds:2.2,bookmaker:'Pinnacle',
  source:'OddsPapi',at:'2026-10-19T12:00:00Z'},
  alternatives:[{odds:2,bookmaker:'Betano BR',at:'2026-10-19T12:00:00Z'}]};
let view=context.render({odds_comparison:[b]},false);
assert.match(view,/MELHORES ODDS PRÉ-JOGO/);
assert.match(view,/2,20/);
assert.match(view,/Pinnacle/);
assert.match(view,/Betano BR/);
assert.match(view,/Ambas marcam/);
view=context.render({live_odds_comparison:[]},true);
assert.match(view,/Nenhuma cotação live recente/);
const injected=context.render({odds_comparison:[{
 ...b,best:{...b.best,bookmaker:'<img src=x onerror=alert(1)>'}
}]},false);
assert.ok(!injected.includes('<img src=x'));
assert.ok(injected.includes('&lt;img'));
const odd15={...b,market:'over_under_15',selection:'over'};
const odd35={...b,market:'over_under_35',selection:'under'};
const markets=context.render({odds_comparison:[odd15,odd35]},false);
assert.match(markets,/Over\/Under 1,5 gols/);
assert.match(markets,/Over\/Under 3,5 gols/);
assert.match(markets,/Mais de 1,5/);
assert.match(markets,/Menos de 3,5/);
const handicap=context.render({odds_comparison:[
  {...b,market:'ah_m05',selection:'home'},
  {...b,market:'ah_p05',selection:'away'},
  {...b,market:'ah_m1',selection:'home'}]},false);
assert.match(handicap,/Mandante -0,5/);
assert.match(handicap,/Visitante -0,5/);
assert.match(handicap,/Mandante -1/);
console.log('NEXUS 5.41: comparacao por casa/horario, fases e escape HTML OK');
