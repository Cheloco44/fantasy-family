import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
const labels={1:"America’s FUPA",2:'District 9',3:'June’s Half-Baked Quacks',4:'The Goon Squad',5:'Cave Kings',6:'Anti-Chel Warriors',7:'Patel Pals',8:'Jive Turkey'};
test('owner-requested polished team labels are separate from provider source names',async()=>{
 assert.ok(existsSync('src/lib/team-names.mjs'),'presentation name helper is missing');
 const {teamLabel}=await import('../src/lib/team-names.mjs');
 const editorial=JSON.parse(readFileSync('src/data/editorial.json','utf8'));
 const clubhouse=JSON.parse(readFileSync('src/data/clubhouse.json','utf8'));
 for(const [id,label] of Object.entries(labels)){
  assert.equal(teamLabel(Number(id),editorial.cast),label);
  const profile=clubhouse.managers.find(m=>m.slug===editorial.cast[id].slug);
  assert.equal(profile.team,label);
 }
 assert.equal(teamLabel(99,editorial.cast),'Team 99');
 assert.equal(teamLabel(null,editorial.cast),'Team unavailable');
 const source=JSON.parse(readFileSync('src/data/current.json','utf8'));
 const before=JSON.stringify(source);
 for(const team of source.teams) teamLabel(team.id,editorial.cast);
 assert.equal(JSON.stringify(source),before,'display labeling must not mutate canonical provider data');
});
