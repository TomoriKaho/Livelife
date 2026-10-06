import type { RouteRecordRaw } from 'vue-router';
import type { DefineComponent } from 'vue';
import { createRouter, createWebHashHistory } from 'vue-router';
import type { PageMeta } from '../types';

type PageModule = {
  default: DefineComponent<object, object, unknown>;
  pageMeta?: PageMeta;
};

// 每个页面自己维护元数据；新增页面无需编辑一份共享路由清单。
const modules = import.meta.glob<PageModule>('../pages/*Page.vue', { eager: true });
const pages = Object.entries(modules)
  .map(([file, module]) => {
    if (!module.pageMeta?.key || !module.pageMeta?.id) {
      throw new Error(`${file} 必须导出包含 key、id 的 pageMeta`);
    }
    return { ...module.pageMeta, component: module.default };
  })
  .sort((a, b) => a.id.localeCompare(b.id));

const keys = pages.map((page) => page.key);
if (new Set(keys).size !== keys.length) throw new Error('页面的 pageMeta.key 不可重复');

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/onboarding' },
  { path: '/login', redirect: '/onboarding' },
  ...pages.map(({ component, ...meta }) => ({
    path: `/${meta.key}` as const,
    name: meta.key,
    component,
    meta,
  })),
  { path: '/:pathMatch(.*)*', redirect: '/map' },
];

export default createRouter({
  history: createWebHashHistory(),
  routes,
});