import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const text=readFileSync(new URL('../web/match-detail.js',import.meta.url),'utf8');
const context={window:{},console};
vm.runInNewContext(text,context);
const panel=context.window.NexusMatchDetail.scoutHistory;
assert.equal(typeof panel,'function');

const snapshots=[
  {m:29,at:'2026-10-10T08:00:00+00:00',source:'FotMob',
   stats:{home:{shots_on:1,corners:2},away:{shots_on:0,corners:1}}},
  {m:34,at:'2026-10-10T08:10:00+00:00',source:'FotMob',
   stats:{home:{shots_on:3,corners:2},away:{shots_on:1,corners:2}}}
];
const html=panel({scout_snapshots:snapshots});
assert.match(html,/Scouts|No gol/);
assert.match(html,/29′–34′/);
assert.match(html,/No gol casa \+2/);
assert.match(html,/No gol fora \+1/);
assert.match(html,/Escanteios fora \+1/);
assert.match(html,/entre capturas/i);
assert.match(html,/observação, não o momento exato/);
assert.doesNotMatch(html,/evento aos 34/);

const single=panel({scout_snapshots:[snapshots[0]]});
assert.match(single,/1 captura/);
assert.doesNotMatch(single,/29′–34′/);
const missing=panel({scout_snapshots:[]});
assert.match(missing,/não há capturas cronológicas/);
const unsafe=panel({scout_snapshots:[{...snapshots[0],source:'<script>alert(1)</script>'}]});
assert.doesNotMatch(unsafe,/<script>/);
console.log('NEXUS: scouts com horario real, intervalos, ausencia de dados e sanitizacao OK');
