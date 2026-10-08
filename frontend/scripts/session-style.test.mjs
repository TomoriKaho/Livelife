import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { sessionShuffle } from '../src/data/session-style.ts';

test('recreating a demo page keeps its palette and cannot mutate the session assignment', () => {
  const palette = ['mint', 'blue', 'pink', 'lavender', 'yellow'];
  const first = sessionShuffle('palette-test', palette);
  assert.deepEqual([...first].sort(), [...palette].sort());
  const expected = [...first];
  first.reverse();
  assert.deepEqual(sessionShuffle('palette-test', palette), expected);
});


test('cold application instances keep demo palettes and order stable', async () => {
  const cold = await import('../src/data/session-style.ts?cold');
  const values = ['yellow', 'blue', 'pink', 'mint', 'lavender'];
  assert.deepEqual(sessionShuffle('cold-palette', values), cold.sessionShuffle('cold-palette', values));
});
