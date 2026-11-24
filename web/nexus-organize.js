/* Organiza Coletas e NEXUS LAB (modo simples): resumo no topo, seções
   recolhíveis, abas compactas. Só move elementos existentes (mantém os ids,
   então as atualizações do site continuam funcionando). Nada é apagado. */
(function(){
'use strict';
const GROUPS=[
  ['Saúde das fontes',['cloud-status','cloud-feed-freshness','cloud-source-health','cloud-league-coverage']],
  ['Modelo e mercados',['cloud-model-validation','cloud-audit','nexus-units-paper','cloud-platform']],
  ['Sinais e alertas',['cloud-signal-journal','cloud-intelligence-v6','cloud-goal-30-70','cloud-signal-evaluation']],
  ['Partidas coletadas',['cloud-controls','cloud-hide-results','cloud-results','cloud-load-more']]
];
function byIdOrClass(root,key){return root.querySelector('#'+key)||root.querySelector('.'+key);}
function organizeCloud(){
  const view=document.getElementById('cloud-view');
  if(!view||view.dataset.nxOrganized)return;
  const anchor=byIdOrClass(view,'cloud-metrics');if(!anchor)return;
  let after=anchor;
  for(const [title,keys] of GROUPS){
    const nodes=keys.map(k=>byIdOrClass(view,k)).filter(Boolean);
    if(!nodes.length)continue;
    const box=document.createElement('details');box.className='nx-group';
    box.innerHTML='<summary>'+title+'</summary>';
    after.after(box);after=box;
    for(const n of nodes)box.append(n);
  }
  view.dataset.nxOrganized='1';
}
function organizeLab(){
  const view=document.getElementById('intelligence-view');
  if(!view)return;
  // Caixas de números todas zeradas viram uma linha honesta.
  const tiles=[...view.querySelectorAll('.lab-metrics .metric-value')];
  const empty=tiles.length&&tiles.slice(1).every(t=>/^(0|—|-|)$/.test(t.textContent.trim()));
  view.classList.toggle('nx-lab-empty',!!empty);
  let note=view.querySelector('.nx-lab-note');
  if(empty&&!note){note=document.createElement('p');note.className='nx-lab-note';
    note.textContent='Ainda não há entradas validadas antes do jogo nem resultado simulado. O estudo de 23/11 mostrou que as casas preveem melhor que o modelo; por isso nenhuma "oportunidade" é mostrada como vantagem.';
    view.querySelector('.lab-metrics')?.after(note);}
  if(!empty&&note)note.remove();
  // Explicação longa de EV recolhida.
  for(const box of view.querySelectorAll('.n53-ev-explain')){
    if(box.closest('details'))continue;
    const d=document.createElement('details');d.className='nx-group nx-inline';
    d.innerHTML='<summary>Como interpretar EV+?</summary>';box.before(d);d.append(box);
    const h=box.querySelector('b');if(h&&/Como interpretar/.test(h.textContent))h.remove();
  }
}
function run(){if(!document.body.classList.contains('nx-simple'))return;organizeCloud();organizeLab();}
let q=false;
new MutationObserver(()=>{if(q)return;q=true;requestAnimationFrame(()=>{q=false;run();});})
  .observe(document.documentElement,{childList:true,subtree:true});
window.NexusOrganize={run,GROUPS};
})();
