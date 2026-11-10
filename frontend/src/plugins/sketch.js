import { createStaticSketchRenderer } from './static-sketch';
import './static-sketch.css';

export function createSketchPlugin() {
  return {
    install(app) {
      const renderer = createStaticSketchRenderer();
      app.directive('sketch', {
        mounted: element => renderer.update(element),
        updated: element => renderer.update(element),
        beforeUnmount: element => renderer.release(element),
      });
    },
  };
}
