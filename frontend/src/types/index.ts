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

/** 兴趣标签目录项，标识与 onboarding/options.js 的 interests 一致 */
export interface InterestTag {
  tag: string;
  label: string;
}

/** 当前用户个人资料，契约见 backend/app/api/profile/API.md */
export interface Profile {
  display_name: string;
  bio: string;
  interests: string[];
}