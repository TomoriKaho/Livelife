/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<object, object, unknown>;
  export default component;
}

interface ImportMetaEnv {
  /** 后端 API 基地址，如 http://localhost:8000 */
  readonly VITE_API_BASE_URL: string;
  readonly VITE_WEB_PREVIEW?: string;
  readonly VITE_WEB_BUILD_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
