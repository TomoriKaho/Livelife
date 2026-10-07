# 前端 Agent 要求

遵循根目录 AGENTS.md，并阅读 docs/architecture.md、docs/engineering.md 和 docs/testing.md。

- 已确定 Vue 3 + TypeScript + Vite + Vue Router、Canvas 2D + Three.js 和 Capacitor；使用 npm 和锁文件，具体版本由初始化任务验证后固定。首阶段网页演示并验证最小 Android 包，iOS 后续，不采用 uni-app。
- demo 阶段以 design 的明确提交为迁移来源，保留页面专属组件、哈希路由、pageMeta 和手绘效果；新增代码使用 TypeScript，既有 JS/MJS 分批迁移。目标目录见 README，不提前创建无用途的工程。
- 资源迁移保留字体和地图许可证及来源，更新导入与构建路径，移除个人机器绝对路径；公众分发地图保留可见 OSM 署名。
- 首阶段仅 GET /test/hello 真实联调，其他业务使用明确标注的前端样例；接口契约见 docs/architecture.md。Web/原生差异通过 platform/ 适配，Android 地址必须从手机可访问。
- 按接口契约开发；后端未完成时使用明确标识的 Mock，不将模拟结果宣称为真实联调。
- 后端地址通过环境配置提供，不在页面中写死正式域名或私密凭证。
- 处理加载、空数据、错误、权限拒绝和重复操作状态。
- 地图、推送等能力按 Android、iOS、网页分别验证；网页预览不能代表原生能力通过。
- 界面改动提供可复现的测试步骤和结果，记录设备、系统和构建版本；有预览环境时提供链接。PR 无需提交界面截图或录屏。
- 不把服务端密钥打包进客户端；公开 SDK 标识与服务端秘密需明确区分。

- 内部 API 测试、调试面板等使用 `VITE_INTERNAL_TOOLS` 构建开关；development / preview 默认开启，production 必须关闭。新增工具条件动态导入，扩展实际产物检查，验证正式构建剔除模块和请求代码，不以 CSS 隐藏或 `import.meta.env.PROD` 判断代替。
- 使用 `npm run build:preview` 联调；`npm run build:production` 自动检查内部工具已移除。`npm run preview` 只服务上一次 dist。教程见 docs/engineering.md 的“内部调试工具与构建模式”，正式 API 和部署工作流仍待后续接入。
