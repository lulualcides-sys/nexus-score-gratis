/* Mostra só ligas principais com cobertura observável. Não altera coletas ou histórico. */
(function(root){
'use strict';
const norm=x=>String(x||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const reject=/\b(?:women|woman|feminino|feminina|femenina|ladies|youth|juvenil|reservas|reserves|amateur|amador|friendly|amistoso|sub ?(?:17|19|20|21|23)|u ?(?:17|19|20|21|23)|qualifier|qualificacao|qualifying|division 3|division 4|segunda division|primera b)\b/;
const main=[
/\b(?:uefa )?champions league\b/,/\b(?:uefa )?europa league\b/,/\b(?:copa )?libertadores\b/,
/\b(?:copa )?(?:sudamericana|sul americana)\b/,/\bcopa do brasil\b/,
/\b(?:brasileirao(?: serie [ab])?|brazilian serie [ab]|campeonato brasileiro serie [ab]|brasil serie [ab]|serie b do brasil)\b/,
/\b(?:english )?premier league\b/,/\b(?:la liga|laliga|primera division spain|spain primera division)\b/,
/\b(?:italian serie a|italy serie a|serie a italy|serie a italiana)\b/,
/\b(?:german )?bundesliga\b/,/\bligue 1\b/,
/\b(?:primeira liga|liga portugal|portuguese primeira)\b/,
/\beredi(?:visie)?\b/,/\b(?:liga profesional|argentine primera|argentina primera division|superliga argentina|primera division argentina)\b/,
/\b(?:mls|major league soccer)\b/,/\b(?:liga mx|mexican primera|mexico primera division)\b/,
/\b(?:fifa )?(?:world cup|copa do mundo)\b/
];
function category(league){
 const x=norm(league);
 if(!x||reject.test(x)||/\b(?:2 bundesliga|bundesliga 2|primavera|serie a2|serie a 2|liga expansion)\b/.test(x))return false;
 return main.some(rx=>rx.test(x))||/^(?:serie a|serie a tim)$/.test(x);
}
const num=x=>x!=null&&x!==''&&typeof x!=='boolean'&&Number.isFinite(Number(x));
function stats(s){
 const keys=['shots_on','shots_off','shots_total','corners','big_chances','dangerous_attacks','xg','possession','fouls','yellow_cards'];
 return !!s&&['home','away'].some(side=>keys.some(key=>num(s[side]?.[key])));
}
function odds(g){
 if(g.odds_available===true)return true;
 if(Array.isArray(g.quotes)&&g.quotes.some(q=>num(q.odds)&&Number(q.odds)>1&&q.source))return true;
 if(Array.isArray(g.odds))return g.odds.some(q=>num(q.odd??q.odds)&&Number(q.odd??q.odds)>1&&q.source);
 const o=g.odds||{};
 return o.available===true||Object.values(o.markets?.['1x2']||{}).some(x=>num(x)&&Number(x)>1);
}
function measured(g){
 const p=g.pressure||g.thermometer;
 return g.has_saved_thermometer===true||g.__hasThermo===true||
   (Array.isArray(p)&&p.length>0)||(Array.isArray(p?.points)&&p.points.length>0)||
   (num(p?.samples)&&Number(p.samples)>0)||stats(g.scoreboard_stats||g.stats)||odds(g)||
   (Array.isArray(g.events)&&g.events.some(e=>['goal','shot_on','corner','red_card'].includes(e?.type)));
}
function agenda(g){
 return g.phase==='scheduled'&&num(g.start_timestamp)&&Number(g.start_timestamp)>0&&
 /(?:espn|fotmob|sofascore|livescore|football|soccerway)/i.test(String(g.source||g.sources?.join(' ')||''))&&
 Boolean(String(g.home||'').trim()&&String(g.away||'').trim());
}
function level(g){
 if(!g||!category(g.league))return 0;
 if(measured(g))return 2;
 if(g.phase==='finished'&&/^\d{1,2}\s*[-–:]\s*\d{1,2}$/.test(String(g.score||''))&&g.score_unverified!==true)return 2;
 return agenda(g)?1:0;
}
const visible=g=>level(g)>0;
function leagueStats(games){
 const groups=new Map();
 for(const g of games||[]){
   if(!category(g?.league))continue;
   const x=groups.get(g.league)||{league:g.league,covered:0,measured:0};
   if(visible(g))x.covered++;
   if(level(g)===2)x.measured++;
   groups.set(g.league,x);
 }
 return [...groups.values()].filter(x=>x.covered>0).sort((a,b)=>b.measured-a.measured||b.covered-a.covered||a.league.localeCompare(b.league,'pt-BR'));
}
root.NexusLeagueCoverage={category,level,visible,leagueStats,measured};
if(typeof module!=='undefined'&&module.exports)module.exports=root.NexusLeagueCoverage;
})(typeof window!=='undefined'?window:globalThis);
