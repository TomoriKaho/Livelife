# 前端开发

客户端使用 Vue 3、TypeScript、Vite 和 Vue Router，地图使用 Canvas 2D 与 Three.js，Android 使用 Capacitor。整体方案见[架构说明](../docs/architecture.md#技术栈与实施阶段)。

- [运行环境与安装](#运行环境与安装)
- [API 地址与联调](#api-地址与联调)
- [构建、预览与检查](#构建预览与检查)
- [内部调试工具与构建模式](#内部调试工具与构建模式)
- [手绘 UI 渲染](src/plugins/README.md)与[装饰缓存](src/platform/SKETCH_CACHE.md)
- [Android 开发与测试](../docs/testing.md#android-测试包操作)

## 运行环境与安装

使用符合 `frontend/package.json` 的 Node.js：`^20.19.0 || >=22.12.0`，并使用随 Node.js 提供的 npm。可从 [Node.js 官网](https://nodejs.org/) 安装满足范围的版本。网页检查/构建在 Ubuntu 24.04 课程机执行，固定 Node.js `24.13.0` 和 npm `11.6.2`，按 package-lock.json 安装。建议成员使用同一版本。完整行为测试会直接导入 `.ts`，还需要 Node 的原生 TypeScript 支持；满足 Vite 的 engines 范围不等于能运行全部测试。Node 24.13.0 是已验证的推荐环境，不限定为唯一补丁版本。

从仓库根目录执行：

```bash
node --version
npm --version
cd frontend
npm ci
test -f .env || cp .env.example .env
npm run dev
```

首次配置时复制环境变量样例；已有 `.env` 时保留自己的配置。开发入口为 `http://127.0.0.1:8765/`，哈希路由默认进入引导页。点击“登录并进入”进入样例地图，无需真实账号。`vite.config.ts` 使用严格端口，8765 被占用时启动失败；可停止自己的旧预览，或执行 `npm run dev -- --port 8775` 指定空闲端口。

## API 地址与联调

在 `.env` 或 `.env.local` 中设置公开配置 `VITE_API_BASE_URL`；本地默认 `http://localhost:8000`。后端的安装、监听和 CORS 见[后端 README](../backend/README.md#cors-与浏览器联调)。接口字段及客户端成功/失败判断见 [API 文档](../docs/api.md)。

Vite 在启动或构建时读取变量；修改后重启开发服务，或重新构建。变量会进入浏览器产物，只能保存公开配置。当前没有 Vite API 代理，浏览器直接请求基地址。

开发及 preview 构建的“我的 → 帮助与反馈 → 接口连通性测试”显示后端地址。点击“测试连接”发起真实 hello 请求，加载期间禁用重复点击。页面不可达先检查前端端口；页面可访问但连接失败时检查后端监听、API 地址和实际网页 Origin。自定义前端端口需同步后端 CORS 白名单。

手机中的 localhost 指向手机自身。手机浏览器的局域网 Origin 需另外配置，Android 本地同步及 HTTPS 地址配置见[Android 教程](../docs/testing.md#2-本地运行到手机或模拟器)。

## 构建、预览与检查

以下命令均在 frontend/ 执行：

```bash
npm run build:preview
npm run preview
```

`build:preview` 先运行 `vue-tsc -b` 类型检查，再执行开启接口测试工具的 Vite preview 模式构建，产物位于 `frontend/dist/`。`preview` 提供本地构建预览 `http://127.0.0.1:8766/`；它要求先构建，不是正式生产服务器。预览端口也为严格端口，可用 `npm run preview -- --port 8776` 指定其他空闲端口。

现有检查与地图命令：

```bash
node --test scripts/*.test.mjs
# 也可以按模块运行：
npm run test:map
npm run test:plan
npm run test:drawer
npm run test:composer
npm run test:favorites

# 从已提交的离线快照重新生成 campus.json，不访问网络：
npm run map:prepare
# 主动访问 Overpass、更新两套快照并重新生成地图：
# npm run map:download
```

地图脚本读写 `src/assets/maps/`；下载会修改快照，普通页面演示和构建无需下载。当前没有独立格式或 lint 脚本。依赖、dist、`.env` 等忽略规则见 `frontend/.gitignore`；TypeScript 构建可能产生 `tsconfig.tsbuildinfo`，属于本地缓存，不应提交。

## 内部调试工具与构建模式

同一份源码通过构建配置生成不同产物。代码分支负责协作，Vite mode 负责选择客户端构建配置，部署环境负责 API 配对；不为测试按钮维护独立的业务代码分支。

| 模式 | 配置文件 | `VITE_INTERNAL_TOOLS` 默认值 | 操作 |
| --- | --- | --- | --- |
| development | frontend/.env.development | true | `npm run dev`，本地开发 |
| preview | frontend/.env.preview | true | `npm run build:preview`，本地测试构建及服务器预览 |
| production | frontend/.env.production | false | `npm run build:production`，移除内部工具的候选产物 |

这三个文件只存公开、非敏感的模式配置并提交 Git。`.env` / `.env.local` 留给本机配置。通常只需按 `.env.example` 配置 API 地址，不必手动设置内部工具开关。mode 专属文件优先于通用 `.env`；执行命令时已有的同名环境变量优先级最高。开关按字符串 `true` / `false` 解析，不能用 `Boolean('false')`。

从 frontend/ 执行完整测试构建教程：

```bash
npm ci
npm run build:preview
npm run check:internal-tools -- true
npm run preview
```

打开 `http://127.0.0.1:8766/`，进入样例 → 我的 → 帮助与反馈，应显示接口连通性测试。按 API 联调章节启动后端并测试 hello。`npm run preview` 仅提供已生成的文件，不选择构建模式，也不会替你重新构建。

验证移除内部工具的候选产物：

```bash
npm run build:production
npm run preview
```

`build:production` 自动检查输出 JS/CSS/HTML，包括异步 chunk，确认测试组件和 hello 测试请求代码的标记均不在产物中。浏览器刷新后进入帮助页，仍有正常帮助内容，接口测试、内部版本信息和测试按钮均不出现。每次构建会替换 dist；测试报告必须记录模式和提交 SHA，不能把旧浏览器页或上一次构建当成新结果。

普通 `npm run build` 默认使用 production。现有课程机构建在进程环境设置 `VITE_WEB_PREVIEW=true`，Vite 因此默认选择 preview，保留旧构建命令兼容；显式 `--mode` 优先。`VITE_WEB_PREVIEW` 控制网关资源路径与 runtime-config.json，`VITE_INTERNAL_TOOLS` 控制用户可见的内部工具，二者不是同一开关。仅选择 preview mode 不会强制读取服务器配置，便于本地静态联调。

临时隐藏本地工具可运行 `VITE_INTERNAL_TOOLS=false npm run dev`，停止后再次正常启动恢复默认。构建时值为空、拼错或 production 模式强行开启工具会报错，修正配置后重试。不要在通用 `.env` 固定启用工具，避免影响其他模式。

新增调试功能按下面的规则实施：

1. API 探针、后端选择、内部版本面板等开发入口放在独立组件中，不加入普通用户流程。
2. 在统一开关为 true 时条件动态导入并渲染组件。业务 API 请求与业务权限逻辑独立维护，不能受调试开关影响。
3. 配套扩展产物检查中的独有标记，分别验证 preview 存在、production 不存在；关闭时调试模块、请求代码与专属样式均应从构建产物移除。
4. 不使用 CSS 隐藏代替构建剔除，不在运行时网页配置里重新启用正式包已移除的工具。`import.meta.env.PROD` 仅指优化构建，preview 同样可为 true，不能据此区分用户版与测试版。
5. PR 记录两种构建的真实结果和必要浏览器步骤，成员正式评审按贡献流程执行。

当前 production 只是关闭内部工具的客户端构建，仍含样例业务数据；不代表已接正式 API、已完成业务验收或已建立正式部署。正式 API 配置、版本元数据、签名与发布工作流在对应后续任务接入。未来构建复用必须同时核对 SHA、客户端目标与构建模式，不能把同一 SHA 的 preview 包当成 production 包。

参考：[Vite 环境变量与模式](https://vite.dev/guide/env-and-mode)。

## 目录与模块

客户端迁移基线为 design 分支 `4d95af0`，后续业务实现维护在 frontend；design 保留为原型参考。

| 位置 | 用途 |
| --- | --- |
| src/pages/ | 页面及页面专属子组件；保留哈希路由和 pageMeta 元数据 |
| src/components/ | 跨页面公共组件 |
| src/api/、src/types/ | 请求、API 配置、错误处理及接口类型 |
| src/data/ | 明确标注的演示数据 |
| src/platform/ | Web / 原生能力适配 |
| src/plugins/ | 手绘等 Vue 插件 |
| src/assets/ | 地图、字体和图片，保留来源与许可证 |
| scripts/ | 资源处理、构建校验和行为测试 |
| android/ | Capacitor Android 工程；iOS 后续创建 |

新增业务、接口和平台代码使用 TypeScript，既有 JS/MJS 逐批迁移。页面专属组件留在对应页面目录。资源迁移同步导入、许可证输出和处理脚本，移除个人机器路径；地图分发保留可见 OSM 署名。

模块说明：[手绘 UI](src/plugins/README.md)、[装饰缓存](src/platform/SKETCH_CACHE.md)、[地图](src/pages/map/README.md)、[建模](src/pages/map/MODELING.md)、[Agent 页面](src/pages/agent/README.md)、[个人页](src/pages/more/README.md)、[字体](src/assets/fonts/README.md)、[地图许可](src/assets/maps/LICENSE.md)。

## 手机网页与原生工程

手机浏览器预览先构建，再执行 `npm run preview:phone`，使用电脑局域网 IP 和 8766 端口访问；网络与防火墙需允许连接。Android 工程位于 android/，SDK、IDE、本地 debug 和分发包步骤见[Android 教程](../docs/testing.md#android-测试包操作)。网页演示的数据边界见[架构说明](../docs/architecture.md#首阶段结构与数据边界)。
