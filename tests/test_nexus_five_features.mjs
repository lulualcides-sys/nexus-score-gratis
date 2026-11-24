import assert from 'node:assert/strict';
import fs from 'node:fs';
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const css=fs.readFileSync(new URL('../web/nexus-simple.css',import.meta.url),'utf8');
const js=fs.readFileSync(new URL('../web/nexus-simple.js',import.meta.url),'utf8');
// 1 fixar ligas
assert.match(js,/nexusPinnedLeagues/);assert.match(html,/data-pin-league/);assert.match(html,/isPinned\(/);
// 2 gols e cartões no termômetro
assert.match(html,/nx-key-event/);assert.match(css,/scout-event:not\(\.nx-key-event\)/);
// 3 ajuda
assert.match(html,/Como ler o termômetro/);assert.match(html,/nx-help-btn/);
// 4 resumo: só com curva recente
const src=html.slice(html.indexOf('function nexusPressureSummary'),html.indexOf('function nexusLeagueLabel'));
const esc=s=>String(s);const f=new Function('esc',src+';return nexusPressureSummary;')(esc);
const now=new Date().toISOString(),pts=[...Array(10)].map((_,i)=>({m:60+i,v:60}));
assert.match(f({live:true,home:'Monza',away:'X',pressure_points:pts,pressure_observed_at:now}),/Monza pressionando forte/);
assert.match(f({live:true,home:'A',away:'Fio',pressure_points:pts.map(p=>({m:p.m,v:-35})),pressure_observed_at:now}),/Fio pressionando/);
assert.equal(f({live:true,home:'A',away:'B',pressure_points:pts,pressure_observed_at:'2020-01-01T00:00:00Z'}),'','dado velho não vira resumo');
assert.equal(f({live:false,pressure_points:pts,pressure_observed_at:now}),'');
assert.equal(f({live:true,pressure_points:pts.slice(0,3),pressure_observed_at:now}),'','pouca amostra');
// 5 esconder odds
assert.match(js,/nexusHideOdds/);assert.match(css,/body\.nx-no-odds \.match-list-odds/);
console.log('NEXUS 5 recursos: OK');
// varredura 24/11
assert.match(css,/setting-line:has\(#demo-setting\)/,'demo quebrada escondida');
assert.match(css,/\.match-tabs\{display:flex!important;flex-wrap:wrap/);
assert.match(js,/prettyDates/);
assert.match(html,/key==='possession'&&Number\.isFinite\(\+v\)\?Math\.round/);
console.log('NEXUS varredura: OK');
{
const src2=html.slice(html.indexOf('function nexusPressureSpark'),html.indexOf('/* Resumo de uma linha'));
const sp=new Function('esc',src2+';return nexusPressureSpark;')(s=>String(s));
const now=new Date().toISOString(),pts=[...Array(15)].map((_,i)=>({m:50+i,v:i%2?60:-30}));
const out=sp({live:true,home:'A',away:'B',pressure_points:pts,pressure_observed_at:now});
assert.match(out,/nx-spark/);assert.equal((out.match(/<rect/g)||[]).length,15);assert.match(out,/class="h hot"/);assert.match(out,/class="a"/);
assert.equal(sp({live:true,pressure_points:pts,pressure_observed_at:'2020-01-01T00:00:00Z'}),'','velho não desenha');
assert.equal(sp({live:false,pressure_points:pts,pressure_observed_at:now}),'');
console.log('NEXUS mini gráfico de pressão: OK');
}
{
const src3=html.slice(html.indexOf('function nexusTipLine'),html.indexOf('function nexusPressureSpark'));
const tip=new Function('esc',src3+';return nexusTipLine;')(s=>String(s));
assert.match(tip({phase:'scheduled',home:'A',away:'B',forecast:{home:52,draw:26,away:22,over25:50,btts:52}}),/A vence 52%.*\+2,5 gols 50%.*Ambas 52%/);
assert.match(tip({phase:'finished',home:'A',away:'B',home_score:2,away_score:5,forecast:{home:44,draw:27,away:29}}),/✗.*A vence 44%/);
assert.match(tip({phase:'finished',home:'A',away:'B',home_score:1,away_score:1,forecast:{home:30,draw:40,away:30}}),/✓.*Empate 40%/);
assert.equal(tip({live:true,forecast:{home:50,draw:25,away:25}}),'','ao vivo usa pressão, não palpite');
assert.equal(tip({phase:'scheduled'}),'','sem previsão: nada');
console.log('NEXUS palpite na lista: OK');
}
