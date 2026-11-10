// Run from an isolated, fully mounted Vite calendar tab; no real account is used.
import router from '../src/router/index.ts';
import { authState, deleteAccount } from '../src/api/auth.ts';
import { fetchProfile, updateProfile } from '../src/api/profile.ts';
import { androidState } from '../src/platform/android-config.ts';
import { previewState } from '../src/platform/runtime-config.ts';

const assert = (value, message) => { if (!value) throw new Error(message); };
const waitFor = async condition => {
  const deadline = performance.now() + 5000;
  while (!condition()) {
    if (performance.now() > deadline) throw new Error('Profile regression timed out');
    await new Promise(resolve => requestAnimationFrame(resolve));
  }
};

async function withProfileFixture(check) {
  const originalFetch = window.fetch, originalRoute = router.currentRoute.value.fullPath;
  const key = 'livelife.auth.token', local = localStorage.getItem(key), session = sessionStorage.getItem(key);
  const user = authState.user;
  const preview = { ...previewState }, android = androidState.config;
  const fixture = { profile: { display_name: '回归测试用户', bio: '', interests: [] }, deleteStatus: 400, deleteNetworkError: false,
    sha: 'a'.repeat(40), profileRequests: 0, status: null, statusOffline: false };
  try {
    await router.push('/calendar');
    previewState.enabled = false; androidState.config = null;
    localStorage.setItem(key, 'profile-test-only'); sessionStorage.removeItem(key);
    authState.user = { id: crypto.randomUUID(), email: 'test@pku.edu.cn' };
    window.fetch = async (url, init) => {
      const path = new URL(url instanceof Request ? url.url : String(url), location.href).pathname;
      if (path.endsWith('/status.json')) {
        if (fixture.statusOffline) throw new TypeError('Test status unavailable');
        return Response.json(fixture.status);
      }
      if (path.endsWith('/auth/me') && init?.method === 'DELETE') {
        if (fixture.deleteNetworkError) throw new TypeError('Test network failure');
        return fixture.deleteStatus === 204 ? new Response(null, { status: 204 })
          : Response.json({ detail: 'Password is incorrect' }, { status: fixture.deleteStatus });
      }
      if (path.endsWith('/profile/me')) {
        fixture.profileRequests++;
        if (init?.method === 'PATCH') Object.assign(fixture.profile, JSON.parse(init.body));
        return Response.json(fixture.profile, { headers: fixture.sha === null ? {} : { 'X-Livelife-Backend-SHA': fixture.sha } });
      }
      return originalFetch(url, init);
    };
    return await check(fixture);
  } finally {
    await router.push('/calendar'); window.fetch = originalFetch; authState.user = user;
    if (local === null) localStorage.removeItem(key); else localStorage.setItem(key, local);
    if (session === null) sessionStorage.removeItem(key); else sessionStorage.setItem(key, session);
    Object.assign(previewState, preview); androidState.config = android;
    await router.push(originalRoute);
  }
}

export async function verifyEmptyProfile() {
  return withProfileFixture(async () => {
    // Re-mount twice to catch defaults being restored on refresh/navigation.
    for (let attempt = 0; attempt < 2; attempt++) {
      await router.push('/more');
      await waitFor(() => document.querySelector('#app .profile-copy h1')?.textContent === '回归测试用户');
      assert(document.querySelectorAll('#app .interest-tag').length === 0, 'Empty interests were replaced by demo tags');
      document.querySelector('#app .edit-profile').click();
      await waitFor(() => document.querySelector('#app textarea[aria-label="个人介绍"]'));
      assert(document.querySelector('#app textarea[aria-label="个人介绍"]').value === '', 'Empty bio was replaced by demo text');
      await router.push('/calendar');
    }
    return ['empty interests and bio survive page re-mounts'];
  });
}

export async function verifyDeletionSession() {
  return withProfileFixture(async fixture => {
    const userId = authState.user.id;
    for (const [status, network] of [[400, false], [503, false], [400, true]]) {
      fixture.deleteStatus = status; fixture.deleteNetworkError = network;
      let failed = false;
      try { await deleteAccount('test-only-wrong-password'); } catch { failed = true; }
      assert(failed, 'Failed deletion was reported as successful');
      assert(localStorage.getItem('livelife.auth.token') === 'profile-test-only' && authState.user?.id === userId,
        'Failed deletion cleared the login state');
    }
    fixture.deleteNetworkError = false; fixture.deleteStatus = 204;
    await deleteAccount('test-only-password');
    assert(localStorage.getItem('livelife.auth.token') === null && sessionStorage.getItem('livelife.auth.token') === null
      && authState.user === null, 'Successful deletion did not clear the login state');
    return ['wrong password, server failure and network failure preserve session; successful deletion clears it'];
  });
}

export async function verifyProfileConfiguration() {
  return withProfileFixture(async fixture => {
    const sha = 'a'.repeat(40);
    const config = { backend_mode: 'fixed', backend_sha: sha, api_base_url: `${location.origin}/api/versions/be-${sha}/` };
    previewState.enabled = true; previewState.config = config;
    assert((await fetchProfile()).ok, 'Matching backend was rejected');
    for (const response of [null, 'invalid', 'b'.repeat(40)]) {
      fixture.sha = response;
      const result = await fetchProfile();
      assert(!result.ok && result.error.includes('版本'), 'Invalid backend SHA was accepted');
    }
    previewState.config = { ...config, backend_mode: 'staging' };
    assert((await fetchProfile()).ok, 'Staging refused a valid updated SHA');
    const android = { ...config, apk_id: 'b'.repeat(32), version_code: 7, frontend_sha: sha,
      status_url: `${location.origin}/downloads/android/build-${'b'.repeat(32)}/status.json` };
    androidState.config = android; fixture.sha = sha;
    fixture.status = { ...android, status: 'ready', expires: Date.now() / 1000 + 3600 };
    assert((await fetchProfile()).ok, 'Ready APK was rejected');
    const requests = fixture.profileRequests;
    for (const status of [{ status: 'released' }, { status: 'ready', expires: 1 }, { offline: true }]) {
      fixture.status = { ...android, expires: Date.now() / 1000 + 3600, ...status };
      fixture.statusOffline = Boolean(status.offline);
      assert(!(await fetchProfile()).ok && !(await updateProfile({ bio: 'blocked' })).ok, 'Invalid APK was allowed to access profiles');
      assert(fixture.profileRequests === requests, 'Profile request escaped the APK status gate');
    }
    return ['matching/missing/malformed/mismatched SHA; staging updates; ready/released/expired/offline APK gates'];
  });
}
