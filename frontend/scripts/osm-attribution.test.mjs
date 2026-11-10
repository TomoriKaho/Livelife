import test from 'node:test';
import assert from 'node:assert/strict';
import { OSM_ATTRIBUTION_TEXT, OSM_COPYRIGHT_URL } from '../src/pages/map/osm-attribution.ts';
test('OSM 署名使用官方版权页与 OSMF 要求的署名文案', () => {
  assert.equal(OSM_COPYRIGHT_URL, 'https://www.openstreetmap.org/copyright');
  assert.match(OSM_COPYRIGHT_URL, /^https:\/\/[^/]*openstreetmap\.org\//);
  assert.equal(OSM_ATTRIBUTION_TEXT, '© OpenStreetMap contributors');
});
