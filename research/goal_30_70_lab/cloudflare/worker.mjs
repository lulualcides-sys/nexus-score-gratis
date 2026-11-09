/* NEXUS 30–70 sampling POC. DISABLED until authorized source and D1 are connected.
   No guessing goals, pressure or odds. No scraper/proxy credentials. */
const allowed=/(?:brasileir[aã]o|campeonato brasileiro|brazil|brasil|premier league|champions league|la liga|bundesliga|serie a|ligue 1|libertadores|europa league|copa do brasil|(?:uefa |europa )?conference league|saudi (?:pro|professional) league|roshn saudi league|^efl championship$|^english championship$|^championship$|eerste divisie|keuken kampioen divisie)/i;
const women=/(?:women|woman|feminin|femenin|femmen|femmin|ladies|female|wsl|nwsl|liga f|\(w\))/i;
const number=x=>x!==null&&x!==undefined&&x!==''&&!Number.isNaN(Number(x))&&Number.isFinite(Number(x))?Number(x):null;

export function sanitizedGame(g,now=Date.now()){
 if(!g||typeof g!=='object'||g.phase!=='live')return null;
 const league=String(g.league||'').slice(0,85);
 if(!allowed.test(league)||women.test(league)||women.test(g.home||'')||women.test(g.away||''))return null;
 const minute=number(g.minute),observed=Date.parse(g.observed_at||'');
 if(!Number.isInteger(minute)||minute<30||minute>70||!Number.isFinite(observed))return null;
 const age=now-observed;
 if(age<0||age>180000)return null; // data strictly fresh
 const pressure=number(g.pressure),shots=number(g.shots_on),chances=number(g.big_chances);
 if(pressure===null&&shots===null&&chances===null)return null;
 if((pressure!==null&&(pressure<0||pressure>100))||
    (shots!==null&&(shots<0||shots>100))||
    (chances!==null&&(chances<0||chances>30)))return null;
 const id=String(g.match_id||'').slice(0,95);
 const score=String(g.score||'').slice(0,9);
 if(!/^[a-zA-Z0-9_:.-]{2,95}$/.test(id)||!/^\d{1,2}-\d{1,2}$/.test(score))return null;
 return {match_id:id,league,minute,score,pressure,shots,chances,
         observed_at:new Date(observed).toISOString()};
}

export async function collect(env,now=Date.now()){
 if(!env||!env.AUTHORIZED_FEED_URL||!env.DB)
   return {state:'disabled_missing_authorized_source_or_database',saved:0};
 let u;
 try{u=new URL(env.AUTHORIZED_FEED_URL)}catch{return {state:'invalid_source_url',saved:0}}
 if(u.protocol!=='https:'||u.username||u.password||u.hostname==='localhost')
   return {state:'invalid_source_url',saved:0};
 if(env.AUTHORIZED_FEED_HOST!==u.hostname)
   return {state:'source_host_not_authorized',saved:0};
 const response=await fetch(u.toString(),{headers:{Accept:'application/json'},
                                          redirect:'error',cache:'no-store'});
 if(!response.ok)return {state:'source_http_'+response.status,saved:0};
 const type=response.headers.get('content-type')||'';
 if(!type.includes('json'))return {state:'source_not_json',saved:0};
 const payload=await response.json();
 const games=Array.isArray(payload?.games)?payload.games:[];
 let saved=0;
 for(const original of games.slice(0,60)){
   const g=sanitizedGame(original,now);
   if(!g)continue;
   await env.DB.prepare(
     'INSERT OR IGNORE INTO live_observations (match_id, league, minute, score, pressure, shots_on, big_chances, observed_at, polled_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
   ).bind(g.match_id,g.league,g.minute,g.score,g.pressure,g.shots,g.chances,g.observed_at,new Date(now).toISOString()).run();
   saved++;
 }
 return {state:'ok_observations_only',saved,examined:Math.min(games.length,60)};
}
export default {
 async scheduled(event,env,ctx){
   ctx.waitUntil(collect(env).then(x=>console.log('NEXUS-30-70',JSON.stringify(x)))
     .catch(e=>console.error('NEXUS-30-70 source failure',e?.name||'unknown')));
 },
 async fetch(){
   return new Response(JSON.stringify({name:'NEXUS 30–70 pilot',state:'inactive_until_authorized_source_configured',
     note:'No predictions, odds or data access via public endpoint.'}),{
     headers:{'content-type':'application/json','cache-control':'no-store'}});
 }
};
