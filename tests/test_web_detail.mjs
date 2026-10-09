// NEXUS WEB 6 — integration checks, no browser or network required.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const script=fs.readFileSync(new URL('../web/match-detail.js',import.meta.url),'utf8');
const live={
  home:'Mandante',away:'Visitante',home_logo:'',away_logo:'',
  score:'1-0',phase:'live',minute:62,league:'Test League',round:'7',
  source:'FotMob',sources:['FotMob'],start_timestamp:1791543600,
  pressure:[{m:2,v:67},{m:4,v:-56},{m:45,v:0},{m:60,v:89}],
  stats:{home:{shots_on:8,shots_off:4,corners:6},
         away:{shots_on:1,shots_off:7,corners:2}},
  events:[{m:14,type:'goal',side:'home',text:'Gol verificado'},
          {m:24,type:'shot_on',side:'home',text:'No alvo'},
          {m:26,type:'shot_off',side:'away',text:'Para fora'},
          {m:45,type:'penalty_missed',side:'away',text:'Pênalti perdido'}],
  form:{home:{available:0,games:[]},away:{available:0,games:[]}},
  odds:[],closing_odds:[],signals:[],outcomes:{}
};
const markup={innerHTML:'',querySelectorAll:()=>[]};
const content={innerHTML:''};
const scroll={scrollTop:55};
const dialog={open:false,showModal(){this.open=true;}};
const nodes={'detail':dialog,'detail-content':markup,'md-content':content,'md-scroll':scroll};
const mockDocument={getElementById:(id)=>nodes[id]||null,querySelectorAll:()=>[]};
const window={};
vm.runInNewContext(script,{window,document:mockDocument,console});
assert.ok(window.NexusMatchDetail.show(live));
assert.match(markup.innerHTML,/md-scoreboard/);
assert.match(markup.innerHTML,/data-tab="markets"/);
assert.match(content.innerHTML,/INTERVALO/);
assert.match(content.innerHTML,/md-home/);
assert.match(content.innerHTML,/md-visitor/);
assert.match(content.innerHTML,/md-event-shot_on/);
assert.match(content.innerHTML,/md-event-shot_off/);
assert.match(content.innerHTML,/❌🥅/);
assert.match(content.innerHTML,/Mandante acima/);
assert.equal(scroll.scrollTop,0);
window.NexusMatchDetail.select('stats');
assert.match(content.innerHTML,/Finalizações no gol/);
window.NexusMatchDetail.select('squads');
assert.match(content.innerHTML,/Elenco ou escalação não disponível/);
window.NexusMatchDetail.select('markets');
assert.match(content.innerHTML,/Nenhuma odd pré-jogo verificada/);
window.NexusMatchDetail.select('projections');
assert.match(content.innerHTML,/Não há modelo probabilístico validado/);
const finished={...live,phase:'finished',minute:0,
  form:{home:{available:1,games:[{opponent:'Rival',gf:2,ga:1,result:'V',day:'2026-10-07',venue:'Casa'}],
                 wins:1,draws:0,losses:0},away:{available:0,games:[]}},
  outcomes:{correct_score:'2-1',over_15:true,over_25:true,over_35:false,btts:true}};
assert.ok(window.NexusMatchDetail.show(finished));
window.NexusMatchDetail.select('form');
assert.match(content.innerHTML,/1 de 10 jogos anteriores/);
window.NexusMatchDetail.select('markets');
assert.match(content.innerHTML,/Resultado do mercado, não P\/L/);
console.log('NEXUS Web: teste da tela de partidas OK');
