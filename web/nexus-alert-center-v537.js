/* NEXUS 5.37 — central local de notificações de jogos, sem dados privados. */
(function(root){
'use strict';
const KEY='nexusHotAlertsV537';
const MAX=80,MAX_AGE=48*3600*1000;
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function clean(raw,now=Date.now()){
 if(!Array.isArray(raw))return [];
 const seen=new Set();
 return raw.filter(x=>{
  if(!x||typeof x!=='object'||!x.id||!x.match_id)return false;
  const at=Number(x.at);
  if(!Number.isFinite(at)||at>now+1000||now-at>MAX_AGE)return false;
  if(seen.has(x.id))return false;seen.add(x.id);return true;
 }).slice(0,MAX).map(x=>({
  id:String(x.id).slice(0,160),match_id:String(x.match_id).slice(0,90),
  title:String(x.title||'Jogo sob pressão').slice(0,115),
  message:String(x.message||'').slice(0,400),
  at:Number(x.at),read:x.read===true
 }));
}
function add(items,evt,now=Date.now()){
 if(!evt||typeof evt.match_id!=='string'||!evt.match_id)return clean(items,now);
 const id=evt.match_id+'|'+String(evt.kind||'pressure')+'|'+Math.floor(now/(8*60000));
 const newest={id,match_id:evt.match_id,title:evt.title,message:evt.message,at:now,read:false};
 return clean([newest,...items],now);
}
function read(storage){
 try{return clean(JSON.parse(storage.getItem(KEY)||'[]'))}catch(_){return []}
}
function save(storage,items){
 const safe=clean(items);
 try{storage.setItem(KEY,JSON.stringify(safe))}catch(_){}
 return safe;
}
function mark(items,id){return items.map(x=>({...x,read:x.id===id?true:x.read}));}
function render(items){
 const current=clean(items);
 const unread=current.filter(x=>!x.read).length;
 const content=current.length?current.map(x=>{
   const time=new Date(x.at).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',
    day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
   return '<button class="nexus-alert-entry '+(x.read?'read':'new')+'" type="button" '+
    'data-nexus-alert-id="'+esc(x.id)+'" data-nexus-match="'+esc(x.match_id)+'">'+
    '<strong>'+esc(x.title)+'</strong><small>'+esc(time)+'</small>'+
    '<span>'+esc(x.message)+'</span><em>ABRIR PARTIDA ↗</em></button>';
 }).join(''):'<p>Sem alertas de pressão recente nesta sessão. A central registra somente sinais esportivos emitidos pelo NEXUS.</p>';
 return {unread,html:content};
}
const api={clean,add,read,save,mark,render};
root.NexusNoticeHub=api;
if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
