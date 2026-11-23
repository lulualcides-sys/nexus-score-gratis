/* NEXUS Live — Cloudflare Worker (cron a cada 2 min).
 * Lê jogos AO VIVO no FotMob, guarda pressão por minuto (momentum) e scouts
 * REALMENTE publicados e serve GET /live para o site. Nunca inventa pressão:
 * jogos sem momentum ficam com points vazio e state explícito.
 */
const FM = 'https://www.fotmob.com/api/data/';
const HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; NEXUS-live/1.0)',
  'Accept': 'application/json', 'Referer': 'https://www.fotmob.com/'};
export const MAX_DETAILS = 40;          // limite de subrequests do plano grátis (50)
export const KEEP_FINISHED_MS = 3 * 3600e3;
const STAT_ALIAS = {'shots on target': 'shots_on', 'total shots': 'shots_total', 'shots': 'shots_total',
  'corners': 'corners', 'corner kicks': 'corners', 'ball possession': 'possession', 'possession': 'possession',
  'expected goals (xg)': 'xg', 'expected goals': 'xg', 'xg': 'xg', 'big chances': 'big_chances',
  'shots off target': 'shots_off', 'yellow cards': 'yellow_cards', 'red cards': 'red_cards'};

export function brDate(now = Date.now()) {
  const d = new Date(now - 3 * 3600e3);
  return d.toISOString().slice(0, 10).replace(/-/g, '');
}

export function momentum(packet) {
  const content = packet && typeof packet === 'object' ? packet.content : null;
  if (!content || typeof content !== 'object') return {points: [], state: 'missing'};
  const facts = content.matchFacts && typeof content.matchFacts === 'object' ? content.matchFacts : {};
  let container = false, notProvided = false, list = false;
  for (const item of [facts.momentum, content.momentum]) {
    if (item === undefined || item === null) continue;
    container = true;
    if (item === false) { notProvided = true; continue; }
    let data = Array.isArray(item) ? item : null;
    if (!data && typeof item === 'object') {
      const main = item.main;
      data = Array.isArray(main) ? main : (main && Array.isArray(main.data) ? main.data : null);
      if (!data && Array.isArray(item.data)) data = item.data;
    }
    if (!Array.isArray(data)) continue;
    list = true;
    const found = new Map();
    for (const e of data) {
      if (!e || typeof e !== 'object' || typeof e.minute === 'boolean' || typeof e.value === 'boolean') continue;
      const m = Number(e.minute), v = Number(e.value);
      if (!Number.isInteger(m) || !Number.isFinite(v) || m < 1 || m > 150 || Math.abs(v) > 1000) continue;
      if (typeof e.minute === 'string' && e.minute.trim() !== String(m)) continue;
      found.set(m, {m, v: Math.round(v * 100) / 100});
    }
    if (found.size) return {points: [...found.values()].sort((a, b) => a.m - b.m), state: 'observed'};
  }
  return {points: [], state: !container ? 'missing' : list ? 'no_valid_points' : notProvided ? 'not_provided' : 'unsupported_shape'};
}

export function stats(packet) {
  const all = packet?.content?.stats?.Periods?.All || {};
  const out = {home: {}, away: {}};
  for (const group of all.stats || []) for (const item of group?.stats || []) {
    const key = STAT_ALIAS[String(item?.title || '').trim().toLowerCase()];
    const values = item?.stats;
    if (!key || !Array.isArray(values) || values.length !== 2) continue;
    ['home', 'away'].forEach((side, i) => {
      const n = Number(String(values[i]).replace('%', '').replace(',', '.'));
      if (Number.isFinite(n)) out[side][key] = n;
    });
  }
  return out;
}

export function liveGames(list) {
  const out = [];
  for (const league of list?.leagues || []) for (const ev of league?.matches || []) {
    const st = ev?.status || {};
    if (!st.started || st.finished || st.cancelled) continue;
    const id = String(ev.id || '');
    if (!/^\d+$/.test(id)) continue;
    const clock = String(st.liveTime?.short || '');
    const mm = clock.match(/(\d{1,3})/);
    out.push({id: 'fotmob-' + id, mid: id, league_id: String(league.primaryId || ''),
      minute: mm ? Number(mm[1]) : null, halftime: /^HT$|half/i.test(clock),
      score: [ev.home?.score, ev.away?.score].map(x => Number.isFinite(+x) ? +x : '?').join('-')});
  }
  return out;
}

/* Prioridade: ligas principais (IDs FotMob) primeiro; depois o resto. */
const MAIN = new Set(['268','8814','9067','45','299','42','73','10216','47','48','87','55','54','53','61','57','111','130','230','112','536','77']);
export function prioritize(games) {
  return [...games].sort((a, b) => (MAIN.has(b.league_id) - MAIN.has(a.league_id)) || ((b.minute || 0) - (a.minute || 0)));
}

export function mergeGame(prev, live, det, nowIso) {
  const old = prev?.points || [];
  const byMin = new Map(old.map(p => [p.m, p]));
  for (const p of det?.points || []) byMin.set(p.m, p);
  const s = det?.stats || {};
  const hasStats = Object.keys(s.home || {}).length || Object.keys(s.away || {}).length;
  return {minute: live.minute, halftime: live.halftime, score: live.score,
    observed_at: nowIso, points: [...byMin.values()].sort((a, b) => a.m - b.m).slice(-150),
    pressure_observed_at: det?.points?.length ? nowIso : (prev?.pressure_observed_at || null),
    momentum_state: det ? det.state : (prev?.momentum_state || 'not_checked'),
    stats: hasStats ? s : (prev?.stats || null),
    stats_observed_at: hasStats ? nowIso : (prev?.stats_observed_at || null), phase: 'live'};
}

async function getJson(url) {
  const r = await fetch(url, {headers: HEADERS, cf: {cacheTtl: 0}});
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

export async function collect(env, now = Date.now(), fetcher = getJson) {
  const nowIso = new Date(now).toISOString();
  const prev = (await env.LIVE.get('live', 'json')) || {games: {}};
  const status = {updated_at: nowIso, live_found: 0, details: 0, with_pressure: 0, errors: []};
  let games;
  try { games = liveGames(await fetcher(FM + 'matches?date=' + brDate(now))); }
  catch (e) { status.errors.push('lista: ' + String(e.message).slice(0, 80)); games = null; }
  const next = {};
  if (games) {
    status.live_found = games.length;
    const chosen = prioritize(games).slice(0, MAX_DETAILS);
    const results = await Promise.allSettled(chosen.map(g => fetcher(FM + 'matchDetails?matchId=' + g.mid)));
    const byId = new Map(games.map(g => [g.id, null]));
    chosen.forEach((g, i) => {
      const r = results[i];
      if (r.status === 'fulfilled') { const m = momentum(r.value); byId.set(g.id, {...m, stats: stats(r.value)}); status.details++; }
      else if (status.errors.length < 6) status.errors.push(g.id + ': ' + String(r.reason?.message || r.reason).slice(0, 60));
    });
    for (const g of games) {
      next[g.id] = mergeGame(prev.games[g.id], g, byId.get(g.id), nowIso);
      if (next[g.id].points.length) status.with_pressure++;
    }
  }
  // Jogos que saíram da lista ao vivo: mantidos como encerrados por 3 h (sem novos dados).
  for (const [id, g] of Object.entries(prev.games || {})) {
    if (next[id]) continue;
    const age = now - Date.parse(g.observed_at || 0);
    if (games && age < KEEP_FINISHED_MS) next[id] = {...g, phase: g.phase === 'live' ? 'ended_or_unlisted' : g.phase};
    else if (!games) next[id] = g;
  }
  const doc = {schema: 1, source: 'FotMob via Cloudflare Worker', status, games: next};
  await env.LIVE.put('live', JSON.stringify(doc));
  return doc;
}

const CORS = {'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=30',
  'Content-Type': 'application/json; charset=utf-8'};

export default {
  async scheduled(event, env, ctx) { ctx.waitUntil(collect(env)); },
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== '/live') return new Response('NEXUS live: use /live', {status: 404, headers: CORS});
    const doc = await env.LIVE.get('live');
    return new Response(doc || JSON.stringify({schema: 1, status: {state: 'not_collected_yet'}, games: {}}), {headers: CORS});
  }
};
