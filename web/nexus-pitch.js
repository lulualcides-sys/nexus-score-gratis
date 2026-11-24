/* NEXUS Mapa ao vivo: campo animado que mostra para onde o jogo pende,
 * a partir da curva de pressão REAL da fonte (últimos minutos).
 * Não é a posição da bola (as fontes grátis não publicam rastreamento). */
(function(root){
'use strict';
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
// Pressão média dos últimos pontos -> posição horizontal (mandante ataca para a direita).
function tilt(points){
  const pts=(points||[]).filter(p=>Number.isFinite(+p.m)&&Number.isFinite(+p.v));
  if(pts.length<3)return null;
  const last=pts[pts.length-1].m,win=pts.filter(p=>p.m>last-3);
  const avg=win.reduce((a,p)=>a+(+p.v),0)/win.length;
  return {avg,x:50+clamp(avg,-100,100)*0.38,minute:last,
    level:Math.abs(avg)>=50?'forte':Math.abs(avg)>=30?'moderada':'equilibrado',side:avg>0?'home':'away'};
}
function svg(t,home,away){
  const hot=t.level==='forte';
  return `<svg viewBox="0 0 100 60" class="nx-pitch-svg" role="img" aria-label="Campo: jogo pendendo para ${t.side==='home'?'o ataque do mandante':'o ataque do visitante'}">
  <rect x="0" y="0" width="100" height="60" rx="3" class="grass"/>
  ${[0,1,2,3,4].map(i=>`<rect x="${i*20}" y="0" width="10" height="60" class="stripe"/>`).join('')}
  <g class="lines"><rect x="2" y="2" width="96" height="56" rx="1"/><line x1="50" y1="2" x2="50" y2="58"/><circle cx="50" cy="30" r="8"/>
  <rect x="2" y="17" width="14" height="26"/><rect x="84" y="17" width="14" height="26"/><rect x="2" y="24" width="5" height="12"/><rect x="93" y="24" width="5" height="12"/></g>
  <rect x="${t.side==='home'?84:2}" y="17" width="14" height="26" class="zone ${hot?'hot':''}" opacity="${t.level==='equilibrado'?0:hot?.55:.3}"/>
  <g class="ball" style="transform:translate(${t.x.toFixed(1)}px,30px)"><circle r="2.6" class="halo ${hot?'hot':''}"/><circle r="1.6"/></g>
  <text x="4" y="56" class="lbl">${esc(home)} →</text><text x="96" y="56" text-anchor="end" class="lbl">← ${esc(away)}</text></svg>`;
}
function esc(s){return String(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function render(){
  const body=document.getElementById('detail-body');if(!body)return;
  const st=typeof state!=='undefined'?state:null;if(!st||!st.selection)return;
  const m=(st.list||[]).find(x=>x.id===st.selection);
  let box=body.querySelector('.nx-pitch');
  const fresh=m&&m.live&&Date.now()-Date.parse(m.pressure_observed_at||0)<=15*60000;
  const t=fresh?tilt(m.pressure_points):null;
  if(!t){if(box)box.remove();return;}
  const html=`<div class="nx-pitch-head"><b>🗺️ Mapa ao vivo</b><span>${t.minute}′ · ${t.level==='equilibrado'?'jogo equilibrado':(t.side==='home'?esc(m.home):esc(m.away))+' pressionando'+(t.level==='forte'?' forte':'')}</span></div>${svg(t,m.home,m.away)}
    <small>Mostra para onde o jogo pende pela pressão real dos últimos minutos. Não é a posição real da bola.</small>`;
  if(!box){box=document.createElement('section');box.className='nx-pitch';body.prepend(box);}
  const ball=box.querySelector('.ball');
  if(ball&&box.dataset.id===m.id){ // anima a bola até a nova posição
    ball.style.transform=`translate(${t.x.toFixed(1)}px,30px)`;
    box.querySelector('.nx-pitch-head span').innerHTML=html.match(/<span>(.*?)<\/span>/)[1];
    const z=box.querySelector('.zone');const tmp=document.createElement('div');tmp.innerHTML=svg(t,m.home,m.away);
    z.replaceWith(tmp.querySelector('.zone'));
  }else{box.innerHTML=html;box.dataset.id=m.id;}
}
if(typeof window!=='undefined'&&typeof document!=='undefined'){
  setInterval(render,5000);
  new MutationObserver(()=>{if(!document.querySelector('#detail-body .nx-pitch'))render();})
    .observe(document.documentElement,{childList:true,subtree:true});
}
root.NexusPitch={tilt,render};
if(typeof module!=='undefined'&&module.exports)module.exports=root.NexusPitch;
})(typeof window!=='undefined'?window:globalThis);
