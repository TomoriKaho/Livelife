import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

const root = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  // Existing course-host builds set this before invoking npm run build.
  // Explicit --mode still takes precedence over this compatibility default.
  mode: process.env.VITE_WEB_PREVIEW === 'true' ? 'preview' : undefined,
  plugins: [
    vue(),
    {
      name: 'validate-internal-tools',
      configResolved(config) {
        const flag = config.env.VITE_INTERNAL_TOOLS;
        if (flag !== 'true' && flag !== 'false') {
          throw new Error('VITE_INTERNAL_TOOLS 必须为字符串 true 或 false。');
        }
        if (config.command === 'build' && config.mode === 'production' && flag !== 'false') {
          throw new Error('production 构建必须关闭 VITE_INTERNAL_TOOLS；接口联调用 --mode preview。');
        }
      },
    },
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
