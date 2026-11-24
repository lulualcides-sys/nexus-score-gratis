/* Modo simples (padrão) × completo. Preferência só neste navegador. */
(function(){
'use strict';
const KEY='nexusSimpleMode';
let simple=true;
try{simple=localStorage.getItem(KEY)!=='0'}catch(_){}
function apply(){
  document.body.classList.toggle('nx-simple',simple);
  const b=document.getElementById('nx-mode-toggle');
  if(b){b.textContent=simple?'☰ Modo completo':'✦ Modo simples';b.setAttribute('aria-pressed',String(!simple));}
}
function setup(){
  const actions=document.querySelector('.header-actions');
  if(actions&&!document.getElementById('nx-mode-toggle')){
    const b=document.createElement('button');b.type='button';b.id='nx-mode-toggle';b.className='nx-mode-toggle';
    b.title='Mostrar ou esconder indicadores técnicos e filtros avançados';
    b.addEventListener('click',()=>{simple=!simple;try{localStorage.setItem(KEY,simple?'1':'0')}catch(_){}apply();if(typeof window.renderMatches==='function')window.renderMatches();else document.getElementById('refresh')?.click();});
    actions.prepend(b);
  }
  // Filtros de abrangência/radar dentro de um "Filtros" recolhível.
  const league=document.querySelector('.nexus-league-quick'),radar=document.querySelector('.nexus-radar-controls');
  if(league&&!league.closest('.nx-filters')){
    const box=document.createElement('details');box.className='nx-filters';
    box.innerHTML='<summary>⚙ Filtros</summary>';
    league.parentNode.insertBefore(box,league);box.append(league);if(radar)box.append(radar);
  }
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
window.NexusSimple={isSimple:()=>simple};
})();
