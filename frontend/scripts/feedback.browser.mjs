// Run in an isolated Vite tab only. Synthetic accounts/responses; no real user data.
export async function verifyFeedback() {
  const auth = await import('/src/api/auth.ts');
  const { submitFeedback } = await import('/src/api/feedback.ts');
  const { previewState } = await import('/src/platform/runtime-config.ts');
  if (previewState.enabled) throw new Error('Use a local Vite tab without deployment runtime config');
  const original = window.fetch, results = [], calls = [];
  const local = localStorage.getItem('livelife.auth.token'), session = sessionStorage.getItem('livelife.auth.token');
  const receipt = { id: '00000000-0000-4000-8000-000000000105', submitted_at: '2026-11-18T08:00:00Z' };
  let mode = 'network', persisted = 0, lateResolve;
  const identities = new Set();
  const json = (data, status = 200, headers = {}) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', ...headers } });
  const assert = (test, label) => { if (!test) throw new Error(label); };
  const wait = async (check, label) => { await new Promise(r => setTimeout(r, 0)); const until = Date.now() + 8000; while (Date.now() < until) { if (check()) return; await new Promise(r => setTimeout(r, 30)); } throw new Error(label); };
  const form = () => document.querySelector('.feedback-form');
  const input = text => { const element = form().querySelector('textarea'); element.value = text; element.dispatchEvent(new Event('input', { bubbles: true })); };
  const send = () => form().dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  try {
    window.fetch = async (url, init = {}) => {
      const path = new URL(typeof url === 'string' ? url : url.url, location.href).pathname;
      if (path === '/feedback') {
        const body = JSON.parse(init.body); calls.push(body);
        if (mode === 'network') throw new TypeError('synthetic offline');
        if (mode === 'timeout') throw new DOMException('synthetic timeout', 'TimeoutError');
        if (mode === 'server') return json({ detail: 'unavailable' }, 503);
        if (mode === 'rate') return json({ detail: 'limited' }, 429, { 'Retry-After': '60' });
        if (mode === 'invalid') return json({ message: 'not a receipt' });
        if (mode === 'late401') return new Promise(resolve => { lateResolve = resolve; });
        if (!identities.has(body.client_request_id)) { identities.add(body.client_request_id); persisted++; }
        if (mode === 'lost') throw new TypeError('saved but response lost');
        return json(receipt, 201);
      }
      if (path === '/profile/me') return json({ display_name: '反馈验收', bio: '', interests: [] });
      if (path === '/auth/me') return json({ id: '00000000-0000-4000-8000-000000000106', email: 'synthetic105@pku.edu.cn' });
      if (path.startsWith('/favorites/activities')) return json({ items: [], counts: { upcoming: 0, ongoing: 0, ended: 0, unknown: 0 }, total: 0, next_offset: null, as_of: new Date().toISOString() });
      if (path === '/locations/activities') return json({ as_of: new Date().toISOString(), window_end: '2099-12-01T00:00:00Z', items: [], nearby_buildings: [], next_offset: null });
      return original(url, init);
    };
    auth.clearSession(); location.hash = '#/calendar';
    await wait(() => document.querySelector('.calendar-page'), 'calendar mount');
    location.hash = '#/more'; await wait(() => document.querySelector('.settings-menu'), 'more mount');
    [...document.querySelectorAll('.menu-row')].find(button => button.textContent.includes('帮助与反馈')).click();
    await wait(form, 'feedback mount');
    assert(form().querySelector('textarea').disabled && form().querySelector('a[href="#/login"]'), 'login required');
    results.push('未登录入口');
    auth.writeAuthToken('synthetic-feedback-a');
    await wait(() => !form().querySelector('textarea').disabled, 'logged in');
    input('网络失败时保留这段正文'); send();
    await wait(() => form().querySelector('[role="alert"]'), 'network error');
    assert(form().querySelector('textarea').value === '网络失败时保留这段正文', 'draft retained');
    const requestId = calls[0].client_request_id;
    for (const failure of ['timeout', 'server', 'rate', 'invalid']) {
      mode = failure; send(); await wait(() => !form().querySelector('textarea').disabled, `${failure} complete`);
      assert(form().querySelector('[role="alert"]') && !form().querySelector('.feedback-receipt'), `${failure} never success`);
      assert(calls.at(-1).client_request_id === requestId, `${failure} keeps UUID`);
      if (failure === 'rate') assert(form().textContent.includes('60 秒'), 'rate hint');
    }
    results.push('断网、超时、503、429及无效回执保留草稿与原 UUID');
    mode = 'lost'; send(); await wait(() => !form().querySelector('textarea').disabled, 'lost result');
    assert(persisted === 1 && !form().querySelector('.feedback-receipt'), 'uncertain persisted result');
    mode = 'ok'; send(); send();
    await wait(() => form().querySelector('.feedback-receipt'), 'confirmed receipt');
    assert(persisted === 1 && form().querySelector('textarea').value === '', 'one persisted feedback');
    assert(form().textContent.includes(receipt.id), 'receipt number visible');
    results.push('丢失回执重试幂等、防重复点击与确认后清空');
    mode = 'late401'; input('账号 A 的私人草稿'); send();
    await wait(() => lateResolve, 'late request');
    auth.writeAuthToken('synthetic-feedback-b');
    await wait(() => !form().querySelector('textarea').disabled, 'account reset');
    assert(!form().querySelector('.feedback-receipt') && form().querySelector('textarea').value === '', 'clear private state');
    lateResolve(json({ detail: 'expired' }, 401));
    await new Promise(r => setTimeout(r, 60));
    assert(auth.readAuthToken() === 'synthetic-feedback-b' && !form().querySelector('[role="alert"]'), 'old 401 cannot clear B');
    results.push('账号切换清空草稿、回执且拒绝旧401');
    // Exercise API response-body race, not only the form's outer epoch guard.
    let finishJson;
    window.fetch = async () => ({ status: 201, ok: true, headers: new Headers(), json: () => new Promise(resolve => { finishJson = resolve; }) });
    const pending = submitFeedback({ client_request_id: crypto.randomUUID(), content: '迟到正文' }).catch(error => error.message);
    await wait(() => finishJson, 'body pending'); auth.writeAuthToken('synthetic-feedback-c'); finishJson(receipt);
    assert((await pending).includes('登录状态已变更'), 'late body rejected');
    results.push('响应体迟到身份隔离');
    return results;
  } finally {
    location.hash = '#/calendar'; await new Promise(r => setTimeout(r, 80));
    window.fetch = original; auth.clearSession();
    if (local) localStorage.setItem('livelife.auth.token', local);
    if (session) sessionStorage.setItem('livelife.auth.token', session);
  }
}
