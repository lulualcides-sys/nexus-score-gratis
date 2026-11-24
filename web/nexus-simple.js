/* Modo simples (padrão) × completo. Preferência só neste navegador. */
(function(){
'use strict';
const KEY='nexusSimpleMode',PINS='nexusPinnedLeagues',NOODDS='nexusHideOdds';
const read=(k,d)=>{try{const v=localStorage.getItem(k);return v===null?d:JSON.parse(v)}catch(_){return d}};
const save=(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v))}catch(_){}};
let pins=new Set(read(PINS,[]));let hideOdds=read(NOODDS,false)===true;
function rerender(){if(typeof window.renderMatches==='function')window.renderMatches();}
let simple=true;
try{simple=localStorage.getItem(KEY)!=='0'}catch(_){}
function apply(){
  document.body.classList.toggle('nx-simple',simple);
  document.body.classList.toggle('nx-no-odds',hideOdds);
  const oc=document.getElementById('nx-hide-odds');if(oc)oc.checked=hideOdds;
  const b=document.getElementById('nx-mode-toggle');
  if(b){b.textContent=simple?'☰ Modo completo':'✦ Modo simples';b.setAttribute('aria-pressed',String(!simple));}
}
function setup(){
  const actions=document.querySelector('.header-actions');
  if(actions&&!document.getElementById('nx-mode-toggle')){
    const b=document.createElement('button');b.type='button';b.id='nx-mode-toggle';b.className='nx-mode-toggle';
    b.title='Mostrar ou esconder indicadores técnicos e filtros avançados';
    b.addEventListener('click',()=>{simple=!simple;try{localStorage.setItem(KEY,simple?'1':'0')}catch(_){}apply();rerender();});
    actions.prepend(b);
  }
  // Filtros de abrangência/radar dentro de um "Filtros" recolhível.
  const league=document.querySelector('.nexus-league-quick'),radar=document.querySelector('.nexus-radar-controls');
  if(league&&!league.closest('.nx-filters')){
    const box=document.createElement('details');box.className='nx-filters';
    box.innerHTML='<summary>⚙ Filtros</summary>';
    league.parentNode.insertBefore(box,league);box.append(league);if(radar)box.append(radar);
    const lab=document.createElement('label');lab.className='nx-odds-toggle';
    lab.innerHTML='<input type="checkbox" id="nx-hide-odds"> Esconder todas as odds';
    box.append(lab);
    lab.querySelector('input').addEventListener('change',e=>{hideOdds=e.target.checked;save(NOODDS,hideOdds);apply();});
  }
  // Fixar ligas favoritas no topo (📌 no cabeçalho do campeonato).
  document.addEventListener('click',ev=>{
    const b=ev.target.closest&&ev.target.closest('[data-pin-league]');if(!b)return;
    ev.preventDefault();ev.stopPropagation();
    const name=b.dataset.pinLeague;pins.has(name)?pins.delete(name):pins.add(name);save(PINS,[...pins]);rerender();
  },true);
  // Celular: tocar num jogo abre o detalhe em tela cheia; Voltar fecha.
  if(!document.getElementById('nx-back')){
    const back=document.createElement('button');back.type='button';back.id='nx-back';back.className='nx-back';
    back.textContent='← Voltar aos jogos';
    back.addEventListener('click',()=>{document.body.classList.remove('nx-sheet');if(lastY!==null)window.scrollTo(0,lastY);});
    document.body.append(back);
  }
  let lastY=null;
  document.addEventListener('click',ev=>{
    const card=ev.target.closest&&ev.target.closest('.match-item,[data-match]');
    if(!card||ev.target.closest('.fav,[data-favorite]'))return;
    if(!window.matchMedia('(max-width:900px)').matches)return;
    lastY=window.scrollY;document.body.classList.add('nx-sheet');
    const panel=document.querySelector('.detail-panel');if(panel)panel.scrollTop=0;
  },true);
  document.addEventListener('keydown',ev=>{if(ev.key==='Escape')document.body.classList.remove('nx-sheet');});
  apply();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);else setup();
/* Datas cruas da fonte (2026-11-24T00:52:46.89+00:00) viram "24/11 21:52" (Brasília). */
const ISO=/\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2}))\b/g;
function prettyDates(root){
  const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);const hits=[];
  while(w.nextNode()){if(ISO.test(w.currentNode.nodeValue))hits.push(w.currentNode);ISO.lastIndex=0;}
  for(const n of hits)n.nodeValue=n.nodeValue.replace(ISO,iso=>{const d=new Date(iso);if(isNaN(d))return iso;
    return d.toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).replace(',','');});
}
let datesQueued=false;
new MutationObserver(()=>{if(datesQueued)return;datesQueued=true;requestAnimationFrame(()=>{datesQueued=false;const d=document.getElementById('detail-body');if(d)prettyDates(d);});})
  .observe(document.documentElement,{childList:true,subtree:true});
window.NexusSimple={isSimple:()=>simple,isPinned:n=>pins.has(String(n)),pinned:()=>[...pins]};
})();
