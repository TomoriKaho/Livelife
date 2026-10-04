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

## 手机真机预览

电脑与手机连接同一个局域网（电脑可以接同一路由器的网线）。在 `design/` 下执行：

```powershell
npm run build
npm run preview:phone
```

用手机浏览器打开终端输出的 `Network` 地址，追加 `/#/map` 即可进入活动地图。电脑需保持开机、预览进程保持运行。地址随电脑所在网络变化；`localhost` 和 `127.0.0.1` 只能用于电脑本机。

更新设计后重新执行 `npm run build` 并刷新手机页面。需要边改边在手机上看时，可将现有开发服务停止后执行 `npm run dev -- --host 0.0.0.0`，手机访问其 `Network` 地址即可热更新。手机浏览器可用「添加到主屏幕」保存入口。

如果手机打不开，先确认使用同一路由器且没有开启访客网络隔离；若 Windows 弹出网络访问提示，选择允许当前私有网络。该方式是局域网预览，不会发布到公网。

## 页面分工

| 界面 | 独立页面文件 | 地址 |
| --- | --- | --- |
| D-01 登录、授权与兴趣引导 | [OnboardingPage.vue](./src/pages/OnboardingPage.vue)（子组件在 `src/pages/onboarding/`） | `#/onboarding` |
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

- 每个页面自行导出 `pageMeta`，路由自动收集顶层 `*Page.vue`；补全已有页面不需要改共享路由表。
- 不在每个页面复制页眉、Tab、字体或纹理算法；通过共享组件与指令复用。
- 页面样式优先 scoped。`styles.css`、`sketch.js` 和 `src/components/` 的公共修改集中协调，并同步 DESIGN.md。
- 保留并提交 `package-lock.json`，使用 `npm ci`；不提交 `node_modules/` 和 `dist/`。
- 新增路由文件必须导出唯一的 `pageMeta.key` 和 `id`；当前保留七个业务页面和五项 Tab，统一样式规范由 `DESIGN.md` 维护。

字体本地加载，许可证在 `assets/fonts/`，构建时会携带当前字体的 OFL 文件。

## 活动地图

D-02 已加入本地燕园 3D 地图、建筑聚焦与楼层悬空展示，并细化了彩色立面、窗格、地标屋顶、博雅塔、湖岸与树冠。界面元素、issue 对应关系和离线更新步骤见 [地图设计说明](./src/pages/map/README.md)；模型来源、精度边界和文件分工见 [建模说明](./src/pages/map/MODELING.md)。地图启动时不连接外部地图服务；2D 当前留白。

## 我的

D-07 已补充个人资料、兴趣小档案、收藏列表，以及账户与隐私、通知与定位、界面风格、帮助与反馈入口。不显示开头的“我的”标题，直接展示资料。数据和示例交互全部留在前端；需求对应、组件分工和演示边界见 [个人页面设计说明](./src/pages/more/README.md)。
