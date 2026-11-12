import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const managers = JSON.parse(readFileSync('src/data/clubhouse.json', 'utf8')).managers;

test('profiles, archive and filterable meme gallery build as real routes', () => {
  for (const path of ['managers/index.html', ...managers.map(m => `managers/${m.slug}/index.html`), 'memes/index.html', 'recaps/index.html', 'recaps/sample/index.html']) {
    assert.ok(existsSync(`dist/${path}`), path);
    assert.ok(readFileSync(`dist/${path}`, 'utf8').includes('DEMO DATA'), path);
  }
  const gallery = readFileSync('dist/memes/index.html', 'utf8');
  for (const marker of ['id="tag-filter"', 'id="manager-filter"', 'id="meme-search"', 'aria-live="polite"']) assert.ok(gallery.includes(marker), marker);
});

test('clubhouse build is explicit about demo data and public status', () => {
  assert.ok(existsSync('dist/index.html'), 'Astro must produce the dashboard');
  const html = readFileSync('dist/index.html', 'utf8');
  for (const text of ['Redlands Possum Busters', 'DEMO DATA', 'No successful ESPN results refresh', 'America/Phoenix', 'Not connected']) assert.ok(html.includes(text), text);
  assert.ok(!html.includes('espn_s2'));
});
