import test from 'node:test';
import assert from 'node:assert/strict';
import { validateAndroidConfig, androidState, checkAndroidStatus } from '../src/platform/android-config.ts';
import { previewState } from '../src/platform/runtime-config.ts';
const origin = 'https://192.144.253.40', id = 'b'.repeat(32), sha = 'a'.repeat(40);
const config = { schema_version: 1, apk_id: id, build_id: `apk-${id}`, frontend_sha: sha,
  backend_sha: sha, backend_mode: 'fixed', api_base_url: `${origin}/api/versions/be-${sha}/`,
  status_url: `${origin}/downloads/android/build-${id}/status.json`, version_code: 7,
  version_name: '0.1.0-test.7', expires: 1900000000, environment: 'pr-42' };
test('native configuration accepts HTTPS pins without weakening web same-origin rules', () => {
  assert.equal(validateAndroidConfig(config).version_code, 7);
  for (const changes of [{api_base_url:'http://localhost:8000/'}, {backend_sha:'c'.repeat(40)},
    {status_url:`${origin}/wrong`}, {version_code:0}, {version_name:'wrong'}]) {
    assert.throws(() => validateAndroidConfig({...config,...changes}));
  }
});
test('released, expired, mismatched and unreachable packages disable requests instead of falling back', async () => {
  const old = globalThis.fetch;
  androidState.config = config;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({...config,status:'ready'}));
    await checkAndroidStatus(); assert.equal(previewState.config.api_base_url, config.api_base_url);
    for (const changes of [{status:'released'}, {expires:1}, {frontend_sha:'c'.repeat(40)}]) {
      globalThis.fetch = async () => new Response(JSON.stringify({...config,status:'ready',...changes}));
      await assert.rejects(checkAndroidStatus()); assert.equal(previewState.config,null);
    }
    globalThis.fetch = async () => { throw new Error('offline'); };
    await assert.rejects(checkAndroidStatus()); assert.equal(previewState.config,null);
  } finally { globalThis.fetch = old; androidState.config = null; }
});
