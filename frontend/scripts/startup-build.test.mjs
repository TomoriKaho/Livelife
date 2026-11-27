import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { checkStartupBuild } from './check-startup-build.mjs';

test('startup resource accepts local, immutable and shared URLs and rejects unpublishable output', () => {
  const root = mkdtempSync(path.join(tmpdir(), 'startup-build-'));
  try {
    mkdirSync(path.join(root, 'assets'));
    const logo = path.join(root, 'assets/splash-logo-test1234.webp');
    writeFileSync(logo, 'synthetic asset');
    const index = url => writeFileSync(path.join(root, 'index.html'), `<image href="${url}"/><image href="${url}"/>`);
    for (const prefix of ['./', '/__livelife/web-builds/fe-test/', '/__livelife/web-assets/']) {
      index(prefix + 'assets/splash-logo-test1234.webp');
      checkStartupBuild(root);
    }
    index('./splash-logo.webp');
    assert.throws(() => checkStartupBuild(root), /hashed asset URL/);
    index('./assets/splash-logo-test1234.webp');
    writeFileSync(path.join(root, 'splash-logo.webp'), 'unpublishable duplicate');
    assert.throws(() => checkStartupBuild(root), /Root-level/);
    rmSync(path.join(root, 'splash-logo.webp'));
    rmSync(logo);
    assert.throws(() => checkStartupBuild(root), /must exist/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
