import { readFile, writeFile } from 'node:fs/promises';
import { project, contains, center, clipRoad, origin } from '../src/pages/map/geometry.mjs';
const directory = new URL('../assets/maps/', import.meta.url);
const raw = JSON.parse(await readFile(new URL('yanyuan-osm.json', directory), 'utf8'));
const source = JSON.parse(await readFile(new URL('source.json', directory), 'utf8'));
const campus = raw.elements.find(e => e.type === 'way' && e.tags?.amenity === 'university' && e.tags.name === '北京大学' && e.geometry?.length);
if (!campus) throw new Error('OSM 数据缺少北京大学校界，不能退回矩形范围');
const boundary = campus.geometry.map(project);
const buildings = [], roads = [], water = [], green = [];
const [south, west, north, east] = source.bbox;
const extent = [[west, south], [east, south], [east, north], [west, north]].map(([lon, lat]) => project({ lon, lat }));
const context = { extent, buildings: [], roads: [], water: [], green: [] };
for (const e of raw.elements) {
  if (e.type !== 'way' || !e.geometry?.length || e.id === campus.id) continue;
  const points = e.geometry.map(project), tags = e.tags || {};
  if (tags.highway) {
    const width = ['primary', 'secondary', 'tertiary', 'residential', 'service'].includes(tags.highway) ? 5 : 2;
    roads.push(...clipRoad(points, boundary).map(points => ({ points, width })));
    // 场景渲染这一整套道路，避免校界处截断，也避免与校内道路重复绘制。
    context.roads.push(...clipRoad(points, extent).map(points => ({ points, width })));
  }
  const inCampus = contains(center(points), boundary);
  if (!inCampus && !contains(center(points), extent)) continue;
  const area = inCampus ? { buildings, water, green } : context;
  if (tags.building && tags.building !== 'no') {
    const levels = Number.parseInt(tags['building:levels'], 10);
    const height = Number.parseFloat(tags.height);
    area.buildings.push({ id: String(e.id), name: tags.name || '', points, height: Number.isFinite(height) ? height : (Number.isFinite(levels) ? levels : 3) * 3.8, levels: Number.isFinite(levels) ? levels : null });
  } else if (tags.natural === 'water' || tags.water || tags.landuse === 'reservoir') area.water.push({ name: tags.name || '', points });
  else if (['grass', 'meadow', 'forest'].includes(tags.landuse) || ['wood', 'grassland', 'scrub'].includes(tags.natural) || ['garden', 'park', 'pitch'].includes(tags.leisure)) area.green.push({ points });
}
// 四舍五入到分米；足够设计展示，减小离线资源体积。
const data = JSON.parse(JSON.stringify({ origin, boundary, buildings, roads, water, green, context, attribution: '© OpenStreetMap contributors', license: 'ODbL 1.0', dataTimestamp: raw.osm3s.timestamp_osm_base }, (_, value) => typeof value === 'number' ? Math.round(value * 10) / 10 : value));
// 经纬度原点不应跟随米制坐标取整。
data.origin = origin;
await writeFile(new URL('campus.json', directory), JSON.stringify(data));
console.log(`燕园校界内：${buildings.length} 栋建筑、${roads.length} 条道路段、${water.length} 处水面。已写入 campus.json。`);
console.log(`周边背景：${context.buildings.length} 栋实际 OSM 建筑；渲染道路共 ${context.roads.length} 段。`);
