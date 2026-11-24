import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const P=createRequire(import.meta.url)('../web/nexus-pitch.js');
const pts=v=>[...Array(6)].map((_,i)=>({m:60+i,v}));
assert.equal(P.tilt(pts(0)).level,'equilibrado');
const h=P.tilt(pts(70));assert.equal(h.side,'home');assert.equal(h.level,'forte');assert.ok(h.x>75&&h.x<=88);
const a=P.tilt(pts(-35));assert.equal(a.side,'away');assert.equal(a.level,'moderada');assert.ok(a.x<50);
assert.equal(P.tilt(pts(10).slice(0,2)),null,'pouca amostra não desenha');
console.log('NEXUS mapa ao vivo: OK');
