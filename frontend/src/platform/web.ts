/**
 * Web 平台适配
 *
 * 封装浏览器环境与 Capacitor 原生环境的差异。
 * 首阶段仅实现 Web 分支；后续按需扩展 Android/iOS 路径。
 */

/** 是否为 Capacitor 原生环境 */
export const isNative = (): boolean => {
  return false; // 首阶段均为 Web
};

/** 获取 API 基地址 */
export const getApiBaseUrl = (): string => {
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
};