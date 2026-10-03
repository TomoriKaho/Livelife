import { readFile, writeFile } from 'node:fs/promises';
import { project, contains, center, clipRoad, origin } from '../src/pages/map/geometry.mjs';
const directory = new URL('../assets/maps/', import.meta.url);
const raw = JSON.parse(await readFile(new URL('yanyuan-osm.json', directory), 'utf8'));
const campus = raw.elements.find(e => e.type === 'way' && e.tags?.amenity === 'university' && e.tags.name === '北京大学' && e.geometry?.length);
if (!campus) throw new Error('OSM 数据缺少北京大学校界，不能退回矩形范围');
const boundary = campus.geometry.map(project);
const buildings = [], roads = [], water = [], green = [];
for (const e of raw.elements) {
  if (e.type !== 'way' || !e.geometry?.length || e.id === campus.id) continue;
  const points = e.geometry.map(project), tags = e.tags || {};
  if (tags.highway) roads.push(...clipRoad(points, boundary).map(points => ({ points, width: ['primary', 'secondary', 'tertiary', 'residential', 'service'].includes(tags.highway) ? 5 : 2 })));
  if (!contains(center(points), boundary)) continue;
  if (tags.building && tags.building !== 'no') {
    const levels = Number.parseInt(tags['building:levels'], 10);
    const height = Number.parseFloat(tags.height);
    buildings.push({ id: String(e.id), name: tags.name || '', points, height: Number.isFinite(height) ? height : (Number.isFinite(levels) ? levels : 3) * 3.8, levels: Number.isFinite(levels) ? levels : null });
  } else if (tags.natural === 'water' || tags.water || tags.landuse === 'reservoir') water.push({ name: tags.name || '', points });
  else if (['grass', 'meadow', 'forest'].includes(tags.landuse) || ['wood', 'grassland', 'scrub'].includes(tags.natural) || ['garden', 'park', 'pitch'].includes(tags.leisure)) green.push({ points });
}
// 四舍五入到分米；足够设计展示，减小离线资源体积。
const data = JSON.parse(JSON.stringify({ origin, boundary, buildings, roads, water, green, attribution: '© OpenStreetMap contributors', license: 'ODbL 1.0', dataTimestamp: raw.osm3s.timestamp_osm_base }, (_, value) => typeof value === 'number' ? Math.round(value * 10) / 10 : value));
// 经纬度原点不应跟随米制坐标取整。
data.origin = origin;
await writeFile(new URL('campus.json', directory), JSON.stringify(data));
console.log(`燕园校界内：${buildings.length} 栋建筑、${roads.length} 条道路段、${water.length} 处水面。已写入 campus.json。`);
