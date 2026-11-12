import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const data=JSON.parse(readFileSync('src/data/clubhouse.json','utf8'));
const expected=[
 ['marcelo','Marcelo','Americas fupa','big guy strongman'],
 ['rich','rich','district 9','old monkey or old man'],
 ['zach','zach','junes half baked qaks','half human half bug'],
 ['ben','ben','good squad','blue hair guy with skinny legs'],
 ['jake','jake','can nikgar','caveman; has many different faces'],
 ['robert','robert','anti chel warriors','older guy in a dodgers hat'],
 ['erik','ERIK','pash patels','robot'],
 ['kyle','kyle','Team Jive turkey','young monkey or young guy in a jester hat'],
];
test('eight owner-supplied mappings are preserved without fabricated profile details',()=>{
 assert.equal(data.managers.length,expected.length);
 assert.deepEqual(data.managers.map(m=>[m.slug,m.alias,m.team,m.characterDescription]),expected);
 for(const m of data.managers){
  assert.equal(m.bio,null);
  assert.equal(m.scoutingReport,null);
  assert.equal(m.approved,false);
  assert.equal(m.espnTeamId,null);
  assert.equal(m.image,null);
 }
 assert.ok(data.memes.every(m=>m.manager===null),'Demo memes must not be attributed to actual managers');
});
