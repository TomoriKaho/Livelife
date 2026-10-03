// 实景特征的人工配置；轮廓来自 OSM，未标注高度、窗格及屋顶结构为设计近似。
// 参考与精度说明见 MODELING.md；不把程序化细节写回真实地图数据。
export const landmarkProfiles = {
  '444991872': { wall: '#a2a6a2', roof: '#727e79', glass: '#478bb0', height: 17, floors: 4, style: 'science', brick: true },
  '188711087': { wall: '#c3b096', roof: '#566a66', glass: '#436f79', height: 17, floors: 3, style: 'hall', roofRise: 17.8 },
  'r3249649': { wall: '#c2b49f', roof: '#626e6a', glass: '#426779', height: 23, floors: 5, style: 'library' },
  '240825557': { wall: '#c9c5b5', roof: '#6f7774', glass: '#578191', style: 'teaching' },
  '240825556': { wall: '#c1b7a6', roof: '#706e63', glass: '#527b87', style: 'teaching' },
  '226702307': { wall: '#cfbe9e', roof: '#666c63', glass: '#477781', style: 'traditional', height: 10 },
  '240832216': { wall: '#c3ba9f', roof: '#53615b', glass: '#454f49', style: 'traditional', height: 9, brick: true },
  '226703041': { wall: '#bcae93', roof: '#56625b', glass: '#3b5c64', style: 'traditional', height: 10 },
  '240832226': { wall: '#b5a687', roof: '#58605a', glass: '#3c585c', style: 'traditional', height: 9 },
  '226703926': { wall: '#d3c7ac', roof: '#53605b', glass: '#6a4432', style: 'gate', height: 4.8 },
  '240825562': { wall: '#9c8b6e', roof: '#596156', glass: '#423e35', height: 37, style: 'pagoda', scenic: true },
  '33457546': { wall: '#c7c9bd', roof: '#75918d', glass: '#4b808e', height: 19, style: 'gym' },
};
function hash(text) { let n = 0; for (const c of text) n = (n * 31 + c.charCodeAt(0)) >>> 0; return n; }
export function profileFor(b) {
  const historic = ['house', 'bungalow', 'pavilion'].includes(b.kind) || /朗润园|燕南园|[全静备]斋|人文学苑|故居/.test(b.name);
  const walls = ['#b9b3a4', '#cbc2af', '#b3b1a9', '#c2b7a1'];
  const value = { wall: walls[hash(b.id) % walls.length], roof: '#788078', glass: '#577c88',
    height: historic && b.heightSource === 'estimated' ? 4.5 : Math.max(4, Math.min(80, b.height)),
    floors: b.levels || (historic ? 1 : 3), style: historic ? 'traditional' : 'modern', brick: historic,
    ...landmarkProfiles[b.id] };
  if (/^#[0-9a-f]{6}$/i.test(b.wallColor)) value.wall = b.wallColor;
  if (/^#[0-9a-f]{6}$/i.test(b.roofColor)) value.roof = b.roofColor;
  return value;
}
