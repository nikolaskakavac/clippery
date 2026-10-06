import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseClips } from './paste-clips';

test('imports ordered named ranges from ChatGPT code blocks and lists', () => {
  const rows = parseClips('```text\n1. **Hook** | 00:12 - 00:38\n\n- Main | 02:15.125 → 03:05\n```', 600);
  assert.deepEqual(rows.map(row => row.clip), [{ name: 'Hook', start: 12, end: 38 }, { name: 'Main', start: 135.125, end: 185 }]);
  assert.deepEqual(rows.map(row => row.line), [2, 4]);
});
test('invalid lines remain visible and cannot become clips', () => {
  const rows = parseClips('Good | 00:00 - 00:10\nBad | 00:10 - 00:00\nToo long | 00:00 - 05:01\nOutside | 09:00 - 11:00\nMissing format\n | 00:00 - 00:10', 600);
  assert.ok(rows[0].clip);
  assert.ok(rows.slice(1).every(row => row.error && !row.clip));
  assert.deepEqual(parseClips('  \n', 600), []);
});
test('limits batch and name sizes without silently dropping rows', () => {
  assert.ok(parseClips(Array(101).fill('Clip | 00:00 - 00:01').join('\n'), 600)[0].error);
  assert.ok(parseClips(`${'a'.repeat(121)} | 00:00 - 00:01`, 600)[0].error);
});
