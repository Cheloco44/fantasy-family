import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const data = JSON.parse(readFileSync('src/data/clubhouse.json', 'utf8'));
const recaps = JSON.parse(readFileSync('src/data/recaps.json', 'utf8'));
const editorial = JSON.parse(readFileSync('src/data/editorial.json', 'utf8'));
const html = path => readFileSync(`dist/${path}`, 'utf8');
const escaped = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');

test('profiles, actual daily archive, sample and filterable locker build as distinct routes', () => {
  for (const path of ['managers/index.html', ...data.managers.map(m => `managers/${m.slug}/index.html`), 'memes/index.html', 'recaps/index.html', 'recaps/sample/index.html', ...recaps.editions.map(e => `recaps/${e.date}/index.html`)]) assert.ok(existsSync(`dist/${path}`), path);
  assert.ok(html('recaps/sample/index.html').includes('DEMO DATA'), 'sample stays explicitly demo');
  const gallery = html('memes/index.html');
  for (const marker of ['id="tag-filter"', 'id="manager-filter"', 'id="meme-search"', 'aria-live="polite"', 'name="manager"', 'DEMO ARTWORK · UNASSIGNED', 'OWNER-APPROVED ARTWORK']) assert.ok(gallery.includes(marker), marker);
  assert.equal((gallery.match(/class="meme"/g) || []).length, editorial.approvedMemes.length + data.memes.length);
  for (const meme of editorial.approvedMemes) assert.ok(gallery.includes(escaped(meme.caption)), meme.id);
});

test('clubhouse leads with the actual latest daily round rather than global demo claims', () => {
  const page = html('index.html');
  const current = JSON.parse(readFileSync('src/data/current.json', 'utf8'));
  const statusText = current.mode === 'live' ? ['ESPN snapshot', 'Last successful results fetch'] : ['No successful ESPN results refresh', 'Not connected'];
  for (const text of ['Redlands Possum Busters', '07:00', 'America/Phoenix', ...statusText]) assert.ok(page.includes(text), text);
  assert.ok(!page.includes('recaps remain DEMO'));
  assert.ok(!page.includes('espn_s2'));
  if (recaps.editions.length) {
    assert.ok(page.includes(escaped(recaps.editions[0].headline)));
    assert.ok(page.includes(`data-recap-date="${recaps.editions[0].date}"`));
    assert.ok(page.includes('data-recap-stale'));
  }
});

test('date editions retain scores, stories and source evidence without per-card bookkeeping', () => {
  for (const edition of recaps.editions) {
    const page = html(`recaps/${edition.date}/index.html`);
    assert.ok(page.includes(escaped(edition.headline)));
    assert.ok(page.includes(escaped(edition.coverageNote)));
    assert.ok(page.includes(`datetime="${edition.sourceFetchedAt}"`));
    assert.ok(page.includes('DAILY ROUND'));
    assert.ok(!page.includes('UNDATED SAMPLE'));
    assert.equal((page.match(/class="daily-round"/g) || []).length, edition.matchups.length);
    for (const matchup of edition.matchups) {
      for (const text of [matchup.homeAlias, matchup.awayAlias, matchup.title, matchup.story]) assert.ok(page.includes(escaped(text)), text);
      for (const note of matchup.trendNotes) assert.ok(!page.includes(escaped(note)), 'thin-history notes stay in the source payload');
      for (const points of [matchup.homePoints, matchup.awayPoints]) assert.ok(page.includes(`>${points ?? 'Unavailable'}</strong>`));
      if (matchup.weeklySummary) assert.ok(!page.includes(escaped(matchup.weeklySummary)), 'weekly diagnostics stay in the source payload');
    }
  }
});

test('recap reading flow keeps methodology in one closed native Data details at the bottom', () => {
  const paths = ['index.html', 'recaps/index.html', ...recaps.editions.map(e => `recaps/${e.date}/index.html`)];
  for (const path of paths) {
    const page = html(path);
    const panels = [...page.matchAll(/<details\b([^>]*)>([\s\S]*?)<\/details>/g)];
    assert.equal(panels.length, 1, `${path}: one native disclosure`);
    assert.doesNotMatch(panels[0][1], /\bopen(?:\s|=|$)/, 'closed by default');
    assert.match(panels[0][2], /<summary[^>]*>Data details<\/summary>/);
    const reading = page.replace(/<details\b[^>]*>[\s\S]*?<\/details>/g, '');
    assert.doesNotMatch(reading, /statsOfficial|Scoring period|matchup period|What the receipts prove|The receipts|Rivalry notebook|Separate weekly context|coverage 1\/7/);
    if (path.startsWith('recaps/') && path !== 'recaps/index.html') {
      assert.ok(page.indexOf('<details') > page.lastIndexOf('class="daily-round"'), 'disclosure follows the rounds');
      assert.ok(panels[0][2].includes(escaped(recaps.editions.find(e => path.includes(e.date)).coverageNote)));
    }
    const prose = page.replace(/<[^>]*>/g, ' ');
    assert.doesNotMatch(prose, /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/, 'no raw ISO timestamp in body prose');
  }
  const home = html('index.html');
  assert.doesNotMatch(home, /coverage 1\/7|verified DAILY ROUNDS|Rivalry notebook|Separate weekly context/);
  for (const edition of recaps.editions) {
    for (const matchup of edition.matchups) {
      assert.ok(Array.isArray(matchup.trendNotes), 'history evidence remains in source');
      assert.ok(Object.hasOwn(matchup, 'weeklySummary'), 'weekly evidence remains in source');
    }
  }
});

test('all rendered image paths are local and resolve to actual built assets', () => {
  for (const path of ['index.html', 'memes/index.html', 'recaps/index.html', ...recaps.editions.map(e => `recaps/${e.date}/index.html`)]) {
    for (const [, src] of html(path).matchAll(/<img\b[^>]*\bsrc="([^"]+)"/g)) {
      assert.ok(!src.includes('..') && !src.includes('://'), src);
      const local = src.replace(/^\/fantasy-family\//, '').replace(/^\//, '');
      assert.ok(existsSync(`dist/${local}`), `${path}: ${src}`);
    }
  }
});
