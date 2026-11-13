import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync('src/data/clubhouse.json','utf8'));
const titles={
 rich:'The Juice — The Comeback Victim',
 marcelo:'The Commissioner — The League’s Supreme Ruler',
 kyle:'The Young Monkey — The Self-Appointed GOAT',
 erik:'Auto Erik — The Banana-Powered Manager',
 ben:'Blue Hair — The Chaos-and-Quiet Specialist',
 zach:'The Bug — The Polite Assassin',
 robert:'IR BOB — The Dodgers’ Most Animated Fan',
 jake:'The Caveman — The Kings’ Unofficial Enforcer',
};
test('owner-supplied lore maps to the confirmed eight managers without becoming factual bios',()=>{
 assert.equal(data.managers.length,Object.keys(titles).length);
 for(const m of data.managers){
  assert.equal(m.loreTitle,titles[m.slug]);
  assert.equal(m.loreKind,'fictional-league-lore');
  assert.ok(typeof m.loreText==='string'&&m.loreText.length>100);
  assert.equal(m.bio,null);
  assert.equal(m.favoriteTeam,null);
  assert.equal(m.scoutingReport,null);
 }
 const robert=data.managers.find(m=>m.slug==='robert');
 assert.match(robert.loreText,/team moms/);
 assert.match(robert.loreText,/Team Anti-Commish/);
 assert.doesNotMatch(robert.loreText,/rulebook|reasons to complain/);
 const rich=data.managers.find(m=>m.slug==='rich');
 assert.match(rich.loreText,/roid rage/);
 assert.match(rich.loreText,/house visit/);
 assert.doesNotMatch(rich.loreText,/rumors are completely made up|Allegedly/);
 const ben=data.managers.find(m=>m.slug==='ben');
 assert.match(ben.loreText,/anything doesn’t go his way/);
 assert.doesNotMatch(ben.loreText,/MMA|bets on|bet loses/);
 const kyle=data.managers.find(m=>m.slug==='kyle');
 assert.match(kyle.loreText,/return fire/);
 assert.match(kyle.loreText,/AI’s fault/);
 assert.doesNotMatch(kyle.loreText,/acts shocked|favorite expert/);
});
test('built profiles and directory disclose fiction, not real allegations or attributed quotes',()=>{
 const directory=readFileSync('dist/managers/index.html','utf8');
 assert.ok(directory.includes('FICTIONAL LEAGUE LORE'));
 for(const m of data.managers){
  const html=readFileSync(`dist/managers/${m.slug}/index.html`,'utf8');
  assert.ok(html.includes('FICTIONAL LEAGUE LORE'),m.slug);
  assert.ok(html.includes('exaggerated banter'),m.slug);
 }
});
