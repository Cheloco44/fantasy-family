import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';

test('Arizona yesterday uses local calendar boundaries in winter, summer and new year', async () => {
  assert.ok(existsSync('src/lib/clock.mjs'), 'recap clock must exist');
  const { yesterdayArizona } = await import('../src/lib/clock.mjs');
  assert.equal(yesterdayArizona(new Date('2027-01-01T06:59:00Z')), '2026-12-30');
  assert.equal(yesterdayArizona(new Date('2027-01-01T07:00:00Z')), '2026-12-31');
  assert.equal(yesterdayArizona(new Date('2027-07-10T12:00:00Z')), '2027-07-09');
});
