import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const read = file => JSON.parse(readFileSync(file, 'utf8'));

test('only curated, approved, valid local archive images enter the daily pool', async () => {
  const mod = await import('../src/lib/archive-pick.mjs');
  assert.equal(typeof mod.buildArchivePool, 'function', 'approval-gated archive pool must exist');
  const curated = ['old', 'pending', 'dated', 'remote', 'unlisted'].map(memeId => ({ memeId, title: 'Old joke', description: 'Scene', joke: 'Punchline' }));
  const memes = [
    { id: 'old', approvalStatus: 'approved', contextType: 'evergreen', image: 'memes/approved/old.webp' },
    { id: 'pending', approvalStatus: 'pending', contextType: 'evergreen', image: 'memes/approved/pending.webp' },
    { id: 'dated', approvalStatus: 'approved', contextType: 'dated', image: 'memes/approved/dated.webp' },
    { id: 'remote', approvalStatus: 'approved', contextType: 'evergreen', image: 'https://example.com/image.webp' },
  ];
  assert.deepEqual(mod.buildArchivePool(curated, memes).map(m => m.id), ['old']);
});


test('locker leads with the daily archive and puts the full collection behind a disclosure', () => {
  const page = readFileSync('src/pages/memes/index.astro', 'utf8');
  assert.match(page, /<DailyArchive/);
  assert.match(page, /<details class="locker-collection">/);
  assert.match(page, /Browse the full collection/);
  assert.ok(page.indexOf('<DailyArchive') < page.indexOf('locker-collection'));
  const curated = read('src/data/archive-features.json');
  const catalog = read('src/data/editorial.json').approvedMemes;
  assert.ok(curated.length > 1, 'a daily rotation needs more than one approved classic');
  for (const c of curated) {
    const m = catalog.find(m => m.id === c.memeId);
    assert.equal(m?.approvalStatus, 'approved');
    assert.equal(m?.contextType, 'evergreen');
    assert.notEqual(m?.date, '2026-11-17', 'new daily headline art is not the archive feature');
  }
});

test('archive deck exhausts before repeating and ignores source order', async () => {
  const { pickArchive } = await import('../src/lib/archive-pick.mjs');
  const pool = ['a', 'b', 'c', 'd'].map(id => ({ id }));
  const picks = Array.from({ length: pool.length }, (_, offset) => {
    const now = new Date(Date.UTC(2026, 10, 18 + offset, 15));
    const forward = pickArchive(pool, now);
    assert.deepEqual(forward, pickArchive([...pool].reverse(), now));
    return forward.item.id;
  });
  assert.equal(new Set(picks).size, pool.length);
  assert.equal(pickArchive(pool, new Date('2026-11-22T15:00:00Z')).item.id, picks[0]);
  assert.equal(pickArchive([], new Date('2026-11-18T15:00:00Z')).item, null);
  assert.throws(() => pickArchive(pool, new Date('bad')), /Invalid archive clock/);
  assert.throws(() => pickArchive([{id:'a'},{id:'a'}]), /unique/);
  assert.equal(pickArchive([{id:'single'}]).item.id, 'single');
});

test('daily archive pick stays fixed until Arizona midnight, then advances', async () => {
  assert.ok(existsSync('src/lib/archive-pick.mjs'), 'daily archive selector must exist');
  const { pickArchive } = await import('../src/lib/archive-pick.mjs');
  const pool = ['a', 'b', 'c'].map(id => ({ id }));
  const morning = pickArchive(pool, new Date('2026-11-18T15:00:00Z'));
  const night = pickArchive(pool, new Date('2026-11-19T06:59:59Z'));
  const next = pickArchive(pool, new Date('2026-11-19T07:00:00Z'));
  assert.equal(morning.item.id, night.item.id);
  assert.equal(morning.date, '2026-11-18');
  assert.equal(next.date, '2026-11-19');
  assert.notEqual(morning.item.id, next.item.id);
});
