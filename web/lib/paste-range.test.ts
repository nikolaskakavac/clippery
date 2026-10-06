import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseRange } from './paste-range';

test('accepts ChatGPT ranges, labeled lines and fractional timestamps', () => {
  for (const text of ['02:15 - 02:48', '**02:15–02:48**', 'IN: 00:02:15\nOUT: 00:02:48', 'od 02:15 do 02:48', '[02:15] → [02:48]']) {
    assert.deepEqual(parseRange(text, 500), { start: 135, end: 168 });
  }
  assert.deepEqual(parseRange('00:02:15,125 --> 00:02:48.500', 500), { start: 135.125, end: 168.5 });
});
test('invalid, ambiguous and out-of-bounds ranges cannot overwrite IN/OUT', () => {
  for (const text of ['02:15', '02:15 - 02:48\n03:00 - 03:20', '-02:15 - 02:48', '02:99 - 03:20', '03:20 - 02:15', '00:00 - 05:01', '08:00 - 09:00']) {
    assert.throws(() => parseRange(text, 500));
  }
});
