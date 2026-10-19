import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const extra=fs.readFileSync(new URL('../web/match-detail.js',import.meta.url),'utf8');
assert.match(html,/nexus-squads-v539\.css/);
assert.match(html,/goal_scorers:\(g\.events\|\|\[\]\)\.filter/);
assert.match(html,/g\.closing_odds\|\|\[\]/);
assert.match(html,/ODDS HISTÓRICAS DE FECHAMENTO/);
assert.match(html,/assist\?'<small title="Assistência confirmada"/);
assert.match(extra,/Odds históricas de fechamento · não são preços atuais/);
for(const p of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi))
 if(p[1].trim())new vm.Script(p[1]);
new vm.Script(extra);
const start=html.indexOf('function lineupsHTML(d){');
const end=html.indexOf('\nfunction indicatorTiles(d){',start);
assert.ok(start>=0&&end>start);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({
 '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const lineup=new Function('NexusUpgrade','esc',html.slice(start,end)+';return lineupsHTML;')(
 {playerState:(p,role,official)=>official?'Titular escalado':'Provável'},esc);
const base={
 home:'Casa',away:'Fora',phase:'finished',events:[{type:'substitution',player_out:'Craque',
 player_in:'Reserva A'}],
 lineups:{home_detail:{official:true,formation:'4-3-3',xi:[
 {name:'Craque',number:'10'},{name:'Camisa 9',number:'9'}],
 bench:[{name:'Reserva A',number:'19'}]},
 away_detail:{official:true,formation:'4-4-2',
 xi:[{name:'9 visitante',number:'9'}],bench:[{name:'Banco',number:'17'}]}},
 team_leaders:{home:{
 goals:{name:'Camisa 9',value:12},assists:{name:'Craque',value:8},
 rating:{name:'Craque',value:7.9}}},
 match_stars:{home:{player:'Craque',label:'Melhor em campo (FotMob)',
 source:'FotMob',rating:9.1}}};
const output=lineup(base);
assert.match(output,/ESCALAÇÕES · TITULARES E RESERVAS/);
assert.match(output,/XI OFICIAL/);
assert.match(output,/saídas confirmadas/);
assert.match(output,/Artilheiro/);
assert.match(output,/Camisa 9/);
assert.match(output,/Líder de assistências/);
assert.match(output,/Craque/);
assert.match(output,/Melhor em campo/);
const missingTop=lineup({...base,team_leaders:{home:{goals:{name:'Atacante Ausente',value:17}}},
  match_stars:{}});
assert.match(missingTop,/Atacante Ausente/);
assert.match(missingTop,/Destaque não relacionado na escalação oficial/);
const probable=lineup({...base,lineups:{...base.lineups,
 home_detail:{...base.lineups.home_detail,official:false}},
 team_leaders:{home:{goals:{name:'Atacante Ausente',value:17}}},match_stars:{}});
assert.doesNotMatch(probable,/Destaque não relacionado na escalação oficial/);
assert.match(output,/★ Destaque/);
assert.ok(output.includes('9.1/10') || output.includes('9.10/10'), 'nota do destaque da partida preservada');
assert.match(output,/TITULAR/);
const unknown=lineup({...base,team_leaders:{},match_stars:{}});
assert.match(unknown,/ranking completo/);
assert.doesNotMatch(unknown,/12 gols/);
assert.doesNotMatch(unknown,/★ Destaque/);
const malicious=lineup({...base,team_leaders:{home:{
 goals:{name:'<img src=x onerror=alert(1)>',value:12}}}});
assert.doesNotMatch(malicious,/<img/);
assert.match(malicious,/&lt;img/);
console.log('NEXUS 5.39: XI/reservas/destaques confirmados, histórico e sintaxe OK');
