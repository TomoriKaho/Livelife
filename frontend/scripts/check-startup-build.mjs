import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

export function checkStartupBuild(root) {
  const html = readFileSync(path.join(root, 'index.html'), 'utf8');
  const images = [...html.matchAll(/<image\b[^>]*\bhref="([^"]+)"/g)].map(match => match[1]);
  assert.equal(images.length, 2, 'Startup splash must contain both image layers');
  assert.equal(images[0], images[1], 'Startup layers must share one resource');
  assert.match(images[0], /(?:^|\/)assets\/splash-logo-[\w-]+\.webp$/, 'Startup logo must use a hashed asset URL');
  assert.ok(existsSync(path.join(root, 'assets', path.posix.basename(images[0]))), 'Startup image must exist');
  assert.ok(!existsSync(path.join(root, 'splash-logo.webp')), 'Root-level splash image cannot be published');
}
