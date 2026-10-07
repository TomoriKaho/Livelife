// Inspect actual bundles, including lazy chunks: hiding a button is insufficient.
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export function checkInternalToolsBuild(expected, directory = 'dist') {
  assert.ok(['true', 'false'].includes(expected), 'expected true or false');
  const root = path.resolve(directory);
  assert.ok(readFileSync(path.join(root, 'index.html'), 'utf8').includes('<html'), 'build HTML required');
  const files = readdirSync(root, { recursive: true })
    .filter(file => /\.(js|css|html)$/.test(file));
  for (const marker of ['connection-test-title', '响应格式不符：应返回 message', '.connection-test']) {
    const present = files.filter(file => readFileSync(path.join(root, file), 'utf8').includes(marker));
    assert.equal(present.length > 0, expected === 'true',
      `internal tool ${marker} must be ${expected === 'true' ? 'included' : 'excluded'}; found in ${present.join(', ')}`);
  }
  console.log(`Internal tools bundle check passed: ${expected}.`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [expected, directory] = process.argv.slice(2);
  checkInternalToolsBuild(expected, directory);
}
