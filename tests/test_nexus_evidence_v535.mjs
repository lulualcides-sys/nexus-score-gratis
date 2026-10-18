import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';

const require=createRequire(import.meta.url);
const e=require('../web/nexus-evidence-v535.js');
const html=readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
assert.match(html,/nexus-evidence-v535\.css/);
assert.match(html,/nexus-evidence-v535\.js/);
assert.match(html,/id="cloud-load-more"/);
assert.match(html,/visible\.slice\(0,cloudVisibleLimit\)/);
assert.match(html,/Exibindo o último snapshot disponível/);
assert.match(html,/nexus-feed-freshness/);
assert.match(html,/box\.innerHTML=NexusEvidence\.auditHTML\(report\)/);
assert.match(html,/html=NexusEvidence\.alertHTML\(data\)/);
const market={market_evidence:{fixtures_with_frozen_forecast:7,
 fixtures_with_result:3,fixtures_with_verified_pregame_1x2:2,
 markets:[
 {market:'1x2',label:'Match Odds · 1X2',forecasts:7,with_price:2,
  theoretical_positive:1,settled:3,hits:2,misses:1,observed_hit_pct:66.7},
 {market:'btts',label:'Ambas marcam',forecasts:7,with_price:0,
  theoretical_positive:0,settled:3,hits:1,misses:2,observed_hit_pct:33.3}
 ]},quotes_registered:267,settled_paper:0,paper_profit_loss_brl:null,
 trades_verified:0,actual_net_pl_brl:null};
const display=e.auditHTML(market);
assert.match(display,/COTAÇÕES BRUTAS/);
assert.match(display,/267/);
assert.match(display,/PARTIDAS COM PRÉ-LIVE CONGELADO/);
assert.match(display,/2 acertos|Acertos/);
assert.match(display,/EV teórico positivo/);
assert.match(display,/NÃO representam 267 operações/);
assert.match(display,/Nenhuma entrada paper liquidada/);
assert.doesNotMatch(display,/R\$\s*0,00/);
assert.doesNotMatch(display,/EXECUÇÕES COM COMPROVANTE.*0/);
assert.doesNotMatch(display,/Trades executados/);
const prior=e.auditHTML({...market,market_evidence:null});
assert.match(prior,/não foi gerada pela coleta/);
assert.doesNotMatch(prior,/R\$\s*0,00/);
const withPaper=e.auditHTML({...market,settled_paper:2,paper_profit_loss_brl:-125.5});
assert.match(withPaper,/R\$\s*125,50/);

const signal={id:'s1',match_id:'g1',home:'Casa',away:'Fora',league:'Liga',
 rule:'pressão forte',minute:32,icon:'🔥',captured_at:'2026-10-17T19:00:00Z',
 outcomes:{'5':'sem_gol_confirmado','10':'gol_confirmado','15':'gol_confirmado'}};
const signal2={id:'s2',match_id:'g2',home:'Casa',away:'Fora',league:'Liga',
 rule:'scouts acumulados',minute:22,icon:'🎯',captured_at:'2026-10-17T19:00:00Z',
 outcomes:{'5':'pendente','10':'janela_incompleta','15':'indeterminado'}};
const evaluation={horizons:{'5':{observations:2,settled:1,hits:0,misses:1,
 pending:1,incomplete:0,unknown:0,rate_pct:0},
 '10':{observations:2,settled:1,hits:1,misses:0,
 pending:0,incomplete:1,unknown:0,rate_pct:100},
 '15':{observations:2,settled:1,hits:1,misses:0,
 pending:0,incomplete:0,unknown:1,rate_pct:100}}};
const data={signal_journal:{items:[signal,signal2]},
 signal_evaluation:evaluation,
 alerts:[{message:'Notificação antiga',created_at:'2026-10-10T12:00:00Z',
 category:'monitoramento'}]};
const slots=e.normalizeSummary(data.signal_evaluation,data.signal_journal);
assert.equal(slots['5'].rate_pct,0);
assert.equal(slots['10'].settled,1);
const alerts=e.alertHTML(data);
assert.match(alerts,/GOL ATÉ 5 MIN/);
assert.match(alerts,/GOL ATÉ 10 MIN/);
assert.match(alerts,/GOL ATÉ 15 MIN/);
assert.match(alerts,/GOL ATÉ 40 MIN/);
assert.match(alerts,/gol confirmado|Gol/);
assert.match(alerts,/Sem gol/);
assert.match(alerts,/Parcial|Pendente/);
assert.match(alerts,/outras 1 mensagens do radar/);
assert.doesNotMatch(alerts,/stake fixa R\$/i);
assert.doesNotMatch(alerts,/ROI didático/i);
assert.doesNotMatch(alerts,/P\/L simulado/);
const fallback=e.normalizeSummary(null,data.signal_journal);
assert.equal(fallback['5'].hits,0);
assert.equal(fallback['5'].misses,1);
assert.equal(fallback['10'].incomplete,1);
assert.match(e.auditHTML({quotes_registered:0,paper_profit_loss_brl:null}),/—/);
assert.doesNotMatch(e.alertHTML({signal_journal:{items:[{...signal,
 home:'<script>Malicioso</script>'}]}}),/<script>/);
for(const script of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)){
 if(script[1].trim())new vm.Script(script[1]);
}
console.log('NEXUS v535: auditoria sem lucro falso, mercado por resultado e alertas por janela OK');
