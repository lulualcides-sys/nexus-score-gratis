/* NEXUS: linha de eventos confirmados, NAO substitui curva de pressao.
   Os graficos mostram somente minutos em que a fonte registrou lances. */
(function(root){
  'use strict';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function validate(raw){
    if(!raw||raw.basis!=='confirmed_event_count'||!Array.isArray(raw.points))return [];
    const byMinute=new Map();
    for(const item of raw.points){
      const m=Number(item?.m),home=Number(item?.home),away=Number(item?.away);
      if(!Number.isInteger(m)||m<0||m>130||!Number.isInteger(home)||
         !Number.isInteger(away)||home<0||away<0||home+away===0||home+away>100)continue;
      const types=item?.types&&typeof item.types==='object'&&!Array.isArray(item.types)?item.types:{};
      const known=['goal','shot_on','shot_off','big_chance_missed','penalty_missed'];
      let count=0;
      for(const kind of known){
        const number=Number(types[kind]);
        if(Number.isInteger(number)&&number>0&&number<=100)count+=number;
      }
      if(count!==home+away)continue;
      byMinute.set(m,{m,home,away,types});
    }
    return [...byMinute.values()].sort((a,b)=>a.m-b.m).slice(0,130);
  }
  function renderActivity(d){
    const events=validate(d?.activity_timeline);
    if(!events.length)return '';
    const bounds={left:28,right:897,top:12,baseline:90,bottom:167};
    const x=m=>bounds.left+Math.min(90,m)*((bounds.right-bounds.left-24)/90)+(m>90?Math.min(22,(m-90)*1.2):0);
    const max=Math.max(1,...events.map(p=>Math.max(p.home,p.away)));
    const factor=61/max;
    const bars=events.map(p=>{
      const xx=x(p.m),a=Math.max(0,p.home*factor),b=Math.max(0,p.away*factor);
      const label=p.m>90?"90+"+(p.m-90):String(p.m);
      const types=Object.entries(p.types).map(([k,v])=>k+': '+v).join(' · ');
      return (a?'<rect class="nexus-activity-home" x="'+xx.toFixed(1)+'" y="'+(90-a).toFixed(1)+'" width="6" height="'+a.toFixed(1)+'"><title>'+esc(label+' min · mandante '+p.home+' evento(s) · '+types)+'</title></rect>':'')+
      (b?'<rect class="nexus-activity-away" x="'+xx.toFixed(1)+'" y="90" width="6" height="'+b.toFixed(1)+'"><title>'+esc(label+' min · visitante '+p.away+' evento(s) · '+types)+'</title></rect>':'');
    }).join('');
    const ticks=[0,15,30,45,60,75,90].map(m=>
      '<text x="'+x(m).toFixed(1)+'" y="166" text-anchor="middle">'+m+"′"+'</text>').join('');
    const count=events.reduce((sum,p)=>sum+p.home+p.away,0);
    return '<section class="nexus-activity" aria-label="Atividade ofensiva por eventos confirmados">'+
      '<div class="nexus-activity-head"><b>● ATIVIDADE OFENSIVA OBSERVADA</b>'+
      '<span>'+count+' evento(s) · '+events.length+' minuto(s) registrado(s)</span></div>'+
      '<p>Chutes, gols, grandes chances perdidas e pênaltis perdidos com minuto confirmado. Contagem por minuto — <strong>não é pressão estimada nem probabilidade de gol.</strong></p>'+
      '<div class="nexus-activity-legend"><span>Mandante acima</span><span>Visitante abaixo</span></div>'+
      '<svg viewBox="0 0 930 175" role="img" aria-label="Eventos confirmados por minuto; barras acima mandante e abaixo visitante, sem interpolação">'+
      '<line x1="22" y1="90" x2="919" y2="90" stroke="#69849a" stroke-dasharray="3 5"/>'+
      '<line x1="'+x(45)+'" y1="12" x2="'+x(45)+'" y2="154" stroke="#61798c" stroke-dasharray="2 4"/>'+
      bars+'<g class="nexus-activity-ticks">'+ticks+'</g></svg>'+
      '<small>Sem barra = nenhum evento individual reportado nesse minuto; não comprova ausência de ataque. Dados derivados de lances, separados do momentum fornecido pela fonte.</small>'+
      '</section>';
  }
  const lab=root?.PressureLab;
  if(lab&&typeof lab.render==='function'&&!lab.__nexusActivityWrapped){
    const oldRender=lab.render;
    lab.render=function(d,scope){
      const html=oldRender.apply(this,arguments),addition=renderActivity(d);
      if(!addition)return html;
      const anchor='<div id="signal-marker-info"';
      return html.includes(anchor)?html.replace(anchor,addition+anchor):
        html.replace('</section>',addition+'</section>');
    };
    lab.__nexusActivityWrapped=true;
  }
  root.NexusActivity={validate,renderActivity};
})(typeof window!=='undefined'?window:{});
