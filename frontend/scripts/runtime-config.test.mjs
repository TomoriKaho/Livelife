import test from 'node:test';
import assert from 'node:assert/strict';
import { validateRuntimeConfig, loadPreviewConfig, previewState } from '../src/platform/runtime-config.ts';

const sha = 'a'.repeat(40);
const config = { schema_version: 1, environment: 'main', frontend_sha: sha,
  build_id: `fe-${sha}-12-1`, backend_mode: 'staging', backend_sha: sha, api_base_url: '/api/staging/' };
const origin = 'https://192.144.253.40';
test('configuration accepts same-origin staging and pinned versions', () => {
  assert.equal(validateRuntimeConfig(config, origin).api_base_url, origin + '/api/staging/');
  assert.equal(validateRuntimeConfig({ ...config, backend_mode: 'fixed', api_base_url: `/api/versions/be-${sha}/` }, origin).backend_sha, sha);
});
test('configuration refuses cross-origin, credentials, unexpected paths and mismatched pins', () => {
  for (const api_base_url of ['http://localhost:8000/', 'https://other.test/api/staging/',
    'https://user:password@192.144.253.40/api/staging/', '/api/staging/?token=private', '/other/']) {
    assert.throws(() => validateRuntimeConfig({ ...config, api_base_url }, origin));
  }
  assert.throws(() => validateRuntimeConfig({ ...config, schema_version: 2 }, origin));
  assert.throws(() => validateRuntimeConfig({ ...config, backend_mode: 'fixed' }, origin));
});
test('failed configuration is visible and cannot retain a prior API target', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(String(url), origin + '/preview/pr-40/runtime-config.json');
      assert.equal(options.cache, 'no-store');
      return new Response(JSON.stringify(config));
    };
    await loadPreviewConfig(true, origin + '/preview/pr-40/#/map');
    assert.ok(previewState.config);
    globalThis.fetch = async () => new Response('', { status: 401 });
    await loadPreviewConfig(true, origin + '/preview/pr-40/');
    assert.equal(previewState.config, null);
    assert.match(previewState.error, /401/);
  } finally { globalThis.fetch = original; }
});
test('an old HTML build cannot silently load a new deployment configuration', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify(config));
    await loadPreviewConfig(true, origin + '/staging/', `fe-${sha}-13-1`);
    assert.equal(previewState.config, null);
    assert.match(previewState.error, /刷新/);
    await loadPreviewConfig(true, origin + '/staging/', config.build_id);
    assert.ok(previewState.config);
  } finally { globalThis.fetch = original; }
});
