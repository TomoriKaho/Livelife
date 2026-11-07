import { mkdir, writeFile } from 'node:fs/promises';
import { Resvg } from '@resvg/resvg-js';
import { sketchVector } from './sketch-vector.mjs';
import { deflateSync } from 'node:zlib';

const output = new URL('../src/assets/sketch/default/', import.meta.url);
await mkdir(output, { recursive: true });
const colors = { yellow: '#ffdf32', blue: '#9ac8f2', mint: '#7ec9a8', pink: '#f4b2ab', lavender: '#c9b6f0' };
const records = [];
function chunk(type, data) {
  const body = Buffer.concat([Buffer.from(type), data]);
  let crc = 0xffffffff;
  for (const byte of body) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  const length = Buffer.alloc(4), checksum = Buffer.alloc(4);
  length.writeUInt32BE(data.length); checksum.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
  return Buffer.concat([length, body, checksum]);
}
function texture(color, size, circle = false) {
  const width = size * 3, raw = Buffer.alloc((width * 4 + 1) * width);
  const rgb = color.match(/[a-f\d]{2}/gi).map(hex => Number.parseInt(hex, 16));
  for (let y = 0; y < width; y++) for (let x = 0; x < width; x++) {
    // Integer-period waves tile continuously; seeded pixel grain adds paper tooth.
    let hash = Math.imul(x + 1, 73856093) ^ Math.imul(y + 1, 19349663);
    hash = Math.imul(hash ^ (hash >>> 16), 2246822507);
    hash = Math.imul(hash ^ (hash >>> 13), 3266489909);
    const grain = ((hash ^ (hash >>> 16)) >>> 0) / 0xffffffff;
    const pressure = Math.sin((x * 2 + y * 3) * Math.PI * 2 / width);
    const radius = Math.hypot((x + .5 - width / 2), (y + .5 - width / 2));
    const coverage = circle ? Math.max(0, Math.min(1, width * .40 - radius)) : 1;
    const offset = y * (width * 4 + 1) + 1 + x * 4;
    rgb.forEach((v, i) => { raw[offset + i] = v; });
    const pigment = grain < .15 ? .12 : .64 + grain * .25 + pressure * .06;
    raw[offset + 3] = Math.round(15 * coverage * pigment) * 17;
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width); header.writeUInt32BE(width, 4); header[8] = 8; header[9] = 6;
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), chunk('IHDR', header), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
async function saveTexture(name, color, size, circle = false) {
  const bytes = texture(color, size, circle);
  await writeFile(new URL(`${name}.png`, output), bytes);
  records.push({ name, width: size * 3, height: size * 3, bytes: bytes.length });
}
async function save(name, svg, logicalWidth) {
  const png = new Resvg(String(svg), {
    fitTo: { mode: 'width', value: logicalWidth * 3 },
    font: { loadSystemFonts: false },
  }).render();
  const bytes = png.asPng();
  await writeFile(new URL(`${name}.png`, output), bytes);
  records.push({ name, width: png.width, height: png.height, bytes: bytes.length });
}
await save('outline', sketchVector(), 96);
for (const [color, cast] of Object.entries(colors)) {
  await save(`outline-${color}`, sketchVector({ cast }), 96);
  // Crop away the shape's outer edge; CSS tiles the paper pigment independently
  // from the nine-slice frame, rather than stretching a card-sized texture.
  await saveTexture(`fill-${color}`, cast, 64);
  await saveTexture(`swatch-${color}`, cast, 12, true);
}
await writeFile(new URL('manifest.json', output), `${JSON.stringify({ theme: 'default', scale: 3, assets: records }, null, 2)}\n`);
console.info(`${records.length} static decorations, ${records.reduce((n, r) => n + r.bytes, 0)} PNG bytes`);
