import { demoLocation } from './demo.js';

// 无有效定位时的初始视角；取得设备位置后保持相同的观看高度和距离。
export const initialView = {
  target: [demoLocation[0], 0, demoLocation[1]],
  offset: [165, 95, 110],
};
