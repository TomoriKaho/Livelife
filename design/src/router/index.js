import { createRouter, createWebHashHistory } from 'vue-router';

// 每个页面自己维护元数据；新增页面无需编辑一份共享路由清单。
const modules = import.meta.glob('../pages/*Page.vue', { eager: true });
export const pages = Object.entries(modules)
  .map(([file, module]) => {
    if (!module.pageMeta?.key || !module.pageMeta?.id) {
      throw new Error(`${file} 必须导出包含 key、id 的 pageMeta`);
    }
    return { ...module.pageMeta, component: module.default };
  })
  .sort((a, b) => a.id.localeCompare(b.id));

const keys = pages.map(page => page.key);
if (new Set(keys).size !== keys.length) throw new Error('页面的 pageMeta.key 不可重复');

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/map' },
    ...pages.map(({ component, ...meta }) => ({ path: `/${meta.key}`, name: meta.key, component, meta })),
    { path: '/:pathMatch(.*)*', redirect: '/map' },
  ],
});
