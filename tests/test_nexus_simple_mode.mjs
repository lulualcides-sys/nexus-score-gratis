import assert from 'node:assert/strict';
import fs from 'node:fs';
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const css=fs.readFileSync(new URL('../web/nexus-simple.css',import.meta.url),'utf8');
const js=fs.readFileSync(new URL('../web/nexus-simple.js',import.meta.url),'utf8');
assert.match(html,/nexus-simple\.css/);assert.match(html,/nexus-simple\.js/);
assert.match(html,/indicator nx-tech">Pressão: analisar/);
for(const sel of ['.metric-grid','.nx-tech','nexus-coverage-','.match-scroll','.agenda-days'])assert.ok(css.includes(sel),sel);
assert.match(js,/localStorage/);assert.match(js,/Modo completo/);assert.match(js,/nx-filters/);
// modo completo deve continuar disponível e nada é removido do DOM, só escondido via classe
assert.doesNotMatch(js,/\.remove\(\)/);
new Function(js);
console.log('NEXUS modo simples: OK');
assert.match(css,/body\.nx-sheet \.detail-panel/);assert.match(js,/Voltar aos jogos/);assert.match(js,/matchMedia\('\(max-width:900px\)'\)/);
console.log('NEXUS detalhe em tela cheia no celular: OK');
