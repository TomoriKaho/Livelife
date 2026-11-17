// Run only in an isolated Vite tab. Uses synthetic fetch responses, no real account.
export async function verifyFavorites() {
  const auth = await import('/src/api/auth.ts');
  const { favorites } = await import('/src/state/favorites.ts');
  const original = window.fetch;
  const oldLocal = localStorage.getItem('livelife.auth.token');
  const oldSession = sessionStorage.getItem('livelife.auth.token');
  const user = { id: '00000000-0000-4000-8000-000000000100', email: 'synthetic100@pku.edu.cn' };
  const id = '00000000-0000-4000-8000-000000000101';
  const row = { id, saved_at: new Date().toISOString(), available: true, title: '收藏浏览器替身活动', platform: 'pku', source_name: '测试来源', source_url: 'https://example.com/source', activity_date: '2099-11-16', start_at: '2099-11-16T08:00:00Z', end_at: null, location: null, place: null, status: 'upcoming' };
  let failList = true, failRemove = true, expired = false, late = null;
  const saved = new Set([id]), results = [];
  function json(data, status = 200) { return new Response(status === 204 ? null : JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }); }
  function list(hasItems) { return { items: hasItems ? [row] : [], counts: { upcoming: hasItems ? 1 : 0, ongoing: 0, ended: 0, unknown: 0 }, total: hasItems ? 1 : 0, next_offset: null, as_of: new Date().toISOString() }; }
  async function wait(check, label) { const until = Date.now() + 8000; while (Date.now() < until) { if (check()) return; await new Promise(r => setTimeout(r, 40)); } throw new Error(label); }
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  try {
    window.fetch = async (input, init = {}) => {
      const url = new URL(typeof input === 'string' ? input : input.url, location.href);
      const method = init.method || 'GET';
      if (url.pathname.startsWith('/favorites/activities')) {
        if (expired) return json({ detail: 'expired' }, 401);
        if (url.pathname.endsWith('/status')) return json({ saved_ids: [] });
        if (method === 'DELETE') { if (failRemove) return json({ detail: 'unavailable' }, 503); saved.delete(id); return json(null, 204); }
        const isA = init.headers.Authorization === 'Bearer synthetic-account-a-100';
        if (late && isA) return late.promise;
        if (failList) return json({ detail: 'unavailable' }, 503);
        return json(list(isA && saved.has(id) && url.searchParams.get('status') === 'upcoming'));
      }
      if (url.pathname === '/profile/me') return json({ display_name: '测试用户', bio: '', interests: [] });
      if (url.pathname === '/auth/me') return json(user);
      if (url.pathname === '/locations/activities') return json({ as_of: new Date().toISOString(), window_end: '2099-12-01T00:00:00Z', items: [], nearby_buildings: [], next_offset: null });
      return original(input, init);
    };
    auth.writeAuthToken('synthetic-account-a-100'); auth.authState.user = user;
    location.hash = '#/calendar'; await wait(() => document.querySelector('.calendar-page'), 'calendar mount');
    location.hash = '#/more?pane=favorites';
    await wait(() => document.querySelector('.favorites-list [role="alert"]'), 'initial failure');
    failList = false;
    document.querySelector('.reload-favorites').click();
    await wait(() => document.querySelector('.favorite-card'), 'list retry');
    results.push('列表失败与重试');
    document.querySelector('.remove-favorite').click();
    await wait(() => document.querySelector('.favorite-card [role="alert"]'), 'failed remove');
    assert(document.querySelector('.favorite-card h2')?.textContent === row.title, 'failed remove must retain card');
    failRemove = false; document.querySelector('.remove-favorite').click();
    await wait(() => document.querySelector('.empty-favorites'), 'successful remove');
    results.push('取消失败保留与成功移除');
    saved.add(id);
    let resolve;
    late = { promise: new Promise(r => { resolve = r; }) };
    const pending = favorites.load();
    await new Promise(r => setTimeout(r, 30));
    auth.writeAuthToken('synthetic-account-b-100'); auth.authState.user = { ...user, id: '00000000-0000-4000-8000-000000000200' };
    await wait(() => document.querySelector('.empty-favorites'), 'account b empty');
    resolve(json(list(true))); await pending;
    assert(!document.querySelector('.favorite-card'), 'late account a must not return');
    results.push('账号切换拒绝旧列表');
    late = null; expired = true;
    await favorites.load();
    await wait(() => document.querySelector('.favorites-list a[href="#/login"]') || document.querySelector('.favorites-list')?.textContent.includes('登录后可保存'), 'expired login');
    assert(auth.readAuthToken() === null, '401 clears credential');
    assert(favorites.state.total === 0 && !document.querySelector('.favorite-card'), '401 clears private state');
    results.push('登录过期清理与登录提示');
    return results;
  } finally {
    location.hash = '#/calendar';
    await new Promise(r => setTimeout(r, 100));
    window.fetch = original;
    auth.clearSession();
    if (oldLocal) localStorage.setItem('livelife.auth.token', oldLocal);
    if (oldSession) sessionStorage.setItem('livelife.auth.token', oldSession);
  }
}
