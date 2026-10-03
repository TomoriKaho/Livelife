import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { readFileSync } from 'node:fs';

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
        for (const filename of ['LICENSE.md', 'source.json', 'campus.json', 'yanyuan-osm.json']) {
          this.emitFile({ type: 'asset', fileName: `assets/maps/${filename}`, source: readFileSync(new URL(`./assets/maps/${filename}`, import.meta.url)) });
        }
        this.emitFile({ type: 'asset', fileName: 'assets/licenses/Three-MIT.txt', source: readFileSync(new URL('./node_modules/three/LICENSE', import.meta.url)) });
      },
    },
  ],
  base: './',
  server: { host: '127.0.0.1', port: 8765, strictPort: true },
  preview: { host: '127.0.0.1', port: 8766, strictPort: true },
});
