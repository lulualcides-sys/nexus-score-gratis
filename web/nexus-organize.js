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
/* Placar provável em destaque (previsão congelada ANTES do jogo). */
function probableScore(){
  const body=document.getElementById('detail-body');if(!body)return;
  const st=typeof state!=='undefined'?state:null;const d=st&&st.detail;
  const b=d&&d.pregame_baseline,f=b&&b.forecast;
  let box=body.querySelector('.nx-prob');
  const top=(f&&Array.isArray(f.top_scores)?f.top_scores:[]).filter(x=>x&&x.score&&Number.isFinite(+x.probability)).slice(0,3);
  if(!top.length||!f.one_x_two){if(box)box.remove();return;}
  const key=(d.id||'')+'|'+b.captured_at;
  if(box&&box.dataset.key===key)return;
  const p=f.one_x_two,esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const res=b.settlement&&b.settlement.score?` · terminou <b>${esc(b.settlement.score)}</b>`:'';
  const html=`<div class="nx-prob-head"><b>🎯 Placar mais provável</b><span>previsão feita antes do jogo${res}</span></div>
    <div class="nx-prob-scores">${top.map((x,i)=>`<div class="${i?'':'main'}"><strong>${esc(x.score.replace('-','–'))}</strong><small>${Math.round(+x.probability)}%</small></div>`).join('')}</div>
    <div class="nx-prob-1x2"><span>${esc(d.home||'Casa')} ${Math.round(+p.home)}%</span><span>Empate ${Math.round(+p.draw)}%</span><span>${esc(d.away||'Fora')} ${Math.round(+p.away)}%</span></div>
    <small class="nx-prob-note">Modelo experimental: no teste de 23/11 as casas de aposta acertaram mais. Use como referência, não como garantia.</small>`;
  if(!box){box=document.createElement('section');box.className='nx-prob';const ref=body.querySelector('.scout-main')||body.querySelector('.nx-pitch');if(ref)ref.after(box);else body.prepend(box);}
  box.innerHTML=html;box.dataset.key=key;
}
/* Aviso de escalação: titulares habituais (≥80% dos últimos jogos) fora do XI. */
function lineupAlert(){
  const body=document.getElementById('detail-body');if(!body)return;
  const st=typeof state!=='undefined'?state:null;const d=st&&st.detail;const r=d&&d.lineup_changes;
  let box=body.querySelector('.nx-lineup');
  const sides=r?['home','away'].map(s=>r[s]).filter(x=>x&&x.missing_count>=2):[];
  if(!sides.length){if(box)box.remove();return;}
  const key=(d.id||'')+JSON.stringify(sides.map(x=>x.missing));
  if(box&&box.dataset.key===key)return;
  const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const html=`<b>⚠️ Escalação diferente do habitual</b>`+sides.map(x=>`<p><strong>${esc(x.team)}</strong>: ${x.missing_count} titular${x.missing_count>1?'es':''} habitua${x.missing_count>1?'is':'l'} fora — ${x.missing.map(esc).join(', ')}${x.missing_count>x.missing.length?'…':''}</p>`).join('')+
    `<small>Habitual = titular em 80% ou mais dos últimos ${Math.max(...sides.map(x=>x.prior_games))} jogos. O motivo (lesão, suspensão, poupado) não é informado pela fonte.</small>`;
  if(!box){box=document.createElement('section');box.className='nx-lineup';const ref=body.querySelector('.nx-prob')||body.querySelector('.scout-main');if(ref)ref.after(box);else body.prepend(box);}
  box.innerHTML=html;box.dataset.key=key;
}
function run(){lineupAlert();probableScore();if(!document.body.classList.contains('nx-simple'))return;organizeCloud();organizeLab();}
let q=false;
new MutationObserver(()=>{if(q)return;q=true;requestAnimationFrame(()=>{q=false;run();});})
  .observe(document.documentElement,{childList:true,subtree:true});
window.NexusOrganize={run,GROUPS,probableScore,lineupAlert};
})();
