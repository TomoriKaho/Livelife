# LiveLife 手机端设计原型

使用 Vue 3 单文件组件、Vue Router 4 哈希路由和 Vite。完整视觉规范见 [DESIGN.md](./DESIGN.md)。

## 启动与构建

需要 Node.js `^20.19.0 || >=22.12.0`。在仓库根目录执行：

```powershell
cd design
npm ci
npm run dev
```

访问 [开发预览](http://127.0.0.1:8765/)。保存 `.vue` 文件后会自动更新。

```powershell
npm run build
npm run preview
```

构建结果位于 `dist/`，预览地址为 [构建预览](http://127.0.0.1:8766/)。端口被占用时先停止旧预览服务，或使用 `npm run dev -- --port 8767`。原来的 Python 源目录预览方式已改为 Vite；Python 等静态服务器可用于 `dist/`。

## 页面分工

| 界面 | 独立页面文件 | 地址 |
| --- | --- | --- |
| D-00 设计规范与组件库 | [DesignSystemPage.vue](./src/pages/DesignSystemPage.vue) | `#/system` |
| D-01 授权与兴趣引导 | [OnboardingPage.vue](./src/pages/OnboardingPage.vue) | `#/onboarding` |
| D-02 地图主页 | [MapPage.vue](./src/pages/MapPage.vue) | `#/map` |
| D-03 信息详情 | [DetailPage.vue](./src/pages/DetailPage.vue) | `#/detail` |
| D-04 日历与活动列表 | [CalendarPage.vue](./src/pages/CalendarPage.vue) | `#/calendar` |
| D-05 兴趣推荐 | [InterestsPage.vue](./src/pages/InterestsPage.vue) | `#/interests` |
| D-06 Agent 对话 | [AgentPage.vue](./src/pages/AgentPage.vue) | `#/agent` |
| D-07 其他功能 | [MorePage.vue](./src/pages/MorePage.vue) | `#/more` |

`index.html` 只负责挂载 Vue。页面内容、逻辑、专属样式放在对应文件中；公共框架已由 `App.vue` 与 `src/components/` 提供。

## 补全一个页面

1. 打开负责的 `src/pages/*Page.vue`，在本文件的 `pageMeta` 调整标题、眉题、强调色等元数据。
2. 用本页内容替换模板中的 `<PagePlaceholder :page="pageMeta" />`。保持一个主要内容容器，与共享页眉、标题、页脚、Tab 配合布局。
3. 页面逻辑放在 `<script setup>`；专属样式放在 `<style scoped>`，继承公共字体和颜色。页面子组件可放在 `src/pages/<页面名>/`。
4. 需要手绘勾线时使用 `.sketch` 加 `v-sketch`；需要彩铅平涂时再设置 `data-pencil="yellow|blue|mint|pink|lavender"`。显式使用透明背景，给内容留内边距。
5. 在 320px 和常规手机宽度检查排版，运行 `npm run build`，按 DESIGN.md 验收公共风格。

```vue
<article v-sketch class="sketch pencil-fill activity-card" data-pencil="mint">
  <h2>活动标题</h2>
  <p>活动说明</p>
</article>
```

样式示例：`.activity-card { background: transparent; padding: 16px; }`。业务文字字号、行距与状态按实际内容设计。

## 减少并行编辑冲突

- 每个页面自行导出 `pageMeta`，路由与页面目录自动收集顶层 `*Page.vue`；补全已有页面不需要改共享路由表。
- 不在每个页面复制页眉、Tab、字体或纹理算法；通过共享组件与指令复用。
- 页面样式优先 scoped。`styles.css`、`sketch.js` 和 `src/components/` 的公共修改集中协调，并同步 DESIGN.md。
- 保留并提交 `package-lock.json`，使用 `npm ci`；不提交 `node_modules/` 和 `dist/`。
- 新增路由文件必须导出唯一的 `pageMeta.key` 和 `id`；当前八页五项 Tab 的范围保持 issue #13 的约定。

字体本地加载，许可证在 `assets/fonts/`，构建时会携带当前字体的 OFL 文件。

## 活动地图

D-02 已加入本地燕园 3D 地图、建筑聚焦与楼层悬空展示。界面元素、issue 对应关系、模型与演示信息的边界、离线数据更新步骤见 [地图设计说明](./src/pages/map/README.md)。地图启动时不连接外部地图服务；2D 当前留白。
