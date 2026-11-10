// Run from an isolated, fully mounted Vite calendar tab; no real account is used.
import router from '../src/router/index.ts';
import { authState } from '../src/api/auth.ts';

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
  const fixture = { profile: { display_name: '回归测试用户', bio: '', interests: [] } };
  try {
    await router.push('/calendar');
    localStorage.setItem(key, 'profile-test-only'); sessionStorage.removeItem(key);
    authState.user = { id: crypto.randomUUID(), email: 'test@pku.edu.cn' };
    window.fetch = async (url, init) => {
      const path = new URL(url instanceof Request ? url.url : String(url), location.href).pathname;
      if (path.endsWith('/profile/me')) {
        if (init?.method === 'PATCH') Object.assign(fixture.profile, JSON.parse(init.body));
        return Response.json(fixture.profile);
      }
      return originalFetch(url, init);
    };
    return await check(fixture);
  } finally {
    await router.push('/calendar'); window.fetch = originalFetch; authState.user = user;
    if (local === null) localStorage.removeItem(key); else localStorage.setItem(key, local);
    if (session === null) sessionStorage.removeItem(key); else sessionStorage.setItem(key, session);
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
