import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const NexusUpgrade=require('../web/nexus-v531.js');
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const a=html.indexOf('window.PressureLab = (() => {');
const b=html.indexOf('})();',a);
assert.ok(a>=0 && b>a);
const window={};
const PressureLab=new Function('window','NexusUpgrade',html.slice(a,b+5)+'\nreturn window.PressureLab;')(window,NexusUpgrade);
const sample={home:'Al Kholood',away:'Al Qadsiah',phase:'live',live:true,
  status:'AO VIVO',minute:44,score:'0-3',stats:{home:{shots_on:0},away:{shots_on:1}},
  thermometer:{points:[{minute:4,value:-40},{minute:6,value:-25},{minute:7,value:20},{minute:10,value:-30}]},
  incidents:[],goal_scorers:[{team:'away',player:'Reijnders',minute:4}],
  odds:{markets:{'1x2':{}}},scout_pressure:{available:true,last_graph_minute:10,windows:{}},
  indicator_board:[]};
const live=PressureLab.render(sample,'all').replaceAll('&#39;',"'");
assert.match(live,/HISTÓRIA DA PRESSÃO · 0–90'/);
assert.match(live,/4\/44 minutos jogados com pressão/);
assert.match(live,/44' de jogo · eixo de 90 minutos \(apenas leituras coletadas\)/);
assert.match(live,/2 gols sem detalhes/);
assert.match(live,/Última medição de pressão no minuto 10'/);
assert.match(live,/SEM LEITURA RECENTE/);
assert.doesNotMatch(live,/JOGO TRAVADO/);
assert.match(live,/Pressão indisponível após 10/);
assert.doesNotMatch(live,/90 minutos completos/);
const awayChance={...sample,minute:32,
  stats:{home:{big_chances:0},away:{big_chances:1}},
  incidents:[{minute:32,emoji:'💣❌',type:'big_chance_missed',team:'AWAY',
    stamp:"32'",text:'Grande chance perdida · para fora'}],
  signal_timeline:[{minute:32,emoji:'💣❌',team:'AWAY',basis:'event'}]};
const chance=PressureLab.chart(awayChance,'all');
assert.match(chance,/scout-event compact away/);
assert.doesNotMatch(chance,/scout-event compact home/);
assert.doesNotMatch(chance,/snapshot-now/);
assert.ok(chance.includes('Grande chance perdida'));
const homeChance=PressureLab.chart({...awayChance,incidents:[{...awayChance.incidents[0],team:'HOME'}]},'all');
assert.match(homeChance,/scout-event compact home/);
assert.doesNotMatch(homeChance,/scout-event compact away/);
const half=PressureLab.chart(sample,'all');
assert.match(half,/90 POSIÇÕES/);
assert.doesNotMatch(half,/45 POSIÇÕES/);
const mobileWindow={innerWidth:390};
const phoneLab=new Function('window','NexusUpgrade',html.slice(a,b+5)+'\nreturn window.PressureLab;')(mobileWindow,NexusUpgrade);
const phone=phoneLab.chart(sample,'all');
assert.match(phone,/mobile-periods/);
assert.match(phone,/0′–30′/);
assert.match(phone,/30′–60′/);
assert.match(phone,/60′–90′/);
assert.equal((phone.match(/class="mobile-period"/g)||[]).length,3);
assert.doesNotMatch(phone,/scout-graph-scroll/);
assert.match(phone,/Sem barra = pressão não medida/);
assert.match(phone,/90 POSIÇÕES/);
assert.match(phone,/0–90′/);


const withScouts={...sample,stats:{
 home:{shots_on:2,shots_off:6,shots_total:8,corners:3,big_chances:1,xg:1.42,
       dangerous_attacks:34,possession:58},
 away:{shots_on:0,shots_off:0,corners:0}},
 stats_observed_at:new Date(Date.now()-20*60000).toISOString(),stats_source:'FotMob'};
const scoutInfo=phoneLab.scoutTotals(withScouts);
assert.match(scoutInfo,/SCOUTS ATRASADOS/);
assert.match(scoutInfo,/1,42/);
assert.match(scoutInfo,/34/);
assert.match(scoutInfo,/Posse/);
assert.match(scoutInfo,/—/);
const currentScouts=phoneLab.scoutTotals({...withScouts,
 stats_observed_at:new Date(Date.now()-120000).toISOString()});
assert.doesNotMatch(currentScouts,/SCOUTS ATRASADOS/);
assert.match(currentScouts,/verificados às/);

const data29={...sample,phase:'live',live:true,minute:29,
  incidents:[
    {minute:22,team:'HOME',emoji:'🥅',text:'Chute no alvo'},
    {minute:22,team:'HOME',emoji:'↗️',text:'Chute para fora'},
    {minute:22,team:'HOME',emoji:'🚩',text:'Escanteio'}],
  signal_timeline:[
    {minute:22,team:'HOME',emoji:'🔥',name:'Forte',basis:'graph'},
    {minute:22,team:'HOME',emoji:'🧨',name:'Total',basis:'graph'},
    {minute:22,team:'HOME',emoji:'⚡',name:'Ofensiva',basis:'graph'},
    {minute:20,team:'AWAY',emoji:'🥶',name:'Frio',basis:'graph'},
    {minute:29,team:'HOME',emoji:'💣',name:'Acumulado',basis:'snapshot'}]};
const timeline29=phoneLab.chart(data29,'all');
assert.match(timeline29,/data-live-minute="29"/);
assert.match(timeline29,/mobile-live-line/);
assert.equal((timeline29.match(/class="mobile-signal home"/g)||[]).length,3);
assert.equal((timeline29.match(/class="mobile-event home"/g)||[]).length,3);
assert.match(timeline29,/data-mobile-signal-index="0"/);
assert.match(timeline29,/data-mobile-signal-index="1"/);
assert.match(timeline29,/data-mobile-signal-index="2"/);
assert.match(timeline29,/data-mobile-signal-index="3"/);
assert.doesNotMatch(timeline29,/data-mobile-signal-index="4"/);
assert.doesNotMatch(timeline29,/mobile-markers|class="mobile-marker |>\+1</);
assert.match(phoneLab.describeMobileSignal(data29,1),/22′/);
assert.match(phoneLab.describeMobileSignal(data29,1),/Total/);
const at44=phoneLab.chart({...data29,minute:44},'all');
assert.match(at44,/data-live-minute="44"/);
assert.equal((at44.match(/class="mobile-live-line"/g)||[]).length,1);
const at93=phoneLab.chart({...data29,minute:93},'all');
assert.match(at93,/data-live-minute="93"/);
const finishedMobileChart=phoneLab.chart({...data29,phase:'finished',live:false},'all');
assert.doesNotMatch(finishedMobileChart,/class="mobile-live-line"/);

const css=fs.readFileSync(new URL('../web/nexus-web-polish.css',import.meta.url),'utf8');
assert.match(css,/#section-thermometer\.scout-main \.compact-timeline \.scout-graph-scroll\{\s*overflow:hidden!important/);
assert.match(css,/#section-thermometer\.scout-main \.compact-timeline \.scout-graph\{\s*width:100%!important/);
assert.doesNotMatch(css,/DESLIZE PARA VER TODOS OS MINUTOS/);
const second=PressureLab.chart({...sample,minute:66,phase:'live'},'all');
assert.match(second,/90 POSIÇÕES/);
const ended=PressureLab.render({...sample,phase:'finished',live:false,minute:0},'all').replaceAll('&#39;',"'");
assert.match(ended,/Partida encerrada · eixo completo 0–90'/);
const complete=PressureLab.render({...sample,goal_scorers:[
   {team:'away',player:'A',minute:4},{team:'away',player:'B',minute:15},
   {team:'away',player:'C',minute:31}]},'all');
assert.doesNotMatch(complete,/gols sem detalhes/);
// Regressão placar ao vivo: odds cruzadas devem aparecer COM fase correta.
const withPregameOdds=PressureLab.render({...sample,
  odds:{available:true,phase:'pregame',source:'ESPN',bookmaker:'DraftKings',
    fetched_at:'2026-10-09T20:34:51+00:00',
    markets:{'1x2':{home:1.909,draw:3.4,away:4.1}}}},'all');
assert.match(withPregameOdds,/ODDS PRÉ-JOGO/);
assert.match(withPregameOdds,/DraftKings/);
assert.match(withPregameOdds,/1,909/);
assert.match(withPregameOdds,/3,40/);
assert.match(withPregameOdds,/4,10/);
assert.doesNotMatch(withPregameOdds,/ODDS AO VIVO/);
const missingOdds=PressureLab.render({...sample,odds:{markets:{'1x2':{}}}},'all');
assert.match(missingOdds,/Odds 1\/X\/2 não disponíveis nas fontes autorizadas/);

console.log('NEXUS: gráfico completo 0-90 no celular, sem rolagem, cobertura real e placar auditável OK');
