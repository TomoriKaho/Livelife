import { mkdir, writeFile } from 'node:fs/promises';

// 仅在设计人员显式执行此脚本时访问网络；启动与构建不会触发下载。
const bbox = [39.982, 116.296, 40.003, 116.321];
const query = `[out:json][timeout:120];(
  way[building](${bbox.join(',')});
  way["building:part"](${bbox.join(',')});
  way[highway](${bbox.join(',')});
  way[natural](${bbox.join(',')});
  way[landuse](${bbox.join(',')});
  way[leisure](${bbox.join(',')});
  way[water](${bbox.join(',')});
  way[amenity=university][name="北京大学"](${bbox.join(',')});
  relation[amenity=university][name="北京大学"](${bbox.join(',')});
  relation[type=multipolygon][building](${bbox.join(',')});
  relation[type=multipolygon][natural=water](${bbox.join(',')});
);out body geom;`;

const endpoint = 'https://overpass-api.de/api/interpreter';
const response = await fetch(endpoint, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'LiveLifeDesign/0.1 (offline campus UI prototype)' },
  body: new URLSearchParams({ data: query }),
  signal: AbortSignal.timeout(180000),
});
if (!response.ok) throw new Error(`Overpass HTTP ${response.status}: ${(await response.text()).slice(0, 300)}`);
const raw = await response.json();
if (raw.remark) throw new Error(raw.remark);
if (!raw.elements?.length) throw new Error('地图响应没有要素');
const directory = new URL('../src/assets/maps/', import.meta.url);
await mkdir(directory, { recursive: true });
await writeFile(new URL('yanyuan-osm.json', directory), JSON.stringify(raw));
await writeFile(new URL('source.json', directory), JSON.stringify({
  downloadedAt: new Date().toISOString(), endpoint, bbox, query,
  attribution: '© OpenStreetMap contributors',
  copyrightUrl: 'https://www.openstreetmap.org/copyright',
  license: 'ODbL 1.0',
  dataTimestamp: raw.osm3s?.timestamp_osm_base,
}, null, 2));
console.log(`已保存 ${raw.elements.length} 个 OSM 要素至 assets/maps/yanyuan-osm.json`);
await import('./download-campus-details.mjs');
await import('./prepare-campus-map.mjs');
