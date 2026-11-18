// Run in an isolated Vite development tab after the calendar page has mounted:
// await (await import('/scripts/agent-conversation.browser.mjs')).verifyAgentConversation()
import router from '../src/router/index.ts';
import { authState, writeAuthToken, clearSession } from '../src/api/auth.ts';

export async function verifyAgentConversation() {
  const originalFetch = window.fetch, originalRoute = router.currentRoute.value.fullPath;
  const storageKey = 'livelife.agent.session.v3', savedSession = sessionStorage.getItem(storageKey);
  const savedLocal = localStorage.getItem('livelife.auth.token'), savedTab = sessionStorage.getItem('livelife.auth.token'), savedUser = authState.user;
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
  const conversation = () => document.querySelector('#app .conversation');
  const conversationContent = () => conversation()?.querySelector('.elastic-list-content');
  const position = () => {
    const viewport = conversation().getBoundingClientRect(), content = conversationContent().getBoundingClientRect();
    return { top: content.top - viewport.top, atTop: Math.abs(content.top - viewport.top) < 3, atBottom: Math.abs(content.bottom - viewport.bottom) < 3 };
  };
  const paint = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const mouse = (target, type, x, y) => target.dispatchEvent(new MouseEvent(type, {
    bubbles: true, cancelable: true, button: 0, buttons: type === 'mouseup' ? 0 : 1, clientX: x, clientY: y,
  }));
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
    writeAuthToken('browser-account-test-only');
    window.fetch = async (url, init) => {
      const path = new URL(url instanceof Request ? url.url : String(url), location.href).pathname;
      if (path.endsWith('/auth/me')) return Response.json({ id: 'browser-user', email: 'browser@stu.pku.edu.cn' });
      if (path.endsWith('/agent/sessions')) return init?.method === 'POST' ? Response.json(session, {status:201}) : Response.json({items:[],next_offset:null});
      if (path.endsWith(`/agent/sessions/${session.session_id}`)) return Response.json({ ...session, messages: [] });
      if (path.endsWith('/messages/stream')) {
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
    emit(1, 'delta', { text: '半截回答' });
    requests[1].controller.close();
    await waitFor(() => [...document.querySelectorAll('#app .message-actions button')].some(button => button.textContent.includes('重试')), 'EOF without done did not expose retry');
    assert(bubbles()[1]?.textContent.includes('半截回答') && bubbles()[1]?.textContent.includes('未完整生成'), 'partial EOF retains partial text with explicit incomplete notice');
    assert(document.querySelectorAll('#app .rating-action').length === 2, 'incomplete reply does not expose feedback actions');
    const retry = [...document.querySelectorAll('#app .message-actions button')].find(button => button.textContent.includes('重试'));
    retry.click();
    await waitFor(() => requests.length === 3, 'Retry did not send a request');
    assert(
      users().length === 2
      && requests[2].body.content === '快捷键发送的问题'
      && requests[2].body.client_request_id === requests[1].body.client_request_id,
      'retry reuses the logical client_request_id without duplicating the user message',
    );
    emit(2, 'delta', { text: '重试成功' }); complete(2);
    await waitFor(() => bubbles().length === 2 && bubbles()[1]?.textContent === '重试成功', 'Retry response did not update the bubble in place');

    await input('滚动定位测试 '.repeat(180)); sendButton().click();
    await waitFor(() => requests.length === 4 && users().length === 3, 'Long message did not send');
    await waitFor(() => position().atBottom, 'Sending a message did not scroll to the conversation bottom');
    conversation().focus(); conversation().dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
    await waitFor(() => position().atTop, 'Home did not move the conversation away from the bottom');
    emit(3, 'delta', { text: '用户正在阅读历史时不应跳回底部。'.repeat(80) });
    await waitFor(() => bubbles()[2]?.textContent.includes('不应跳回底部'), 'Long streaming delta did not render');
    assert(position().atTop, 'streaming preserves a reader who has scrolled up');
    conversation().dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
    await waitFor(() => position().atBottom, 'End did not move the conversation to the bottom');
    emit(3, 'delta', { text: '继续跟随底部。'.repeat(40) });
    await waitFor(() => bubbles()[2]?.textContent.includes('继续跟随底部'), 'Second streaming delta did not render');
    await waitFor(() => position().atBottom, 'Streaming content did not keep a bottom reader at the bottom');
    await paint();
    const viewport = conversation().getBoundingClientRect(), x = viewport.left + viewport.width / 2;
    try {
      mouse(conversation(), 'mousedown', x, viewport.top + 40);
      mouse(window, 'mousemove', x, viewport.top + 100);
      mouse(window, 'mousemove', x, viewport.top + 160);
      await paint();
      const readingTop = position().top;
      assert(!position().atBottom, 'drag leaves the bottom before release');
      emit(3, 'delta', { text: '拖动未松手时收到的内容。'.repeat(40) });
      await waitFor(() => bubbles()[2]?.textContent.includes('拖动未松手'), 'Delta during dragging did not render');
      await paint();
      assert(Math.abs(position().top - readingTop) < 3, 'streaming preserves the reading position during an active drag');
    } finally {
      mouse(window, 'mouseup', x, viewport.top + 160);
    }
    complete(3);
    await waitFor(() => !document.querySelector('#app .thinking-message'), 'Dragged response did not complete');
    conversation().focus({ preventScroll: true });
    conversation().dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
    await waitFor(() => position().atTop, 'Home after dragging did not reach history');
    await input('阅读历史后主动发送'); sendButton().click();
    await waitFor(() => requests.length === 5 && users().length === 4, 'Send while reading history did not append a user message');
    await waitFor(() => position().atBottom, 'Sending while reading history did not force the bottom');
    complete(4);
    results.push('sending forces the bottom while streaming respects manual reading position');
    return results;
  } finally {
    await router.push('/calendar');
    for (const request of requests) request.controller.error(new DOMException('Test finished', 'AbortError'));
    window.fetch = originalFetch;
    clearSession();
    if (savedLocal !== null) localStorage.setItem('livelife.auth.token', savedLocal);
    if (savedTab !== null) sessionStorage.setItem('livelife.auth.token', savedTab);
    authState.user = savedUser;
    if (savedSession === null) sessionStorage.removeItem(storageKey);
    else sessionStorage.setItem(storageKey, savedSession);
    await router.push(originalRoute);
  }
}
