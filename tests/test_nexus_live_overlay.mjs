import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const L=createRequire(import.meta.url)('../web/nexus-live.js');
const now=new Date().toISOString(), old=new Date(Date.now()-3600e3).toISOString();
const value={games:[
  {id:'fotmob-1',phase:'live',minute:40,score:'0-0',pressure:[{m:1,v:2}],stats:{home:{corners:2},away:{}}},
  {id:'fotmob-2',phase:'live',minute:10,score:'0-0',pressure:[]},
  {id:'fotmob-3',phase:'finished',score:'1-1'}]};
const live={status:{updated_at:now},games:{
  'fotmob-1':{phase:'live',minute:67,score:'1-0',observed_at:now,pressure_observed_at:now,
    points:[{m:1,v:2},{m:66,v:40}],stats:{home:{shots_on:4},away:{shots_on:1}},stats_observed_at:now},
  'fotmob-2':{phase:'live',minute:55,score:'2-2',observed_at:old,points:[{m:50,v:9}]},
  'fotmob-3':{phase:'ended_or_unlisted',observed_at:now,points:[{m:5,v:1}]}}};
assert.equal(L.apply(value,live),1);
const g=value.games[0];
assert.equal(g.minute,67);assert.equal(g.score,'1-0');assert.equal(g.pressure.length,2);
assert.deepEqual(g.stats.home,{corners:2,shots_on:4},'mantém scouts antigos e soma os novos');
assert.equal(value.games[1].minute,10,'dado velho (>15 min) não vira ao vivo');
assert.equal(value.games[2].phase,'finished','jogo encerrado não volta a ao vivo');
// desligado sem URL válida
const off={games:[{id:'fotmob-1',phase:'live'}]};
let called=false;
assert.equal(await L.overlay(off,async u=>{if(u.endsWith('/live'))called=true;return {ok:true,json:async()=>({url:'http://evil.com'})};}),0);
assert.equal(called,false);
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
assert.match(html,/nexus-live\.js/);
assert.equal((html.match(/NexusLive\.overlay\(value,realFetch\)/g)||[]).length,2);
console.log('NEXUS live overlay: OK');
{
const list=[{id:'fotmob-1',live:true,minute:40,score:'0–0',home_score:0,away_score:0},{id:'fotmob-9',live:false,phase:'finished'}];
const n=L.patchList(list,{games:{'fotmob-1':{phase:'live',minute:71,score:'2-1',observed_at:new Date().toISOString(),points:[{m:70,v:30}],stats:{home:{shots_on:5},away:{}}},
  'fotmob-9':{phase:'ended_or_unlisted',observed_at:new Date().toISOString()}}});
assert.equal(n,1);assert.equal(list[0].minute,71);assert.equal(list[0].score,'2–1');assert.equal(list[0].home_score,2);
assert.equal(list[0].scoreboard_stats.home.shots_on,5);assert.equal(list[1].phase,'finished','encerrado não volta');
console.log('NEXUS lista ao vivo a cada 20 s: OK');
}
