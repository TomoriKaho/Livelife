import { createHandDrawnRenderer } from '../../sketch.js';

// 同一帧的多个组件更新合并绘制，待 Vue 完成 DOM 更新后再测量。
export function createSketchPlugin() {
  return {
    install(app) {
      const renderer = createHandDrawnRenderer();
      let frame = null;
      const schedule = () => {
        if (frame !== null) return;
        frame = requestAnimationFrame(() => {
          frame = null;
          renderer.refresh();
        });
      };
      app.directive('sketch', {
        mounted: schedule,
        updated: schedule,
        beforeUnmount: element => renderer.release(element),
      });
      // 保留设计文档中的手动刷新接口，常规组件通过 v-sketch 自动刷新。
      window.HandDrawn = renderer;
      app.onUnmount(() => {
        if (frame !== null) cancelAnimationFrame(frame);
        renderer.dispose();
        if (window.HandDrawn === renderer) delete window.HandDrawn;
      });
    },
  };
}
