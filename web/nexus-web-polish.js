/* NEXUS Web refinamento das abas. Dados reais e etiquetas de proveniência.
   Sobrescreve apenas projeção e confronto da interface original (sem tocar no motor).
*/
(function(){
'use strict';
const E=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const N=x=>x!=null&&x!==''&&Number.isFinite(Number(x))?Number(x):null;
const P=x=>N(x)==null?'—':N(x).toFixed(1).replace('.',',')+'%';
const cap=x=>Math.max(0,Math.min(100,N(x)||0));
const pctbar=(label,amount,type='home')=>{
 const v=N(amount);
 return '<div class="nexus-prob-row"><div class="nexus-prob-label"><span>'+E(label)+'</span><strong>'+
   (v===null?'—':P(v))+'</strong></div><div class="nexus-prob-track">'+
   (v===null?'':'<i class="nexus-prob-fill '+type+'" style="width:'+cap(v)+'%"></i>')+
   '</div></div>';
};
const card=(title,value,subtitle='')=>
 '<div class="nexus-insight"><span>'+E(title)+'</span><b>'+E(value)+'</b><em>'+E(subtitle)+'</em></div>';
const panel=(title,subtitle,body,cls)=>'<section class="'+cls+'" aria-label="'+E(title)+'">'+
  '<header class="nexus-analysis-top"><h3>'+E(title)+'</h3><small>'+E(subtitle)+'</small></header>'+body+'</section>';
const sample=f=>f&&N(f.n)!=null?N(f.n):f&&N(f.available)!=null?N(f.available):0;
function formBlock(name,form){
 if(!form)return '<div class="nexus-team-form"><h4>'+E(name)+'</h4><div class="nexus-empty">A fonte ainda não informou resultados anteriores verificáveis.</div></div>';
 const played=sample(form),games=(form.recent||form.games||[]).slice(0,10);
 let wins=N(form.wins),draws=N(form.draws),losses=N(form.losses);
 if(wins==null)wins=games.filter(g=>g.result==='V').length;
 if(draws==null)draws=games.filter(g=>g.result==='E').length;
 if(losses==null)losses=games.filter(g=>g.result==='D').length;
 const meanF=N(form.avg_goals_for)??N(form.gf);
 const meanA=N(form.avg_goals_against)??N(form.ga);
 const aver=(sum)=>played?Math.round(sum/played*100)/100:null;
 return '<div class="nexus-team-form"><h4>'+E(name)+'</h4><small>'+
 E(played)+' de 10 jogos anteriores encontrados</small>'+
 '<div class="nexus-form-badges"><b class="w">'+wins+' V</b><b class="d">'+draws+
 ' E</b><b class="l">'+losses+' D</b></div>'+
 '<div class="nexus-compare-item"><span>Média de gols marcados</span><b>'+E(meanF===null?'—':meanF.toFixed(2))+'</b></div>'+
 '<div class="nexus-compare-item"><span>Média de gols sofridos</span><b>'+E(meanA===null?'—':meanA.toFixed(2))+'</b></div>'+
 '<div class="nexus-compare-item"><span>Over 2.5 nos jogos</span><b>'+
 (N(form.over25_pct)!=null?P(form.over25_pct):games.length?P(games.filter(g=>N(g.gf)!=null&&N(g.ga)!=null&&N(g.gf)+N(g.ga)>=3).length/games.length*100):'—')+
 '</b></div><div class="nexus-compare-item"><span>Ambas marcam (BTTS)</span><b>'+
 (N(form.btts_pct)!=null?P(form.btts_pct):games.length?P(games.filter(g=>N(g.gf)>0&&N(g.ga)>0).length/games.length*100):'—')+
 '</b></div>'+
 (games.length?'<div class="nexus-section-title">Sequência recente</div><div class="nexus-form-badges">'+
  games.slice(0,10).map(g=>'<b class="'+(g.result==='V'?'w':g.result==='E'?'d':'l')+
  '" title="'+E(g.opponent||'')+'">'+E(g.result||'—')+'</b>').join('')+
  '</div>':'')+'</div>';
}
function projection(d,p){
 const pre=p||d?.prelive||{};
 const f=pre.forecast||null, goals=f?.expected_goals||{};
 const finished=d.phase==='finished',live=d.phase==='live';
 const recorded=d.pregame_baseline?.forecast?.expected_goals;
 const stamp=d.pregame_baseline?.captured_at||'';
 const before=Number.isFinite(Date.parse(stamp))&&Number.isFinite(Number(d.start_timestamp))?
    Date.parse(stamp)<Number(d.start_timestamp)*1000:false;
 const stored=!!recorded&&before;
 // Resultados históricos consultados depois do confronto não são previsões pré-jogo registradas.
 const classif=stored?'Projeção registrada antes do jogo':
   finished?'Simulação retrospectiva, NÃO previsão pré-jogo':
   live?'Modelo histórico ilustrativo · partida em andamento':
   'Modelo Poisson experimental · sem calibração';
 const nH=sample(pre.sample?.home),nA=sample(pre.sample?.away);
 const x=Number(goals.home),y=Number(goals.away);
 const valid=pre.available&&f&&goals.home!=null&&goals.away!=null&&Number.isFinite(x)&&Number.isFinite(y)&&x>=0&&y>=0;
 const statsH=d.stats?.home||{},statsA=d.stats?.away||{};
 const score=d.home_score!=null&&d.away_score!=null?String(d.home_score)+'–'+String(d.away_score):'—';
 let html='<div class="nexus-note"><b>'+E(classif)+'.</b> '+E(finished?
 'O NEXUS não conta esta simulação como acerto ou lucro; médias anteriores podem ter sido consultadas após a partida.':
 'Probabilidades teóricas, não calibradas por backtest. EV+ depende também de cotação válida e teste histórico.')+'</div>';
 if(valid){
   const pr=f.one_x_two||{};
   html+='<div class="nexus-section-title">Probabilidades de resultado · Match Odds</div>'+
      pctbar(d.home+' vence',pr.home,'home')+pctbar('Empate',pr.draw,'draw')+
      pctbar(d.away+' vence',pr.away,'away');
   const total=x+y;
   html+='<div class="nexus-insight-grid">'+
     card('Gols esperados · mandante',x.toFixed(2),'modelo histórico')+
     card('Gols esperados · visitante',y.toFixed(2),'modelo histórico')+
     card('Total esperado',total.toFixed(2),'Poisson independente')+'</div>';
   const over=N(f.over_2_5_pct),btts=N(f.btts_yes_pct);
   html+='<div class="nexus-section-title">Mercados de gols · cenário teórico</div>'+
     pctbar('Over 2.5 FT',over)+pctbar('Under 2.5 FT',over===null?null:100-over,'away')+
     pctbar('Ambas marcam · SIM',btts)+pctbar('Ambas marcam · NÃO',btts===null?null:100-btts,'away');
   const top=(f.top_scores||[]).slice(0,5).filter(g=>g&&g.score);
   if(top.length){
      html+='<div class="nexus-section-title">Placares com maior probabilidade no modelo</div>'+
       '<div class="nexus-scores">'+top.map(g=>'<div class="nexus-score"><b>'+
       E(g.score)+'</b><span>'+P(g.probability)+'</span></div>').join('')+'</div>';
   }
   const segments=f.periods||{};
   for(const [key,title] of [['first','1º tempo'],['second','2º tempo']]){
     const rows=(segments[key]||[]).filter(r=>N(r.value)!==null);
     if(!rows.length)continue;
     html+='<div class="nexus-section-title">'+title+'</div>'+
       rows.slice(0,4).map(v=>pctbar(v.label,v.value)).join('');
   }
 }else{
   html+='<div class="nexus-empty">'+E(pre.reason||
    'Amostra insuficiente dos dois times para estimar probabilidades pelo modelo Poisson original.')+'</div>';
 }
 html+='<div class="nexus-section-title">Forma esportiva que embasa a análise</div>'+
 '<div class="nexus-team-compare">'+formBlock(d.home,pre.sample?.home)+
 formBlock(d.away,pre.sample?.away)+'</div>';
 if(finished){
   html+='<div class="nexus-section-title">Resultado observado · não é previsão</div>'+
    '<div class="nexus-insight-grid">'+card('Placar final',score,'resultado verificado')+
    card('xG observado',statsH.xg!=null&&statsA.xg!=null?statsH.xg+' × '+statsA.xg:'—','apenas se informado')+
    card('Finalizações no alvo',statsH.shots_on!=null&&statsA.shots_on!=null?
      statsH.shots_on+' × '+statsA.shots_on:'—','scouts reais')+'</div>';
 }
 html+='<p class="nexus-note">Fonte: '+E(pre.source||d.source||'fontes conectadas')+
  '. Apenas médias e resultados efetivamente disponíveis; estas estimativas não estabelecem rentabilidade nem recomendam entrada.</p>';
 return panel('NEXUS · Projeções e mercados',classif,html,'nexus-projection');
}
function confrontation(d){
 const p=d.prelive||{};
 const data=Array.isArray(d.head_to_head)?d.head_to_head:[];
 const valid=data.filter(g=>g&&/^\d{1,2}[-–]\d{1,2}$/.test(String(g.score||''))).slice(0,20);
 const normalize=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\b(?:fc|sc|ec|de|da|do|clube)\b/g,'').replace(/[^a-z0-9]+/g,' ').trim();
 let h=0,a=0,draw=0;
 const rows=[],seen=new Set();
 for(const g of valid){
   const direct=normalize(g.home)===normalize(d.home)&&normalize(g.away)===normalize(d.away);
   const rev=normalize(g.home)===normalize(d.away)&&normalize(g.away)===normalize(d.home);
   if(!direct&&!rev)continue;
   const key=String(g.date||g.at||'')+':'+normalize(g.home)+':'+normalize(g.away)+':'+g.score;
   if(seen.has(key))continue;seen.add(key);
   const [hg,ag]=String(g.score).split(/[-–]/).map(Number);
   if(hg===ag)draw++;else if((direct&&hg>ag)||(rev&&ag>hg))h++;else a++;
   rows.push(g);
 }
 const total=h+a+draw;
 let result='<div class="nexus-note">Confronto direto e forma recente são análises diferentes. Usamos apenas partidas passadas reconhecidas pela fonte, sem inventar resultados ou contar jogos futuros.</div>';
 result+='<div class="nexus-section-title">Histórico direto · '+total+' partidas verificadas</div>';
 if(total){
   result+='<div class="nexus-insight-grid">'+
     card('Vitórias · '+d.home,h,'dos duelos')+card('Empates',draw,'dos duelos')+
     card('Vitórias · '+d.away,a,'dos duelos')+'</div>'+
     '<div class="nexus-h2h-result"><i class="h" style="width:'+(100*h/total)+'%"></i>'+
     '<i class="d" style="width:'+(100*draw/total)+'%"></i>'+
     '<i class="a" style="width:'+(100*a/total)+'%"></i></div>'+
     '<div class="nexus-h2h-list">'+rows.map(g=>
       '<div class="nexus-h2h-row"><span>'+E(g.date||'')+'</span><span>'+E(g.home)+
       ' × '+E(g.away)+'</span><b>'+E(g.score)+'</b></div>').join('')+'</div>';
 }else result+='<div class="nexus-empty">Nenhum confronto direto confiável foi localizado entre esses dois clubes nos históricos conectados. Abaixo estão os resultados recentes de cada equipe, que não equivalem a confrontos diretos.</div>';
 if(total){
  const scores=rows.map(g=>String(g.score).split(/[-–]/).map(Number));
  const goals=scores.reduce((n,p)=>n+p[0]+p[1],0);
  const over=scores.filter(p=>p[0]+p[1]>=3).length;
  const btts=scores.filter(p=>p[0]>0&&p[1]>0).length;
  const pct=n=>(100*n/total).toFixed(1).replace('.',',')+'%';
  const providers=[...new Set(rows.map(g=>String(g.source||'Histórico').trim()).filter(Boolean))];
  result+='<div class="nexus-section-title">Estatísticas dos confrontos reais</div>'+
     '<div class="nexus-h2h-metrics">'+
     card('Gols por jogo',(goals/total).toFixed(2),'média · '+total+' jogos')+
     card('Over 2,5',pct(over),over+' de '+total+' jogos')+
     card('Ambas marcam',pct(btts),btts+' de '+total+' jogos')+
     card('Vitórias · '+d.home,pct(h),h+' de '+total+' jogos')+
     '</div><p class="nexus-h2h-source">Fontes: '+E(providers.join(' + '))+
     ' · somente confrontos passados verificados · não é EV+.</p>';
 }
 result+='<div class="nexus-section-title">Comparativo dos últimos dez jogos disponíveis</div>'+
 '<div class="nexus-team-compare">'+formBlock(d.home,p.sample?.home)+
 formBlock(d.away,p.sample?.away)+'</div>';
 const home=p.sample?.home,away=p.sample?.away;
 if(sample(home)>0&&sample(away)>0){
    const homeGF=N(home.gf)??N(home.avg_goals_for);
    const awayGF=N(away.gf)??N(away.avg_goals_for);
    if(homeGF!==null&&awayGF!==null){
     result+='<div class="nexus-section-title">Comparação ofensiva descritiva</div>'+
      '<div class="nexus-insight-grid">'+
       card('Média de gols · '+d.home,homeGF.toFixed(2),sample(home)+' partidas')+
       card('Média de gols · '+d.away,awayGF.toFixed(2),sample(away)+' partidas')+
       card('Diferença entre médias',Math.abs(homeGF-awayGF).toFixed(2),
          homeGF>awayGF?d.home:awayGF>homeGF?d.away:'Empate')+'</div>';
    }
 }
 result+='<p class="nexus-note">Os dados de forma são relativos aos jogos anteriores encontrados. Os confrontos são identificados por equipes, placares e datas, evitando duplicações. Uma vantagem histórica não representa EV+ validado.</p>';
 return panel('NEXUS · Confronto completo','H2H + forma + gols',result,'nexus-comparison');
}
if(typeof window!=='undefined'){
 window.comparisonProjection56=(d)=>projection(d,d?.prelive);
 window.preliveProjectionV5=(p,d)=>projection(d,p);
 window.headToHeadHTML=confrontation;
 window.NexusWebPolish={projection,confrontation};
}
})();