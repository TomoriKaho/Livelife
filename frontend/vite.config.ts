import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

const root = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'include-offline-licenses',
      generateBundle() {
        // 字体许可证
        this.emitFile({
          type: 'asset',
          fileName: 'assets/fonts/Xiaolai-OFL.txt',
          source: readFileSync(new URL('./src/assets/fonts/Xiaolai-OFL.txt', import.meta.url), 'utf8'),
        });
        // 地图许可证与数据
        for (const filename of [
          'LICENSE.md',
          'source.json',
          'campus.json',
          'yanyuan-osm.json',
          'yanyuan-details-osm.json',
          'details-source.json',
        ]) {
          this.emitFile({
            type: 'asset',
            fileName: `assets/maps/${filename}`,
            source: readFileSync(new URL(`./src/assets/maps/${filename}`, import.meta.url)),
          });
        }
        // Three.js 许可证
        this.emitFile({
          type: 'asset',
          fileName: 'assets/licenses/Three-MIT.txt',
          source: readFileSync(new URL('./node_modules/three/LICENSE', import.meta.url)),
        });
      },
    },
  ],
  base: './',
  experimental: {
    renderBuiltUrl(filename) {
      if (process.env.VITE_WEB_PREVIEW === 'true' && /\.(ttf|woff2?|png|jpe?g|webp)$/.test(filename)) {
        return '/__livelife/web-assets/' + filename;
      }
    },
  },
  publicDir: fileURLToPath(new URL('./public', import.meta.url)),
  server: {
    host: '127.0.0.1',
    port: 8765,
    strictPort: true,
  },
  preview: {
    host: '127.0.0.1',
    port: 8766,
    strictPort: true,
  },
});
