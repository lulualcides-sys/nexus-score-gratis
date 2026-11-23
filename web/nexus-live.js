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
    if(!cache||Date.now()-at>50000){
      const r=await fetcher(url+'/live',{cache:'no-store'});
      if(!r.ok)return 0;
      cache=await r.json();at=Date.now();
    }
    return apply(value,cache);
  }catch(_){return 0;}
}
root.NexusLive={overlay,apply};
if(typeof module!=='undefined'&&module.exports)module.exports=root.NexusLive;
})(typeof window!=='undefined'?window:globalThis);
