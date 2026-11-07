import test from 'node:test';
import assert from 'node:assert/strict';
import { readAgentEvents } from '../src/api/agent-stream.mjs';

test('reads split SSE frames and dispatches citation, text and completion', async () => {
  const chunks = [
    'event: citation\ndata: {"rank":1,"title":"百讲"}\n\n',
    'event: delta\ndata: {"text":"有活动"}\n\n',
    'event: done\ndata: {"status":"completed"}\n\n',
  ];
  const stream = new ReadableStream({
    pull(controller) {
      const chunk = chunks.shift();
      if (chunk) controller.enqueue(new TextEncoder().encode(chunk));
      else controller.close();
    },
  });
  const seen = [];
  await readAgentEvents(new Response(stream), {
    citation: (data) => seen.push(['citation', data.title]),
    delta: (data) => seen.push(['delta', data.text]),
    done: (data) => seen.push(['done', data.status]),
  });
  assert.deepEqual(seen, [['citation', '百讲'], ['delta', '有活动'], ['done', 'completed']]);
});

test('reports HTTP errors using the API error code', async () => {
  await assert.rejects(
    readAgentEvents(new Response(JSON.stringify({ detail: { code: 'token_quota_exceeded' } }), { status: 429 })),
    /token_quota_exceeded/,
  );
});

test('rejects a stream that closes without a terminal event', async () => {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('event: delta\ndata: {"text":"partial"}\n\n'));
      controller.close();
    },
  });
  await assert.rejects(readAgentEvents(new Response(stream), {}), /incomplete_stream/);
});
