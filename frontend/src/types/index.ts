/** 页面元数据 —— 每个 Page.vue 必须导出 pageMeta */
export interface PageMeta {
  /** 路由 hash，如 "map" */
  key: string;
  /** 排序 id */
  id: string;
  /** 页面标题 */
  title?: string;
  /** 底部导航高亮项 */
  nav?: string;
  /** 是否全屏（隐藏页眉和底部导航） */
  shell?: 'focus';
  /** 是否沉浸模式 */
  immersive?: boolean;
  /** 自定义页眉 */
  customHeading?: boolean;
  /** 显示页眉 */
  heading?: boolean;
  /** 显示页脚 */
  footer?: boolean;
}

/** 后端 hello 接口响应 */
export interface HelloResponse {
  message: string;
}