/* NEXUS Live: sobrepõe pressão/scouts AO VIVO do Worker Cloudflare (cron 2 min).
 * Desligado enquanto web/live-config.json não tiver URL. Nunca inventa dados:
 * só copia o que o Worker observou, com o horário real da observação. */
(function(root){
'use strict';
let config=null,cache=null,at=0;
async function loadConfig(fetcher){
  if(config)return config;
  try{const r=await fetcher('./live-config.json',{cache:'no-store'});config=r.ok?await r.json():{};}
  catch(_){config={};}
  return config;
}
function apply(value,live){
  if(!value||!Array.isArray(value.games)||!live||typeof live.games!=='object')return 0;
  let n=0;
  for(const g of value.games){
    const e=live.games[String(g.id)];
    if(!e||e.phase!=='live')continue;
    const fresh=Date.parse(e.observed_at||0);
    if(!Number.isFinite(fresh)||Date.now()-fresh>15*60000)continue; // dado velho não vira "ao vivo"
    g.phase='live';
    if(Number.isFinite(e.minute))g.minute=e.minute;
    if(/^\d+-\d+$/.test(String(e.score||'')))g.score=e.score;
    g.halftime=e.halftime===true;
    g.observed_at=e.observed_at;
    if(Array.isArray(e.points)&&e.points.length>=(g.pressure||[]).length){
      g.pressure=e.points.map(p=>({m:p.m,v:p.v}));
      if(e.pressure_observed_at)g.pressure_observed_at=e.pressure_observed_at;
      g.pressure_last_minute=e.points[e.points.length-1].m;
    }
    if(e.stats&&(Object.keys(e.stats.home||{}).length||Object.keys(e.stats.away||{}).length)){
      g.stats={home:{...(g.stats?.home||{}),...e.stats.home},away:{...(g.stats?.away||{}),...e.stats.away}};
      if(e.stats_observed_at)g.stats_observed_at=e.stats_observed_at;
    }
    g.live_source='NEXUS Live (Cloudflare, 2 min)';
    n++;
  }
  value.live_overlay={applied:n,updated_at:live.status?.updated_at||null};
  return n;
}
async function overlay(value,fetcher){
  try{
    const cfg=await loadConfig(fetcher);
    const url=String(cfg.url||'');
    if(!/^https:\/\/[a-z0-9.-]+\.workers\.dev$/i.test(url))return 0;
    if(!cache||Date.now()-at>15000){
      const r=await fetcher(url+'/live',{cache:'no-store'});
      if(!r.ok)return 0;
      cache=await r.json();at=Date.now();
    }
    return apply(value,cache);
  }catch(_){return 0;}
}
/* Ciclo rápido (20 s): atualiza na lista os jogos ao vivo direto do Worker,
   sem rebaixar o feed de 1 MB. Só dado observado há ≤15 min. */
function patchList(list,live){
  if(!Array.isArray(list)||!live||typeof live.games!=='object')return 0;
  let n=0;
  for(const m of list){
    const e=live.games[String(m.id)];
    if(!e||e.phase!=='live')continue;
    const t=Date.parse(e.observed_at||0);if(!Number.isFinite(t)||Date.now()-t>15*60000)continue;
    const sc=String(e.score||'').match(/^(\d+)-(\d+)$/);
    if(sc){m.home_score=+sc[1];m.away_score=+sc[2];m.score=sc[1]+'–'+sc[2];}
    if(Number.isFinite(e.minute))m.minute=e.minute;
    m.live=true;m.phase='live';m.halftime=e.halftime===true;m.status=m.halftime?'HT':'AO VIVO';
    if(Array.isArray(e.points)&&e.points.length){m.pressure_points=e.points.slice(-12);m.pressure_observed_at=e.pressure_observed_at||e.observed_at;m.has_saved_thermometer=true;}
    if(e.stats&&(Object.keys(e.stats.home||{}).length||Object.keys(e.stats.away||{}).length))
      m.scoreboard_stats={home:{...(m.scoreboard_stats?.home||{}),...e.stats.home},away:{...(m.scoreboard_stats?.away||{}),...e.stats.away}};
    m.observed_at=e.observed_at;n++;
  }
  return n;
}
let ticking=false;
async function tick(){
  if(ticking||document.hidden)return;ticking=true;
  try{
    const cfg=await loadConfig(fetch.bind(root));const url=String(cfg.url||'');
    if(!/^https:\/\/[a-z0-9.-]+\.workers\.dev$/i.test(url))return;
    const r=await fetch(url+'/live',{cache:'no-store'});if(!r.ok)return;
    cache=await r.json();at=Date.now();
    const st=typeof state!=='undefined'?state:null;
    if(st&&!st.demo&&!st.reference&&patchList(st.list,cache)&&typeof renderMatches==='function')renderMatches();
    const stamp=document.getElementById('nx-live-stamp');
    if(stamp&&cache.status?.updated_at)stamp.textContent='Ao vivo atualizado às '+new Date(cache.status.updated_at).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  }catch(_){}finally{ticking=false;}
}
if(typeof window!=='undefined'&&typeof document!=='undefined'){
  setInterval(tick,20000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)tick();});
  window.addEventListener('load',()=>setTimeout(tick,4000));
}
root.NexusLive={overlay,apply,patchList,tick};
if(typeof module!=='undefined'&&module.exports)module.exports=root.NexusLive;
})(typeof window!=='undefined'?window:globalThis);
