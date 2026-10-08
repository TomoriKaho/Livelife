import type { CapacitorConfig } from '@capacitor/cli';
const config: CapacitorConfig = {
  appId: 'io.github.tomorikaho.livelife.dev',
  appName: 'Livelife 测试',
  webDir: 'dist',
  server: { hostname: 'localhost', androidScheme: 'https', cleartext: false },
};
export default config;
