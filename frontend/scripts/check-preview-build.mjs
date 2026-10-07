// Guard the experimental Vite resource URL hook using the actual built output.
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { checkInternalToolsBuild } from './check-internal-tools-build.mjs';

const root = process.argv[2] ? path.resolve(process.argv[2]) : path.resolve(import.meta.dirname, '../dist');
const ident = process.env.VITE_WEB_BUILD_ID;
assert.match(ident ?? '', /^fe-[0-9a-f]{40}-[1-9][0-9]*-[1-9][0-9]*$/);
const prefix = `/__livelife/web-builds/${ident}/`;
const html = readFileSync(path.join(root, 'index.html'), 'utf8');
assert.ok(html.includes(prefix + 'assets/'), 'HTML must address its immutable build');
let shared = 0;
for (const filename of readdirSync(path.join(root, 'assets'))) {
  if (!/\.(js|css)$/.test(filename)) continue;
  const text = readFileSync(path.join(root, 'assets', filename), 'utf8');
  for (const match of text.matchAll(/\/__livelife\/web-assets\/[A-Za-z0-9_.\-/]+/g)) {
    assert.ok(existsSync(path.join(root, match[0].replace('/__livelife/web-assets/', ''))), match[0]);
    shared++;
  }
}
assert.ok(shared >= 3, 'font and images must use shared URLs');
for (const file of ['assets/maps/campus.json', 'assets/maps/LICENSE.md', 'assets/fonts/Xiaolai-OFL.txt',
  'assets/licenses/Three-MIT.txt']) assert.ok(existsSync(path.join(root, file)), file);
console.log('Preview build resource URLs and licenses verified.');

checkInternalToolsBuild('true', root);
