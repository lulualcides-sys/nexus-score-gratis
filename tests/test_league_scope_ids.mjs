// Regressão: filtro de ligas por ID canônico FotMob (primaryId), não só por nome.
// Casos reais do histórico 18/10–18/11/2026 (Gana, Série A BR, Femenil, Liga Portugal 2...).
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const c=require('../web/nexus-league-coverage.js');
const done=(league,league_id,extra={})=>({league,league_id,phase:'finished',score:'1-0',home:'A',away:'B',source:'FotMob',...extra});

// 1. Mesmo nome, países diferentes: só o ID oficial decide.
assert.equal(c.profile('Premier League','47')?.id,'premier');
for(const id of ['522','263','441','63','9066','116','529','118','262','519'])
  assert.equal(c.profile('Premier League',id)?.tier==='main',false,'Premier League '+id+' não é a inglesa');
assert.equal(c.profile('Premier League','63')?.id,'russia');
assert.equal(c.profile('Premier League','441')?.id,'ukraine');
assert.equal(c.profile('Ligue 1','516'),null);
assert.equal(c.profile('Bundesliga','38')?.id,'austria');
assert.equal(c.profile('Bundesliga','54')?.id,'bundesliga');
assert.equal(c.profile('Championship','123'),null);
assert.equal(c.profile('CAF Champions League Qualification','10619'),null);

// 2. Brasileirão não pode virar Serie A italiana; Série B não pode sumir.
assert.equal(c.profile('Série A','268')?.id,'br_a');
assert.equal(c.profile('Série A')?.id,'br_a','acento FotMob = Brasil');
assert.equal(c.profile('Série B','8814')?.id,'br_b');
assert.equal(c.profile('Série B')?.id,'br_b');
assert.equal(c.profile('Serie A','55')?.id,'italy');

// 3. Feminino, base e segunda divisão não entram como liga principal.
const initial=c.getScope();
c.setScope('main');
for(const [n,id] of [['Liga MX Femenil Apertura','9906'],['Eredivisie Vrouwen',''],['Liga Portugal 2','185'],
  ['Premier League U18','10068'],['Premier League 2','9084']]){
  assert.equal(c.category(n,id),false,n);
  assert.equal(c.visible(done(n,id)),false,n);
}
c.setScope('all');
assert.equal(c.visible(done('Liga Portugal 2','185')),true,'em "todas" aparece, rotulada como ela mesma');
assert.equal(c.visible(done('Liga MX Femenil Apertura','9906')),false,'feminino nunca');
c.setScope(initial);
assert.equal(c.profile('Liga Portugal 2'),null);
assert.equal(c.profile('Premier League U18'),null);
assert.equal(c.womenGame({league:'Liga MX Femenil Apertura'}),true);
assert.equal(c.womenGame({league:'Eredivisie Vrouwen'}),true);

// 4. Escopo ampliado e "todas".
const friendly=done('Friendlies','114',{home:'Singapore',away:'Brazil'});
const minor=done('Segunda Federacion - Group 3','9138');
const women=done('Liga F','9907');
assert.equal(c.category('Friendlies','114'),false,'amistoso não é liga principal');
assert.equal(c.profile('Friendlies','114')?.tier,'extended');
const before=c.getScope();
c.setScope('main');
assert.equal(c.visible(friendly),false);
assert.equal(c.visible(done('Premier League','47')),true);
assert.equal(c.visible(done('Premier League','522')),false);
c.setScope('extended');
assert.equal(c.visible(friendly),true);
assert.equal(c.visible(minor),false);
c.setScope('all');
assert.equal(c.visible(minor),true);
assert.equal(c.visible(women),false,'feminino continua fora');
for(const n of ['Friendlies U21','Premier League U18','UEFA Youth League','MLS Next Pro','Serie A Primavera'])
  assert.equal(c.visible(done(n,'1')),false,n+' (base) fora');
assert.throws(()=>c.setScope('xyz'));
c.setScope(before);
assert.equal(c.getScope(),'all','padrão = todas as competições masculinas');

// 5. Estatística por liga usa ID e agrupa "Outras" no modo todas.
c.setScope('all');
const stats=c.leagueStats([done('Premier League','47'),done('Premier League','522'),friendly,minor]);
c.setScope(before);
const ids=stats.map(x=>x.league);
assert.ok(ids.includes('premier')&&ids.includes('friendlies')&&ids.includes('other'));
assert.equal(stats.find(x=>x.league==='premier').total,1,'Gana não conta como Premier League');

// 6. Linhas ESPN (código de liga) continuam aceitas sem ID FotMob.
assert.equal(c.profile('eng.1')?.id,'premier');
assert.equal(c.visible(done('usa.1',undefined,{source:'ESPN'})),true);
console.log('league scope ids: ok');
