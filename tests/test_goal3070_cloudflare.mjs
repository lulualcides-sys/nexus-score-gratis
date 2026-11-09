import assert from 'node:assert/strict';
import {sanitizedGame,collect} from '../research/goal_30_70_lab/cloudflare/worker.mjs';
const now=Date.parse('2026-11-09T11:00:00Z');
const data={match_id:'game-123',league:'Brasileirão Série B',minute:52,
 phase:'live',score:'0-0',observed_at:'2026-11-09T10:59:00Z',
 pressure:64,shots_on:2,big_chances:1};
assert.equal(sanitizedGame(data,now).minute,52);
assert.equal(sanitizedGame({...data,minute:71},now),null);
assert.equal(sanitizedGame({...data,league:'Brasileirão Feminino'},now),null);
assert.equal(sanitizedGame({...data,observed_at:'2026-11-09T10:40:00Z'},now),null);
assert.equal(sanitizedGame({...data,pressure:null,shots_on:null,big_chances:null},now),null);
assert.equal((await collect({},now)).state,'disabled_missing_authorized_source_or_database');
console.log('Cloudflare sampler safe-by-default smoke: OK');
