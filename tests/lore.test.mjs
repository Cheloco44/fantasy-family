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
 robert:'Blue Hat — The Dodgers’ Most Animated Fan',
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
 assert.equal(robert.loreText,'The jokes stay on league chaos: especially the parade of new coaches he keeps adding instead of addressing the turnover. He also dislikes the commissioner with the focus of a man who has studied the rulebook purely to find new reasons to complain.');
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
