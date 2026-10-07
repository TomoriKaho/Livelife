import { Capacitor } from '@capacitor/core';
import { previewState } from './runtime-config';

/**
 * Web 平台适配
 *
 * 封装浏览器环境与 Capacitor 原生环境的差异。
 * 首阶段仅实现 Web 分支；后续按需扩展 Android/iOS 路径。
 */

/** 是否为 Capacitor 原生环境 */
export const isNative = (): boolean => {
  return Capacitor.isNativePlatform();
};

/** 获取 API 基地址 */
export const getApiBaseUrl = (): string => {
  if (previewState.enabled) {
    if (!previewState.config) throw new Error('测试配置不可用，请先重新读取配置。');
    return previewState.config.api_base_url;
  }
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
};
