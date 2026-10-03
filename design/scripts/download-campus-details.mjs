import { readFile, writeFile } from 'node:fs/promises';

// 只在显式运行时联网。补齐原快照 out tags 丢失的 relation 成员与真实树点。
const directory = new URL('../assets/maps/', import.meta.url);
const { bbox } = JSON.parse(await readFile(new URL('source.json', directory), 'utf8'));
const query = `[out:json][timeout:120];(relation[type=multipolygon][building](${bbox.join(',')});node[natural=tree](${bbox.join(',')});way[natural=tree_row](${bbox.join(',')}););out body geom;`;
const endpoint = 'https://overpass-api.de/api/interpreter';
const response = await fetch(endpoint, {
  method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'LiveLifeDesign/0.1 (offline campus UI prototype)' },
  body: new URLSearchParams({ data: query }), signal: AbortSignal.timeout(180000),
});
if (!response.ok) throw new Error(`Overpass HTTP ${response.status}: ${(await response.text()).slice(0, 500)}`);
const raw = await response.json();
if (raw.remark || !raw.elements?.length) throw new Error(raw.remark || '没有有效补充要素');
await writeFile(new URL('yanyuan-details-osm.json', directory), JSON.stringify(raw));
await writeFile(new URL('details-source.json', directory), JSON.stringify({
  downloadedAt: new Date().toISOString(), endpoint, bbox, query,
  dataTimestamp: raw.osm3s?.timestamp_osm_base,
  attribution: '© OpenStreetMap contributors', license: 'ODbL 1.0',
}, null, 2));
console.log(`已保存 ${raw.elements.length} 个补充 OSM 要素`);
