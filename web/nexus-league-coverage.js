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
function observationFreshness(value,nowSec=Date.now()/1000,maxMinutes=20){
 if(typeof value!=='string'||!value.trim())return 'unknown';
 const stamp=Date.parse(value);
 if(!Number.isFinite(stamp))return 'unknown';
 const lag=nowSec*1000-stamp;
 if(lag< -120000)return 'future';
 return lag<=maxMinutes*60000?'fresh':'stale';
}
function sourceFreshness(g,nowSec=Date.now()/1000){
 const observed=observationFreshness(g?.observed_at,nowSec);
 const statsAt=g?.stats_observed_at||(g?.scoreboard_stats?g?.observed_at:null);
 return {observed,stats:observationFreshness(statsAt,nowSec),
         pressure:observationFreshness(g?.pressure_observed_at,nowSec)};
}
function coverageStatus(g,nowSec=Date.now()/1000){
 if(!category(g?.league))return 'insuficiente';
 const stats=g.scoreboard_stats||g.stats||{};
 const keys=['shots_on','shots_total','corners','big_chances','possession','xg'];
 const count=s=>keys.filter(k=>num(stats[s]?.[k])).length;
 const p=g.pressure||g.thermometer;
 const hasPressure=(Array.isArray(p)&&p.length>=3)||
   (Array.isArray(p?.points)&&p.points.length>=3)||
   (num(p?.samples)&&Number(p.samples)>=3);
 const hasBothScouts=count('home')>=2&&count('away')>=2;
 if(hasPressure&&hasBothScouts){
   // Dados coletados anteriormente nao viram status "completa" em jogo live.
   if(g.phase!=='live')return 'completa';
   const fresh=sourceFreshness(g,nowSec);
   if(!g.stale&&fresh.observed==='fresh'&&fresh.stats==='fresh'&&fresh.pressure==='fresh')
      return 'completa';
 }
 if(visible(g))return 'parcial';
 return 'insuficiente';
}
function coverageEvidence(g,nowSec=Date.now()/1000){
 const status=coverageStatus(g,nowSec);
 const fresh=sourceFreshness(g,nowSec);
 const p=g?.pressure||g?.thermometer;
 const points=Array.isArray(p)?p:Array.isArray(p?.points)?p.points:[];
 const sourceSamples=points.length||Number(p?.samples||0);
 const stats=g?.scoreboard_stats||g?.stats||{};
 const scouts=['shots_on','shots_total','corners','big_chances','possession','xg'];
 const perSide=side=>scouts.filter(k=>num(stats?.[side]?.[k])).length;
 const realOdds=odds(g);
 const staleLive=g?.phase==='live'&&(g?.stale||fresh.observed!=='fresh'||
   (sourceSamples>0&&fresh.pressure!=='fresh')||
   (perSide('home')+perSide('away')>0&&fresh.stats!=='fresh'));
 return {status,source_pressure_samples:sourceSamples,
    home_scout_fields:perSide('home'),away_scout_fields:perSide('away'),
    odds_observed:realOdds, freshness:fresh, stale_live:!!staleLive,
    reason:staleLive?'Dados ao vivo sem horário recente verificado; não usar como pressão atual':
      status==='completa'?'Pressão e scouts recentes observados nos dois times':
      status==='parcial'?'Dados observados, mas cobertura insuficiente para análise completa':
       'Sem scouts verificáveis para avaliação' };
}
function analysisPriority(g,nowSec=Date.now()/1000){
 const status=coverageStatus(g,nowSec);
 const phase=g?.phase||'';
 const start=Number(g?.start_timestamp);
 const minutes=Number.isFinite(start)&&start>0?(start-nowSec)/60:null;
 const freshness=sourceFreshness(g,nowSec);
 const fresh=!g?.stale && freshness.observed==='fresh';
 // Radar de dados, NAO indicador de aposta ou liquidez de mercado.
 let score=status==='completa'?65:status==='parcial'?30:0;
 if(phase==='live')score+=12;
 if(phase==='scheduled'&&minutes!==null&&minutes>0&&minutes<=120)score+=10;
 if(fresh)score+=8;
 if(odds(g)&&(phase!=='live'||fresh))score+=5;
 if(phase==='live'&&!fresh)score=Math.min(10,score);
 return {score:Math.min(100,score),status,freshness:freshness.observed,
         kind:'data_quality_not_betting_signal',
   reason:status==='completa'?'Scouts e termômetro medidos':
          status==='parcial'?'Dados parciais disponíveis':'Scouts insuficientes',
   warning:'Sem dados não há justificativa para inferir pressão ou EV+'};
}
function leagueStats(games){
 const groups=new Map();
 for(const g of games||[]){
   if(!category(g?.league))continue;
   const x=groups.get(g.league)||{league:g.league,covered:0,measured:0,completa:0,parcial:0,insuficiente:0,total:0};
   x.total++;
   x[coverageStatus(g)]++;
   if(visible(g))x.covered++;
   if(level(g)===2)x.measured++;
   groups.set(g.league,x);
 }
 return [...groups.values()].filter(x=>x.covered>0).sort((a,b)=>b.measured-a.measured||b.covered-a.covered||a.league.localeCompare(b.league,'pt-BR'));
}
root.NexusLeagueCoverage={category,level,visible,leagueStats,measured,coverageStatus,coverageEvidence,analysisPriority,observationFreshness,sourceFreshness};
if(typeof module!=='undefined'&&module.exports)module.exports=root.NexusLeagueCoverage;
})(typeof window!=='undefined'?window:globalThis);
