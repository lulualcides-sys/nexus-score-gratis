import assert from 'node:assert/strict';
import {momentum, stats, liveGames, prioritize, mergeGame, collect, brDate, MAX_DETAILS} from '../live_worker/worker.mjs';

// momentum: só o que a fonte publica
assert.deepEqual(momentum({content: {matchFacts: {momentum: {main: {data: [{minute: 1, value: 12}, {minute: '2', value: -5}, {minute: 'x', value: 1}]}}}}}).points,
  [{m: 1, v: 12}, {m: 2, v: -5}]);
assert.equal(momentum({content: {momentum: false}}).state, 'not_provided');
assert.equal(momentum({content: {}}).state, 'missing');
assert.equal(momentum({content: {momentum: {main: {data: [{minute: true, value: 3}]}}}}).state, 'no_valid_points');

// stats
const s = stats({content: {stats: {Periods: {All: {stats: [{stats: [{title: 'Shots on target', stats: [4, 1]}, {title: 'Ball possession', stats: ['61%', '39%']}]}]}}}}});
assert.deepEqual(s, {home: {shots_on: 4, possession: 61}, away: {shots_on: 1, possession: 39}});

// lista ao vivo
const list = {leagues: [{primaryId: 9999, matches: [
  {id: 1, status: {started: true, finished: false, liveTime: {short: "67'"}}, home: {score: 1}, away: {score: 0}},
  {id: 2, status: {started: true, finished: true}},
  {id: 3, status: {started: false}}]},
  {primaryId: 47, matches: [{id: 4, status: {started: true, liveTime: {short: "12'"}}, home: {score: 0}, away: {score: 0}}]}]};
const g = liveGames(list);
assert.deepEqual(g.map(x => x.id), ['fotmob-1', 'fotmob-4']);
assert.equal(g[0].minute, 67);
assert.equal(prioritize(g)[0].id, 'fotmob-4', 'Premier League primeiro');

// merge mantém pontos antigos e acrescenta novos
const m = mergeGame({points: [{m: 1, v: 3}], momentum_state: 'observed'}, g[0], {points: [{m: 2, v: 4}], state: 'observed', stats: {home: {}, away: {}}}, 'T');
assert.deepEqual(m.points.map(p => p.m), [1, 2]);
assert.equal(m.stats, null, 'sem scouts novos e sem antigos: null, não inventa');

// collect ponta a ponta com KV falso
const store = new Map();
const env = {LIVE: {get: async (k, t) => store.has(k) ? (t === 'json' ? JSON.parse(store.get(k)) : store.get(k)) : null,
  put: async (k, v) => store.set(k, v)}};
const detail = {content: {matchFacts: {momentum: {main: {data: [{minute: 66, value: 40}]}}}}};
const fetcher = async url => url.includes('matches?date=') ? list : url.includes('matchId=1') ? detail : {content: {momentum: false}};
const doc = await collect(env, Date.parse('2026-11-23T20:00:00Z'), fetcher);
assert.equal(doc.status.live_found, 2);
assert.equal(doc.status.with_pressure, 1);
assert.deepEqual(doc.games['fotmob-1'].points, [{m: 66, v: 40}]);
assert.equal(doc.games['fotmob-4'].momentum_state, 'not_provided');
// jogo que terminou some da lista: mantido marcado, sem novos dados
const later = await collect(env, Date.parse('2026-11-23T20:30:00Z'), async url => url.includes('matches?date=') ? {leagues: []} : {});
assert.equal(later.games['fotmob-1'].phase, 'ended_or_unlisted');
// falha da lista não apaga o que existe
const fail = await collect(env, Date.parse('2026-11-23T20:32:00Z'), async () => { throw new Error('down'); });
assert.ok(fail.games['fotmob-1'] && fail.status.errors.length);
assert.equal(brDate(Date.parse('2026-11-24T02:00:00Z')), '20261123', 'data no fuso de Brasília');
assert.ok(MAX_DETAILS <= 45, 'cabe no limite grátis de subrequests');
console.log('NEXUS live worker: OK');
