export async function readAgentEvents(response, handlers, signal) {
  if (!response.ok) {
    let code = `http_${response.status}`;
    try { code = (await response.json())?.detail?.code || code; } catch { /* keep status code */ }
    throw new Error(code);
  }
  if (!response.body) throw new Error('empty_stream');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let terminalEvent = false;
  try {
    while (true) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r\n/g, '\n');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = parseFrame(frame);
        if (event) {
          if (event.event === 'done' || event.event === 'error') terminalEvent = true;
          await handlers[event.event]?.(event.data);
        }
      }
      if (done) break;
    }
    if (buffer.trim()) {
      const event = parseFrame(buffer);
      if (event) {
        if (event.event === 'done' || event.event === 'error') terminalEvent = true;
        await handlers[event.event]?.(event.data);
      }
    }
    if (!terminalEvent) throw new Error('incomplete_stream');
  } finally {
    if (signal?.aborted) await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

function parseFrame(frame) {
  let event = 'message';
  const data = [];
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  try { return { event, data: JSON.parse(data.join('\n')) }; }
  catch { return null; }
}
