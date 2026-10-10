import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const src=fs.readFileSync(new URL('../web/nexus-activity.js',import.meta.url),'utf8');
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const root={PressureLab:{render:()=>'<section id="section-thermometer"><div id="signal-marker-info"></div></section>'}};
vm.runInNewContext(src,{window:root});
const data={activity_timeline:{basis:'confirmed_event_count',points:[
  {m:7,home:2,away:0,types:{shot_on:2}},
  {m:28,home:0,away:1,types:{shot_off:1}},
  {m:95,home:1,away:0,types:{goal:1}}
]}};
const visual=root.NexusActivity.renderActivity(data);
assert.match(visual,/ATIVIDADE OFENSIVA OBSERVADA/);
assert.match(visual,/3 minuto\(s\) registrado\(s\)/);
assert.match(visual,/90\+5/);
assert.match(visual,/não é pressão estimada/);
assert.match(visual,/nexus-activity-away/);
assert.match(root.PressureLab.render(data),/section-thermometer/);
assert.match(root.PressureLab.render(data),/ATIVIDADE OFENSIVA OBSERVADA/);
assert.equal(root.NexusActivity.renderActivity({}), '');
assert.equal(root.NexusActivity.renderActivity({activity_timeline:{basis:'confirmed_event_count',points:[
  {m:23,home:1,away:0,types:{shots_total:1}}
]}}),'');
const unsafe={activity_timeline:{basis:'confirmed_event_count',points:[
  {m:3,home:1,away:0,types:{shot_on:1,'<img src=x>':5}}
]}};
assert.doesNotMatch(root.NexusActivity.renderActivity(unsafe),/<img src=x>/);
assert.match(html,/src="\.\/nexus-activity\.js"/);
assert.match(html,/href="\.\/nexus-activity\.css"/);
console.log('NEXUS activity: eventos sem inferir pressao, compatibilidade web, markup OK');
