// Run in an isolated local Vite tab (no real credentials or model requests).
import { authState, clearSession, readAuthToken, writeAuthToken, logout } from '../src/api/auth.ts';
import { loadAgentSession, sendAgentMessage } from '../src/api/agent.ts';

export async function verifyAgentAuth() {
  const originalFetch = window.fetch;
  const savedLocal = localStorage.getItem('livelife.auth.token');
  const savedTab = sessionStorage.getItem('livelife.auth.token');
  const savedAgent = sessionStorage.getItem('livelife.agent.session.v2');
  const savedUser = authState.user;
  const results = [];
  const assert = (ok, message) => { if (!ok) throw new Error(message); results.push(message); };
  const select = token => {
    writeAuthToken(token);
    authState.user = { id: token, email: 'synthetic@stu.pku.edu.cn' };
  };
  const conversation = { session_id: 'synthetic-session', session_token: 'synthetic-agent-token', expires_at: new Date(Date.now() + 86400000).toISOString() };
  const waitFor = async condition => {
    for (let i = 0; i < 100; i++) {
      if (condition()) return;
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    throw new Error('Timed out waiting for test request');
  };
  try {
    clearSession();
    let calls = 0;
    window.fetch = async () => { calls++; return Response.json(conversation); };
    await loadAgentSession().then(() => { throw new Error('Anonymous request accepted'); }, error => {
      assert(error.message === 'authentication_required' && calls === 0, 'anonymous client makes no Agent request');
    });
    select('account-a');
    window.fetch = async (_url, init) => {
      assert(init.headers.Authorization === 'Bearer account-a', 'Agent creation sends account Bearer');
      return Response.json(conversation, { status: 201 });
    };
    await loadAgentSession();
    window.fetch = async (_url, init) => {
      assert(init.headers.Authorization === 'Bearer account-a' && init.headers['X-Agent-Session'] === conversation.session_token, 'history sends separate account and conversation credentials');
      return Response.json({ ...conversation, messages: [] });
    };
    await loadAgentSession();

    let release;
    window.fetch = () => new Promise(resolve => { release = resolve; });
    const stale = loadAgentSession().catch(error => error);
    await waitFor(() => release);
    select('account-b');
    release(Response.json({ ...conversation, messages: [{ content: 'private-a' }] }));
    assert((await stale).message === 'authentication_required', 'late history from account A is rejected after switch');
    assert(sessionStorage.getItem('livelife.agent.session.v2') === null, 'account switch removes prior conversation cache');

    window.fetch = async () => Response.json(conversation);
    await loadAgentSession();
    let requestSignal;
    window.fetch = async (_url, init) => {
      requestSignal = init.signal;
      return new Response(new ReadableStream({
        start(controller) {
          init.signal.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')));
        },
      }));
    };
    const stream = sendAgentMessage(conversation.session_token, 'hello', crypto.randomUUID(), {}, new AbortController().signal).catch(error => error);
    await waitFor(() => requestSignal);
    clearSession();
    await stream;
    assert(requestSignal.aborted && !readAuthToken(), 'logout/identity clearing aborts active SSE');
    assert(sessionStorage.getItem('livelife.agent.session.v2') === null, 'logout clears Agent cache');

    select('account-c');
    calls = 0;
    window.fetch = async () => { calls++; return Response.json({ detail: 'Session expired' }, { status: 401 }); };
    await loadAgentSession().catch(() => {});
    assert(calls === 1 && readAuthToken() === null, '401 clears login without creating another anonymous session');

    select('account-d');
    let logoutRelease;
    window.fetch = () => new Promise(resolve => { logoutRelease = resolve; });
    const oldLogout = logout();
    await waitFor(() => logoutRelease);
    select('account-e');
    logoutRelease(new Response(null, { status: 204 }));
    await oldLogout;
    assert(readAuthToken() === 'account-e', 'late logout response cannot clear a newer account');

    sessionStorage.setItem('livelife.agent.session.v2', 'synthetic-cache');
    window.dispatchEvent(new StorageEvent('storage', { key: 'livelife.auth.token', storageArea: localStorage }));
    assert(sessionStorage.getItem('livelife.agent.session.v2') === null && authState.user === null, 'cross-tab identity change invalidates Agent state');
    return results;
  } finally {
    window.fetch = originalFetch;
    clearSession();
    if (savedLocal !== null) localStorage.setItem('livelife.auth.token', savedLocal);
    if (savedTab !== null) sessionStorage.setItem('livelife.auth.token', savedTab);
    if (savedAgent !== null) sessionStorage.setItem('livelife.agent.session.v2', savedAgent);
    authState.user = savedUser;
  }
}
