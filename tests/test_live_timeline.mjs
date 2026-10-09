import assert from 'node:assert/strict';
import fs from 'node:fs';
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const a=html.indexOf('window.PressureLab = (() => {');
const b=html.indexOf('})();',a);
assert.ok(a>=0 && b>a);
const window={};
const PressureLab=new Function('window',html.slice(a,b+5)+'\nreturn window.PressureLab;')(window);
const sample={home:'Al Kholood',away:'Al Qadsiah',phase:'live',live:true,
  status:'AO VIVO',minute:44,score:'0-3',stats:{home:{shots_on:0},away:{shots_on:1}},
  thermometer:{points:[{minute:4,value:-40},{minute:6,value:-25},{minute:7,value:20},{minute:10,value:-30}]},
  incidents:[],goal_scorers:[{team:'away',player:'Reijnders',minute:4}],
  odds:{markets:{'1x2':{}}},scout_pressure:{available:true,last_graph_minute:10,windows:{}},
  indicator_board:[]};
const live=PressureLab.render(sample,'all').replaceAll('&#39;',"'");
assert.match(live,/HISTÓRIA DA PRESSÃO · 0–90'/);
assert.match(live,/4\/44 minutos jogados com pressão/);
assert.match(live,/44' de jogo · termômetro completo 0–90'/);
assert.match(live,/2 gols sem detalhes/);
assert.match(live,/Última medição de pressão no minuto 10'/);
assert.match(live,/SEM LEITURA RECENTE/);
assert.doesNotMatch(live,/JOGO TRAVADO/);
assert.match(live,/Pressão indisponível após 10/);
assert.doesNotMatch(live,/90 minutos completos/);
const half=PressureLab.chart(sample,'all');
assert.match(half,/90 POSIÇÕES/);
assert.doesNotMatch(half,/45 POSIÇÕES/);
const mobileWindow={innerWidth:390};
const phoneLab=new Function('window',html.slice(a,b+5)+'\nreturn window.PressureLab;')(mobileWindow);
const phone=phoneLab.chart(sample,'all');
assert.match(phone,/viewBox="0 0 520 302"/);
assert.match(phone,/90 POSIÇÕES/);
assert.match(phone,/0–90'/);
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
console.log('NEXUS: gráfico completo 0-90 no celular, sem rolagem, cobertura real e placar auditável OK');
