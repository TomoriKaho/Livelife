import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const fontAllow = [root, '/Users/huangkefan/Library/Fonts'];

export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'include-offline-licenses',
      generateBundle() {
        this.emitFile({
          type: 'asset',
          fileName: 'assets/fonts/Xiaolai-OFL.txt',
          source: readFileSync(new URL('./assets/fonts/Xiaolai-OFL.txt', import.meta.url), 'utf8'),
        });
        for (const filename of ['LICENSE.md', 'source.json', 'campus.json', 'yanyuan-osm.json', 'yanyuan-details-osm.json', 'details-source.json']) {
          this.emitFile({ type: 'asset', fileName: `assets/maps/${filename}`, source: readFileSync(new URL(`./assets/maps/${filename}`, import.meta.url)) });
        }
        this.emitFile({ type: 'asset', fileName: 'assets/licenses/Three-MIT.txt', source: readFileSync(new URL('./node_modules/three/LICENSE', import.meta.url)) });
      },
    },
  ],
  base: './',
  publicDir: fileURLToPath(new URL('./public', import.meta.url)),
  server: { host: '127.0.0.1', port: 8765, strictPort: true, fs: { allow: fontAllow } },
  preview: { host: '127.0.0.1', port: 8766, strictPort: true, fs: { allow: fontAllow } },
});
