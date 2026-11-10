// Run in an isolated Vite development tab after the calendar page has mounted:
// await (await import('/scripts/agent-conversation.browser.mjs')).verifyAgentConversation()
import router from '../src/router/index.ts';

export async function verifyAgentConversation() {
  const originalFetch = window.fetch, originalRoute = router.currentRoute.value.fullPath;
  const storageKey = 'livelife.agent.session.v1', savedSession = sessionStorage.getItem(storageKey);
  const requests = [], results = [], encoder = new TextEncoder();
  const assert = (condition, message) => { if (!condition) throw new Error(message); results.push(message); };
  const waitFor = async (condition, message) => {
    const deadline = performance.now() + 5000;
    while (!condition()) {
      if (performance.now() > deadline) throw new Error(message);
      await new Promise(resolve => requestAnimationFrame(resolve));
    }
  };
  const session = { session_id: crypto.randomUUID(), session_token: 'browser-test-only', expires_at: new Date(Date.now() + 86400000).toISOString() };
  const bubbles = () => document.querySelectorAll('#app .message-agent .message-bubble');
  const users = () => document.querySelectorAll('#app .message-user');
  const editor = () => document.querySelector('#app textarea');
  const sendButton = () => document.querySelector('#app .send-button');
  const input = async text => {
    editor().value = text; editor().dispatchEvent(new Event('input', { bubbles: true }));
    await waitFor(() => !sendButton().disabled, 'Send button did not become ready');
  };
  const emit = (index, event, data) => requests[index].controller.enqueue(
    encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`),
  );
  const complete = index => { emit(index, 'done', { status: 'completed' }); requests[index].controller.close(); };
  try {
    await router.push('/calendar');
    window.fetch = async (url, init) => {
      const path = new URL(url instanceof Request ? url.url : String(url), location.href).pathname;
      if (path.endsWith('/agent/sessions')) return Response.json(session, { status: 201 });
      if (path.endsWith('/agent/sessions/current')) return Response.json({ ...session, messages: [] });
      if (path.endsWith('/agent/messages/stream')) {
        const request = { body: JSON.parse(init.body), controller: null };
        requests.push(request);
        return new Response(new ReadableStream({
          start(controller) { request.controller = controller; },
        }), { headers: { 'Content-Type': 'text/event-stream' } });
      }
      return originalFetch(url, init);
    };
    await router.push('/agent');
    await waitFor(() => editor() && !document.querySelector('#app .conversation-date')?.textContent.includes('正在连接'), 'Conversation did not load');
    await input('按钮发送的问题'); sendButton().click();
    await waitFor(() => requests.length === 1 && users().length === 1, 'Click did not append a user message');
    assert(editor().value === '', 'click clears draft and appends exactly one user message');
    assert(requests[0].body.content === '按钮发送的问题', 'click sends the entered question');
    assert(sendButton().disabled, 'duplicate send is disabled while streaming');
    emit(0, 'message_start', { message_id: crypto.randomUUID() });
    emit(0, 'delta', { text: '第一段' });
    await waitFor(() => bubbles()[0]?.textContent === '第一段', 'First delta was not rendered before completion');
    emit(0, 'citation', { information_id: crypto.randomUUID(), rank: 1, title: '测试来源', platform: 'test', snippet: '公开片段', source_url: 'https://example.test/source' });
    await waitFor(() => document.querySelector('#app .citation-link'), 'Citation was not rendered during streaming');
    emit(0, 'delta', { text: '第二段' });
    await waitFor(() => bubbles()[0]?.textContent === '第一段第二段', 'Second delta was not rendered before completion');
    results.push('text and citations update incrementally before done');
    complete(0);
    await waitFor(() => document.querySelector('#app .rating-action'), 'Completion did not enable feedback');
    assert(!document.querySelector('#app .thinking-message'), 'completion removes the thinking indicator without further input');

    await input('快捷键发送的问题');
    editor().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true }));
    await waitFor(() => requests.length === 2 && users().length === 2, 'Keyboard send did not append a user message');
    assert(editor().value === '' && requests[1].body.content === '快捷键发送的问题', 'Ctrl+Enter clears draft and sends exactly one question');
    emit(1, 'error', { code: 'model_timeout', retryable: true }); requests[1].controller.close();
    await waitFor(() => [...document.querySelectorAll('#app .message-actions button')].some(button => button.textContent.includes('重试')), 'Failure did not expose retry');
    const retry = [...document.querySelectorAll('#app .message-actions button')].find(button => button.textContent.includes('重试'));
    retry.click();
    await waitFor(() => requests.length === 3, 'Retry did not send a request');
    assert(users().length === 2 && requests[2].body.content === '快捷键发送的问题', 'retry resends the question without duplicating the user message');
    emit(2, 'delta', { text: '重试成功' }); complete(2);
    await waitFor(() => bubbles()[2]?.textContent === '重试成功', 'Retry response did not render');
    return results;
  } finally {
    await router.push('/calendar');
    for (const request of requests) request.controller.error(new DOMException('Test finished', 'AbortError'));
    window.fetch = originalFetch;
    if (savedSession === null) sessionStorage.removeItem(storageKey);
    else sessionStorage.setItem(storageKey, savedSession);
    await router.push(originalRoute);
  }
}
