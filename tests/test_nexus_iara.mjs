import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const js=fs.readFileSync(new URL('../web/nexus-iara.js',import.meta.url),'utf8');
const context={window:{}};
vm.runInNewContext(js,context);
const iara=context.window.NexusIara;
assert.equal(typeof iara.evaluate,'function');
assert.equal(typeof iara.render,'function');
const pressure=(start,end,val)=>
  Array.from({length:end-start+1},(_,i)=>({minute:start+i,value:val}));
const base={
 id:'fotmob-900',home:'Mandante',away:'Visitante',phase:'live',live:true,minute:35,
 score:'1-1',start_timestamp:1791000000,
 thermometer:{points:pressure(21,35,58)},
 stats:{home:{shots_on:6,big_chances:2,corners:7,red_cards:0},
   away:{shots_on:1,big_chances:0,corners:2,red_cards:0}},
 incidents:[],indicator_board:[{emoji:'🔥',state:'active',team:'HOME'}]
};
let v=iara.evaluate(base);
assert.equal(v.active,true);
assert.match(v.intro,/Mandante está pressionando/);
assert.match(v.next,/nova chance de gol/);
assert.ok(v.tags.includes('ATENÇÃO A NOVO GOL'));
assert.match(iara.render(base),/IARA/);
assert.match(iara.render(base),/Pode sair mais um gol/);
assert.match(iara.render(base),/Finalizações no gol 6×1/);
assert.doesNotMatch(iara.render(base),/gol garantido|80% de gol/i);
const rival={
 ...base,score:'0-2',thermometer:{points:pressure(21,35,-61)},
 stats:{home:{shots_on:1,big_chances:0,corners:1,red_cards:0},
        away:{shots_on:6,big_chances:2,corners:9,red_cards:0}},
 prelive:{odds:{markets:{'1x2':{home:1.65,draw:3.6,away:4.1}},
    source:'ESPN',fetched_at:'2026-09-22T20:00:00Z'}}
};
v=iara.evaluate(rival);
assert.match(v.intro,/Visitante está pressionando/);
assert.match(v.intro,/zebra está vencendo/);
assert.match(v.next,/Visitante/);
// Sem odds capturadas antes do jogo, não inventar quem é favorito.
const wrongOdds={...rival,prelive:{odds:{markets:{'1x2':{
 home:1.65,draw:3.6,away:4.1}},fetched_at:'2027-02-09T20:00:00Z'}}};
assert.doesNotMatch(iara.evaluate(wrongOdds).intro,/zebra|favorito/i);
const stale={...base,minute:46};
v=iara.evaluate(stale);
assert.match(v.intro,/A curva de pressão parou/);
assert.match(v.next,/sem pressão recente confiável/);
assert.ok(v.tags.includes('CURVA ATRASADA'));
assert.match(iara.render(stale),/PRESSÃO DESATUALIZADA/);
assert.doesNotMatch(iara.render(stale),/● LEITURA ATUALIZÁVEL/);
assert.doesNotMatch(v.next,/cenário merece atenção/);
const noMomentum={...base,thermometer:{points:[]},stats:{home:{},away:{}},indicator_board:[]};
v=iara.evaluate(noMomentum);
assert.match(v.intro,/fonte ainda não entregou/);
assert.match(v.next,/não consegue apontar/);
assert.equal(v.confidence,'SEM DADOS RECENTES');
const observedDelta={...noMomentum,minute:35,scout_snapshots:[
  {m:25,at:'2026-10-10T08:00:00Z',source:'FotMob',
   stats:{home:{shots_on:1,corners:2},away:{shots_on:0,corners:1}}},
  {m:33,at:'2026-10-10T08:10:00Z',source:'FotMob',
   stats:{home:{shots_on:3,corners:2},away:{shots_on:1,corners:2}}}
]};
v=iara.evaluate(observedDelta);
assert.equal(v.confidence,'SCOUTS ENTRE CAPTURAS');
assert.match(v.intro,/25′–33′/);
assert.match(v.intro,/Mandante: chutes no alvo \+2/);
assert.match(v.next,/não permite estimar a chance/);
assert.match(iara.render(observedDelta),/SEM CURVA DE PRESSÃO/);
assert.doesNotMatch(v.intro,/está pressionando com intensidade forte/);
assert.equal(iara.scoutEvolution({...observedDelta,minute:60},60),null);
assert.equal(iara.scoutEvolution({...observedDelta,scout_snapshots:[
 observedDelta.scout_snapshots[0],
 {...observedDelta.scout_snapshots[1],source:'Outra fonte'}]},35),null);
const weakCoverage={...base,thermometer:{points:[
 {minute:27,value:88},{minute:28,value:90},{minute:35,value:81}
]}};
assert.match(iara.evaluate(weakCoverage).intro,/faltam amostras consecutivas/);
const balanced={...base,thermometer:{points:pressure(21,35,0)}};
assert.match(iara.evaluate(balanced).intro,/Ritmo ofensivo baixo/);
const finished={...base,phase:'finished',live:false};
assert.equal(iara.render(finished),'');
const malicious={...base,home:'<img src=x onerror=alert(1)>',away:'Visitante'};
assert.doesNotMatch(iara.render(malicious),/<img src=x onerror/);
assert.match(iara.render(malicious),/&lt;img/);
const mustWin={
 ...base,standings:{
  source:'FotMob',league:'Brasileirão Série A',updated_at:'2026-10-09T13:00:00Z',
  home:{position:17,points:27,played:28,level:'alta',
    reasons:[{kind:'sair_z4',label:'Sair da zona de rebaixamento',
      detail:'17º lugar com 27 pontos; primeiro fora da zona: 16º com 28.'}]},
  away:{position:4,points:48,played:28,level:'moderada',
    reasons:[{kind:'defender_g4',label:'Defender o G4',
      detail:'4º lugar, 48 pontos; o 5º soma 47.'}]}}};
let motivation=iara.standingsMotivation(mustWin);
assert.equal(motivation.list.length,2);
assert.equal(iara.standingsMotivation({...mustWin,standings:{
  ...mustWin.standings,source:'ESPN'}}).list.length,2);
assert.equal(iara.standingsMotivation({...mustWin,standings:{
  ...mustWin.standings,source:'Fonte não verificada'}}).available,false);
assert.match(iara.render(mustWin),/Sair da zona de rebaixamento/);
assert.match(iara.render(mustWin),/Defender o G4/);
assert.match(iara.evaluate(mustWin).intro,/aumenta o peso esportivo/);
assert.match(iara.render(base),/Aguardando classificação verificada/);
const evTest={...mustWin,prelive:{
 forecast:{one_x_two:{home:52,draw:26,away:22}},
 sample:{home:{n:10},away:{n:10}},
 odds:{source:'ESPN',fetched_at:'2026-09-22T20:00:00Z',
 markets:{'1x2':{home:2.2,draw:3.1,away:4.1}}}}};
const ev=iara.experimentalValue(evTest);
assert.ok(ev);
assert.equal(ev.experimental,true);
assert.ok(ev.positive);
assert.match(iara.render(evTest),/EV teórico/);
assert.match(iara.render(evTest),/não calibrado/);
assert.match(iara.render(evTest),/[Nn]ão é EV\+ comprovado/);
const late={...evTest,prelive:{...evTest.prelive,
 odds:{...evTest.prelive.odds,fetched_at:'2027-01-01T20:00:00Z'}}};
assert.equal(iara.experimentalValue(late),null);
assert.match(iara.render(late),/Indisponível sem odds pré-jogo/);
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const css=fs.readFileSync(new URL('../web/nexus-iara.css',import.meta.url),'utf8');
assert.match(html,/window\.NexusIara\.render\(d\)/);
assert.match(html,/src="\.\/nexus-iara\.js"/);
assert.match(html,/href="\.\/nexus-iara\.css"/);
assert.match(css,/\.iara-card/);
console.log('NEXUS IARA: analise contextual, odds, zebra, dados atrasados e privacidade OK');
