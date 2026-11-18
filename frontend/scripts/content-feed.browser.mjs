// In an isolated Vite tab: await (await import('/scripts/content-feed.browser.mjs')).verifyContentFeed()
import { createApp, h, nextTick, ref } from 'vue';
import { useContentFeed } from '../src/pages/interests/useContentFeed.ts';
import { fetchContent } from '../src/api/content.ts';
import { previewState } from '../src/platform/runtime-config.ts';
import { androidState } from '../src/platform/android-config.ts';

const assert = (value, message) => { if (!value) throw new Error(message); };
const waitFor = async check => {
  const deadline = performance.now() + 15000;
  while (!check()) {
    if (performance.now() > deadline) throw new Error('Content regression timed out');
    await new Promise(resolve => setTimeout(resolve, 10));
  }
};
const item = id => ({ id, title: null, excerpt: '<b>literal text</b>', platform: 'wechat', source_name: null,
  source_url: null, fetched_at: '2026-11-18T04:00:00Z', published_at: null });

export async function verifyContentFeed() {
  const original = window.fetch, preview = { ...previewState }, android = androidState.config;
  const root = document.createElement('div');
  const filters = ref({ keyword: '', platform: '', source_name: '' });
  let feed, mode = 'pages', releaseOld, requests = [];
  const app = createApp({ setup() { feed = useContentFeed(filters); return () => h('div'); } });
  try {
    previewState.enabled = false; androidState.config = null;
    window.fetch = async (url, options) => {
      if (!String(url).includes('/content/articles?')) return original(url, options);
      const params = new URL(url).searchParams;
      requests.push(Object.fromEntries(params));
      if (mode === 'offline') throw new TypeError('Test network unavailable');
      if (mode === 'slow') return new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))));
      if (mode === 'invalid') return Response.json({ items: [ { ...item('unsafe'), source_url: 'javascript:alert(1)' } ], next_offset: null });
      if (mode === 'late' && params.get('keyword') === 'old') {
        // Deliberately ignore abort to exercise the response generation guard.
        await new Promise(resolve => { releaseOld = resolve; });
        return Response.json({ items: [item('old')], next_offset: null });
      }
      if (mode === 'empty') return Response.json({ items: [], next_offset: null });
      if (params.get('offset') === '20') return Response.json({ items: [item('first'), item('second')], next_offset: null });
      return Response.json({ items: [item(params.get('keyword') || 'first')], next_offset: mode === 'pages' ? 20 : null });
    };
    app.mount(root);
    await waitFor(() => !feed.loading.value);
    assert(feed.items.value[0].id === 'first', 'Initial page failed');
    await feed.loadMore();
    assert(feed.items.value.length === 2 && feed.nextOffset.value === null, 'Pagination or dedup failed');
    mode = 'offline'; await feed.reload();
    assert(feed.error.value && !feed.items.value.length, 'Offline state failed');
    mode = 'pages'; await feed.retry();
    mode = 'offline'; await feed.loadMore();
    assert(feed.error.value && feed.items.value.length === 1 && feed.nextOffset.value === 20, 'Failed page lost content');
    mode = 'pages'; await feed.retry();
    assert(feed.items.value.length === 2, 'Page retry failed');
    mode = 'late'; filters.value.keyword = 'old'; await nextTick();
    await waitFor(() => !!releaseOld);
    filters.value.keyword = 'new'; await nextTick();
    await waitFor(() => !feed.loading.value);
    releaseOld(); await new Promise(resolve => setTimeout(resolve, 30));
    assert(feed.items.value[0].id === 'new', 'Late response overwrote new query');
    mode = 'empty'; await feed.reload();
    assert(!feed.error.value && !feed.items.value.length, 'Empty state failed');
    mode = 'slow'; await feed.reload();
    assert(feed.error.value.includes('超时'), 'Timeout state failed');
    mode = 'invalid';
    await fetchContent(filters.value, 0, new AbortController().signal).then(() => { throw new Error('Unsafe link accepted'); }, error => assert(error.message.includes('格式'), 'Wrong invalid response error'));
    previewState.enabled = true; previewState.config = { api_base_url: 'http://localhost:8000', backend_mode: 'fixed', backend_sha: 'a'.repeat(40) };
    mode = 'empty';
    await fetchContent(filters.value, 0, new AbortController().signal).then(() => { throw new Error('Missing SHA accepted'); }, error => assert(error.message.includes('版本'), 'Wrong version error'));
    return { passed: true, checks: ['pagination', 'dedup', 'offline', 'page retry', 'late response', 'empty', 'timeout', 'unsafe link', 'SHA gate'], requests: requests.length };
  } finally {
    app.unmount(); window.fetch = original;
    Object.assign(previewState, preview); androidState.config = android;
  }
}
