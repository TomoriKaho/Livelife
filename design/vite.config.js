import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { readFileSync } from 'node:fs';

export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'include-font-license',
      generateBundle() {
        this.emitFile({
          type: 'asset',
          fileName: 'assets/fonts/Xiaolai-OFL.txt',
          source: readFileSync(new URL('./assets/fonts/Xiaolai-OFL.txt', import.meta.url), 'utf8'),
        });
      },
    },
  ],
  base: './',
  server: { host: '127.0.0.1', port: 8765, strictPort: true },
  preview: { host: '127.0.0.1', port: 8766, strictPort: true },
});
