import { readdir, readFile } from 'node:fs/promises';

const assets = new URL('../dist/assets/', import.meta.url);
const files = (await readdir(assets)).filter(name => name.endsWith('.js'));
if (!files.length) throw new Error('Build JavaScript was not found');
const retired = ['livelife-sketch-cache', 'pencil-png-v1', 'pencil-pigment-', 'pencil-nav-mask-', 'warmSketchLayouts'];
for (const file of files) {
  const source = await readFile(new URL(file, assets), 'utf8');
  for (const marker of retired) if (source.includes(marker))
    throw new Error(`${file} still contains retired runtime sketch logic: ${marker}`);
}
console.info(`Static sketch bundle check passed (${files.length} JavaScript chunks)`);
