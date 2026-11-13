import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const data=JSON.parse(readFileSync('src/data/clubhouse.json','utf8'));
const expected=[
 ['marcelo','Marcelo','America’s FUPA','big guy strongman'],
 ['rich','Rich','District 9','old monkey or old man'],
 ['zach','Zach','June’s Half-Baked Quacks','half human half bug'],
 ['ben','Ben','The Goon Squad','blue hair guy with skinny legs'],
 ['jake','Jake','CAVE N1KGAR','caveman; has many different faces'],
 ['robert','IR BOB','Anti-Chel Warriors','older guy in a dodgers hat'],
 ['erik','Erik','Patel Pals','robot'],
 ['kyle','Kyle','Jive Turkey','young monkey or young guy in a jester hat'],
];
test('eight owner-supplied mappings are preserved without fabricated profile details',()=>{
 assert.equal(data.managers.length,expected.length);
 assert.deepEqual(data.managers.map(m=>[m.slug,m.alias,m.team,m.characterDescription]),expected);
 for(const m of data.managers){
  assert.equal(m.bio,null);
  assert.equal(m.scoutingReport,null);
  assert.equal(m.approved,true);
  assert.equal(m.espnTeamId,null);
  assert.equal(m.image,`avatars/${m.slug}.webp`);
 }
 assert.ok(data.memes.every(m=>m.manager===null),'Demo memes must not be attributed to actual managers');
});
