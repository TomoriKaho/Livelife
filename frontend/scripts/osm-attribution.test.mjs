import test from 'node:test';
import assert from 'node:assert/strict';
import { OSM_ATTRIBUTION_TEXT, OSM_COPYRIGHT_URL } from '../src/pages/map/osm-attribution.ts';
import { drawerHeights } from '../src/pages/map/drawer-gesture.mjs';

test('OSM 署名使用官方版权页与 OSMF 要求的署名文案', () => {
  assert.equal(OSM_COPYRIGHT_URL, 'https://www.openstreetmap.org/copyright');
  assert.match(OSM_COPYRIGHT_URL, /^https:\/\/[^/]*openstreetmap\.org\//);
  assert.equal(OSM_ATTRIBUTION_TEXT, '© OpenStreetMap contributors');
});

// 抽屉 bottom 固定为 nav 高度，顶边 = shell - nav - height。
// expanded 时顶边正好等于 header，即页眉下沿，与 .map-stage 顶部齐平，
// 地图（含右下角署名）被完整遮挡 —— 这是展开档需要第二份署名的依据。
test('仅展开档完整覆盖地图，隐藏与默认档仍露出地图署名', () => {
  const shell = 844, header = 76, nav = 86;
  const heights = drawerHeights(shell, header, nav);
  const topEdge = state => shell - nav - heights[state];
  assert.equal(heights.expanded, shell - header - nav);
  assert.equal(topEdge('expanded'), header);
  assert.ok(topEdge('middle') > header, '默认档顶边低于页眉，地图署名可见');
  assert.ok(topEdge('hidden') > header, '隐藏档顶边低于页眉，地图署名可见');
});

test('窄屏下展开档同样完整覆盖地图', () => {
  const shell = 568, header = 64, nav = 78;
  const heights = drawerHeights(shell, header, nav);
  assert.equal(shell - nav - heights.expanded, header);
  assert.ok(shell - nav - heights.middle > header);
});
