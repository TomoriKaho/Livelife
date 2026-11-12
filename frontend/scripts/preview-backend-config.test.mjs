import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { validateRuntimeConfig } from '../src/platform/runtime-config.ts';

test('published branch and legacy backend configurations pass the real frontend validator', () => {
  const root = fileURLToPath(new URL('../../', import.meta.url));
  const script = `
import json, sys
sys.path[:0] = ['deploy', 'deploy/tests']
from test_branch_database import published_web_configs
print(json.dumps(published_web_configs()))
`;
  const results = JSON.parse(execFileSync(process.env.PYTHON || 'python3', ['-c', script], {
    cwd: root, encoding: 'utf8', timeout: 30000,
  }));
  assert.equal(results.length, 4);
  for (const { status, expected_sha, mode, config } of results) {
    assert.equal(status, 'ready');
    const validated = validateRuntimeConfig(config, 'https://preview.test');
    assert.equal(validated.backend_sha, expected_sha);
    assert.equal(validated.backend_mode, mode);
    assert.equal(validated.api_base_url, config.api_base_url);
  }
});
