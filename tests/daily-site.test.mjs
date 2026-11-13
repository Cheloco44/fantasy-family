import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import vm from 'node:vm';

const source = path => readFileSync(`src/${path}`, 'utf8');
const script = path => (source(path).match(/<script>([\s\S]*?)<\/script>/)?.[1] || '')
  .replace(/<(?:HTMLInputElement|HTMLSelectElement|HTMLElement)>/g, '')
  .replace(/!([;.])/g, '$1').replace(/:string\[\]/g, '').replace(/ as HTMLElement/g, '');

test('locker combines caption, tag and any selected manager; reset clears every control', () => {
  const control = value => ({ value, checked: false, addEventListener(event, fn) { this[event] = fn; }, focus() {} });
  const search = control(''); const tag = control(''); const reset = control('');
  const managers = ['marcelo', 'rich', 'ben'].map(control);
  const cards = [
    { dataset: { caption: 'daily punchline', tags: '["rivalry"]', managers: '["marcelo","rich"]' } },
    { dataset: { caption: 'another punchline', tags: '["rivalry"]', managers: '["ben"]' } },
    { dataset: { caption: 'demo goalie', tags: '["goalies"]', managers: '[]' } },
  ];
  const results = {}; const empty = {};
  const nodes = { '#manager-filter': control(''), '#meme-search': search, '#tag-filter': tag, '#clear-filters': reset, '#results': results, '#empty-results': empty };
  vm.runInNewContext(script('pages/memes/index.astro'), { document: {
    querySelector: s => nodes[s], querySelectorAll: s => s === '.meme' ? cards : managers,
  } });
  search.value = 'PUNCHLINE'; search.input(); tag.value = 'rivalry'; tag.change();
  managers[1].checked = true; managers[1].change();
  assert.deepEqual(cards.map(c => c.hidden), [false, true, true], 'second manager association matches');
  managers[2].checked = true; managers[2].change();
  assert.deepEqual(cards.map(c => c.hidden), [false, false, true], 'selected managers are an OR group');
  search.value = 'missing'; search.input(); assert.equal(empty.hidden, false);
  reset.click();
  assert.equal(search.value, ''); assert.equal(tag.value, '');
  assert.ok(managers.every(m => !m.checked)); assert.ok(cards.every(c => !c.hidden));
  assert.equal(empty.hidden, true); assert.equal(results.textContent, 'Showing 3 of 3 memes');
});

test('daily presentation preserves complete art and wraps manager controls on phones', () => {
  const css = source('styles/global.css');
  assert.match(css, /\.round-art img[^}]*object-fit:contain/);
  assert.match(css, /\.manager-options[^}]*flex-wrap:wrap/);
  assert.match(css, /\.manager-options label[^}]*min-height:44px/);
  assert.match(css, /\[hidden\][^{]*\{display:none!important/);
});

test('daily edition routes consume the shared archive with explicit evidence and weekly separation', () => {
  const home = source('pages/index.astro');
  assert.ok(home.includes("../data/recaps.json"), 'homepage must read the real archive');
  assert.ok(home.includes('data-recap-date'));
  const archive = source('pages/recaps/index.astro');
  assert.ok(archive.includes('recaps.editions.map'));
  assert.ok(existsSync('src/pages/recaps/[date].astro'), 'individual date route');
  const daily = source('pages/recaps/[date].astro');
  for (const marker of ['getStaticPaths', 'sourceFetchedAt', 'weeklyContextAt', 'coverageNote', 'trendNotes', 'DAILY ROUND', 'approvalStatus', 'isArchive']) assert.ok(daily.includes(marker), marker);
});

test('global clubhouse labels distinguish real daily aggregates from the sample', () => {
  const layout = source('layouts/Layout.astro');
  assert.ok(layout.includes('07:00'));
  assert.ok(!layout.includes('recaps remain DEMO'));
  assert.ok(layout.includes('Daily team aggregates'));
});

test('no-network freshness uses Arizona yesterday and ages an unchanged deployed page', () => {
  function check(now, date) {
    const warning = { hidden: true };
    const node = { dataset: { recapDate: date }, querySelector: () => warning };
    class Clock extends Date { constructor(...args) { super(...(args.length ? args : [now])); } }
    vm.runInNewContext(script('layouts/Layout.astro'), {
      document: { querySelectorAll: () => [node] }, Date: Clock, Intl,
      setInterval: () => {}, window: { addEventListener() {} },
    });
    return warning.hidden;
  }
  assert.equal(check('2026-11-13T06:59:00Z', '2026-11-11'), true, 'still Nov 12 in Arizona');
  assert.equal(check('2026-11-13T07:01:00Z', '2026-11-11'), false, 'now older than yesterday');
  assert.equal(check('2026-11-13T07:01:00Z', '2026-11-12'), true);
});
