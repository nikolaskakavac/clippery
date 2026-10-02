import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseHistory, rememberSource } from './source-history';
import { Video } from './api';

const source = (index: number): Video => ({ id: String(index).padStart(11, '0'), title: `Video ${index}`, channel: 'Creator', duration: 60,
  durationFormatted: '00:01:00', thumbnail: 'https://untrusted.test/image', webpageUrl: 'https://untrusted.test/', isShort: false });

test('history rejects malformed storage and reconstructs trusted URLs', () => {
  assert.deepEqual(parseHistory('{broken'), []);
  assert.deepEqual(parseHistory('{}'), []);
  const history = parseHistory(JSON.stringify([null, {}, source(1), source(1), { ...source(2), duration: -1 }]));
  assert.equal(history.length, 1);
  assert.equal(history[0].webpageUrl, 'https://www.youtube.com/watch?v=00000000001');
  assert.equal(history[0].thumbnail, 'https://i.ytimg.com/vi/00000000001/hqdefault.jpg');
});

test('recent sources are unique, refreshed and capped at twenty', () => {
  const items = Array.from({ length: 25 }, (_, index) => source(index));
  const updated = rememberSource(items, { ...source(5), title: 'Updated' });
  assert.equal(updated.length, 20);
  assert.equal(updated[0].title, 'Updated');
  assert.equal(updated.filter(item => item.id === source(5).id).length, 1);
  assert.equal(parseHistory(JSON.stringify(items)).length, 20);
  assert.equal(items[0].id, source(0).id);
});
