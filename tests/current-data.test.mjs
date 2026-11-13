import {test} from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';

test('current-result freshness never turns missing, invalid or future data into a live claim',async()=>{
 assert.ok(existsSync('src/lib/current-data.mjs'),'current-data helper must exist');
 const {freshness}=await import('../src/lib/current-data.mjs');
 const now=new Date('2026-11-13T12:00:00Z');
 assert.equal(freshness(null,now),'unavailable');
 assert.equal(freshness({mode:'demo',fetchedAt:'2026-11-13T11:00:00Z'},now),'unavailable');
 assert.equal(freshness({mode:'live',fetchedAt:'invalid'},now),'unavailable');
 assert.equal(freshness({mode:'live',fetchedAt:'2026-11-14T11:00:00Z'},now),'unavailable');
 assert.equal(freshness({mode:'live',fetchedAt:'2026-11-13T11:00:00Z'},now),'current');
 assert.equal(freshness({mode:'live',fetchedAt:'2026-11-12T12:00:00Z'},now),'stale');
 assert.equal(freshness({mode:'live',fetchedAt:'2026-11-12T11:00:00Z'},now),'stale');
});

test('score labels preserve category records, zero points and missing data distinctly',async()=>{
 const {scoreText}=await import('../src/lib/current-data.mjs');
 assert.equal(typeof scoreText,'function');
 assert.equal(scoreText({available:true,points:0},'H2H_POINTS'),'0');
 assert.equal(scoreText({available:false,points:null},'H2H_POINTS'),'Unavailable');
 assert.equal(scoreText({available:true,points:999,categoryRecord:{wins:3,losses:5,ties:2}},'H2H_CATEGORY'),'3–5–2');
 assert.equal(scoreText(null,'H2H_POINTS'),'BYE');
 assert.equal(scoreText({available:true,points:10},'UNKNOWN'),'Unavailable');
});

test('snapshot status supports the seven-AM pipeline without stale manual-only claims',()=>{
 const clubhouse=JSON.parse(readFileSync('src/data/clubhouse.json','utf8'));
 assert.equal(clubhouse.refreshTime,'07:00');
 const status=readFileSync('src/components/DataStatus.astro','utf8');
 assert.ok(status.includes('07:00'));
 assert.ok(status.includes('daily-clubhouse.yml'));
 assert.ok(!status.includes('No automatic score refresh is enabled'));
 assert.ok(!status.includes('DEMO DATA · Not actual daily results'));
 const board=readFileSync('src/components/CurrentLeague.astro','utf8');
 assert.ok(!board.includes('Manual ESPN snapshot'));
});

test('built scoreboard distinguishes verified snapshots from empty state',()=>{
 const snapshot=JSON.parse(readFileSync('src/data/current.json','utf8'));
 const html=readFileSync('dist/index.html','utf8');
 assert.ok(html.indexOf('The scoreboard.')>=0);
 assert.ok(!html.includes('recaps remain DEMO DATA'));
 assert.ok(html.includes('data-snapshot-time'));
 if(snapshot.mode==='live'){
  assert.equal(snapshot.teams.length,8);
  assert.equal(new Set(snapshot.teams.map(t=>t.id)).size,8);
  assert.ok(html.includes('ESPN SNAPSHOT'));
  assert.ok(html.includes('Full matchup totals, not daily scores'));
 }else{
  assert.equal(snapshot.teams.length,0);
  assert.equal(snapshot.matchups.length,0);
  assert.ok(!html.includes('class="matchup-card"'));
  assert.ok(html.includes('Not connected'));
 }
});
