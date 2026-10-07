# 工程规范

## 技术栈与实施阶段

技术路线由 [Issue #19](https://github.com/TomoriKaho/Livelife/issues/19) 确认，frontend/ 已初始化网页客户端，backend/ 已实现本地 hello 接口；业务后端及原生工程仍待实现。选型、实现和验证状态分别记录，不将待引入组件描述为已运行服务。

| 层次 | 确定方案 | 实施阶段与用途 |
| --- | --- | --- |
| 客户端 | Vue 3 + TypeScript + Vite + Vue Router | 首阶段网页与移动布局；npm 管理依赖并提交 package-lock.json |
| 地图 | Canvas 2D + Three.js | 首阶段复用离线校园地图；2D 作为低性能设备的可选入口 |
| APP | Capacitor | 同一前端支持 Android/iOS；首阶段最小 Android 包，iOS 后续 |
| API | Python + FastAPI + Pydantic | 已实现本地 hello 接口及响应校验；业务接口后续引入 |
| 数据库 | PostgreSQL + SQLAlchemy + Alembic | 业务持久化阶段引入；首阶段不启动数据库 |
| 后台任务 | 独立 Python worker | 后续采集与推荐；不依赖手机后台运行 |
| 部署 | Python venv + Supervisor；Nginx + SSH 隧道 | 课程机普通用户直接运行后端，公网机提供 HTTPS；#29 实施 |

检索先基于真实中文校园内容验证分词与召回；pgvector、Redis + Celery、LLM 服务、登录及推送供应商待专项确认。本次不新增状态管理库、地图在线 SDK 或微服务体系。

### 客户端选择依据

最终目标为 APP，网页是开发和演示入口。design 原型采用标准 Vue 页面、Vue Router、DOM/SVG 手绘效果、Canvas 2D 和 Three.js。Vue + Capacitor 可继续沿用 Web 实现，再通过原生插件接入系统能力；uni-app 和 Flutter 不作为本次实施路线，小程序需求如进入范围需另行评估。

Capacitor 页面在原生容器的 WebView 中运行，复用代码不代表已经验证原生体验。地图性能、键盘、安全区、返回键、定位和通知必须在对应设备验证。国内 Android 厂商推送通道另行调研，不能把生成安装包当成推送已经可用。

参考：[Capacitor 介绍](https://capacitorjs.com/docs)、[构建流程](https://capacitorjs.com/docs/basics/workflow)、[FastAPI 特性](https://fastapi.tiangolo.com/features/)。

## 原型迁移与目录职责

完整目标目录见 [README](../README.md#目标目录结构)。客户端迁移基线为 design 分支 `4d95af0`，迁入 frontend/ 后以该目录作为网页实现入口；backend/ 已提供 FastAPI 服务入口、hello 路由、响应模型和测试；业务模块、原生工程及数据库部分仍是后续计划。

- 客户端已按上述基线迁移页面、地图和手绘插件；后续变更继续在 frontend/ 维护，设计参考不长期维护另一套业务代码。
- pages/ 保留现有页面及地图、Agent 等页面专属子目录；components/ 仅放跨页面公共组件。保留哈希路由、pageMeta 元数据和手绘插件，不为了目录统一拆散专属组件。
- 新增接口、平台适配及业务代码使用 TypeScript，既有 JS/MJS 逐批迁移；初始化时支持过渡期混合文件并提供真实检查命令，不强制首阶段重写所有原型。
- api/ 集中请求、API 地址配置及错误处理；types/ 定义接口类型；data/ 放明确标注的演示数据；platform/ 封装 Web/原生能力差异，避免页面散布平台分支。
- 原型 assets/ 地图与字体、src/pictures/ 图片迁入 src/assets/，保留来源与许可证；sketch.js 及其 Vue 指令统一纳入 plugins/。同步更新相对导入、构建许可证输出、地图处理脚本与测试路径，移除个人机器字体路径等绝对路径依赖。
- scripts/ 放资源处理和校验；tests/ 放测试并保留原型中有价值的行为用例。android/、ios/ 放 Capacitor 原生工程，按阶段生成并维护配置；产物及签名凭证不提交。
- 后端为模块化单体：api/ 管理路由，schemas/ 管理 Pydantic 数据结构，core/ 管理配置；services/ 后续承载业务逻辑，db/ 管理数据库连接与模型，migrations/ 保存 Alembic 迁移。workers/ 后续提供独立进程入口，可复用服务与数据访问逻辑，不作为独立微服务。
- deploy/ 集中后端环境注册表、直接运行后端与 SSH 隧道的控制工具、项目网关和初始化脚本；.github/ 保留模板及 Actions 工作流。目录按实际需要创建。

## 目录与启动命令

### 运行环境与安装

使用符合 `frontend/package.json` 的 Node.js：`^20.19.0 || >=22.12.0`，并使用随 Node.js 提供的 npm。可从 [Node.js 官网](https://nodejs.org/) 安装满足范围的版本。网页检查/构建在 Ubuntu 24.04 课程机执行，固定 Node.js `24.13.0` 和 npm `11.6.2`，按 package-lock.json 安装。建议成员使用同一版本；运行包含 TypeScript 直接导入的全部行为测试需要 Node.js 24.13.0。

从仓库根目录执行：

```bash
node --version
npm --version
cd frontend
npm ci
cp .env.example .env
npm run dev
```

首次配置时复制环境变量样例；已有 `.env` 时保留自己的配置。开发入口为 `http://127.0.0.1:8765/`，哈希路由默认进入引导页。点击“登录并进入”进入样例地图，无需真实账号。`vite.config.ts` 使用严格端口，8765 被占用时启动失败；可停止自己的旧预览，或执行 `npm run dev -- --port 8775` 指定空闲端口。

### 后端安装、启动与检查

后端使用 Python 3.12（`>=3.12,<3.13`）和 uv 管理依赖，精确依赖版本由 `backend/uv.lock` 锁定。先按 [uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/) 安装 uv；macOS 已有 Homebrew 时可执行 `brew install uv`。本次本地验证使用 uv `0.10.9` 和 Python `3.12.13`，仓库固定 Python 3.12 系列而非唯一补丁版本。

从仓库根目录，在独立终端执行：

```bash
uv --version
cd backend
uv python install 3.12
uv sync --locked
uv run python --version
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`uv sync --locked` 创建 `backend/.venv` 并安装锁定的运行及开发依赖；无需手动激活虚拟环境。已有可用 Python 3.12 时可跳过 `uv python install 3.12`。安装依赖或下载 Python 需要访问对应下载源。当前 hello 服务无需数据库、凭证或后端 `.env` 配置。

服务监听 `http://127.0.0.1:8000`；8000 被占用时先检查占用者，或使用其他空闲端口并同步前端 `VITE_API_BASE_URL`。启动后保持此终端运行，按 Ctrl+C 停止。在另一个终端验证：

```bash
curl -i http://127.0.0.1:8000/test/hello
```

预期为 HTTP 200、`Content-Type: application/json` 和 `{"message":"hello world"}`。`curl` 成功只验证接口；浏览器联调还需符合下节 CORS 配置。

以下检查均在 backend/ 执行：

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv lock --check
```

测试覆盖 hello 响应、允许及拒绝的 CORS 来源、未知路径和不支持的方法。

### API 地址与联调

| 变量 | 示例/默认值 | 用途 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | hello 后端基地址；可按实际后端修改，未设置时使用该默认值 |

Vite 在开发启动或构建时读取环境变量；修改 `.env` 后重启开发服务，构建预览则重新运行构建。变量会进入浏览器产物，只能保存公开配置，不得放服务端秘密。`.env.example` 的地址是本地配置示例，不代表后端已经运行。

development / preview 构建的“我的 → 帮助与反馈 → 接口连通性测试”显示当前后端地址。点击“测试连接”发起 `GET /test/hello`，加载期间禁用重复点击；只有 HTTP 200 且 JSON `message` 为字符串 `hello world` 才显示成功。网络不可达、非 200、无效 JSON、字段不符或 10 秒超时均显示原因，允许重试。

当前 Vite 未配置 API 代理，网页直接请求配置的基地址。后端须允许实际网页 Origin，例如 `http://127.0.0.1:8765` 或构建预览的 `http://127.0.0.1:8766`；协议、主机或端口不同都属于不同 Origin。页面不可达时先检查前端端口；页面可访问但连接失败时检查后端是否启动、地址及后端 CORS 配置。后端启动方法见上节；默认允许 localhost 或 127.0.0.1 的 5173、8765、8766 端口。自定义网页端口需同步修改 `backend/app/main.py` 中的明确来源白名单，手机局域网和 Android/Capacitor 来源尚未配置。

### 构建、预览与检查

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

地图脚本读写 `src/assets/maps/`；下载会修改快照，普通页面演示和构建无需下载。当前没有独立格式或 lint 脚本，不应报告这些检查已经通过。依赖、dist、`.env` 等忽略规则见 `frontend/.gitignore`；TypeScript 构建可能产生 `tsconfig.tsbuildinfo`，属于本地缓存，不应提交。

### 内部调试工具与构建模式

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

### 演示范围与移动端

活动、账户、兴趣、Agent 对话和定位为前端样例，无数据库、登录、模型或上传服务；只有 hello 测试区发送真实请求。请求成功需另行启动兼容后端，模拟响应验证不能代替真实联调。

需要手机浏览器预览时，先构建，再执行 `npm run preview:phone`，通过电脑在局域网中的实际 IP 和 8766 端口访问；网络及防火墙需要允许手机连接。hello 后端地址必须设置为手机可访问的地址，手机的 localhost 不指向电脑。手机网页不代表 Android/iOS 安装包已经验证。当前没有 Capacitor 原生工程或 APK 命令，后续安排见 [部署说明](deployment.md#capacitor-构建与首阶段验证包)。

### 后端部署工具检查

业务工程启动命令仍待初始化；#29 的基础设施检查可以独立运行：

```bash
python3 -m venv deploy/.venv
deploy/.venv/bin/python -m pip install supervisor==4.3.0 ruff==0.11.13
deploy/.venv/bin/python -m unittest discover -s deploy/tests -v
deploy/.venv/bin/ruff check deploy
```

Python 3.12，控制工具使用标准库和固定版本 Supervisor；详见 [部署教程](deployment.md)。

## 编码约定

- 遵循选定语言和框架的主流格式化工具，在初始化 PR 中固定配置和检查命令。
- 命名体现用途，模块职责明确；不混合页面逻辑、数据库访问和后台采集。
- 配置通过环境变量或配置层提供，环境差异不散落在业务代码中。
- 用户输入校验、资源权限检查和敏感操作由服务端保证。
- 接口与数据库变更同步契约、迁移和测试说明。
- 日志包含可追踪任务或请求标识，不输出秘密和真实私有信息。
- 仅提交源码、必要配置和锁文件；产物、缓存、依赖目录加入忽略规则。
- 测试围绕行为与风险；不为低影响文档修正编写镜像式测试。

## commit 规范

commit 和 PR 标题统一使用 `类型: (范围) 描述`，使用英文冒号和括号，冒号后及右括号后各留一个空格，描述使用中文。例如 `feat: (订阅) 新增兴趣订阅接口`。范围填写本次改动涉及的模块或主题，例如 `订阅`、`地图`、`前端`、`后端`、`部署`、`协作`；跨模块改动可用共同的功能名称，项目整体调整可写 `工程`。一次提交表达一个明确目的。

| type     | 用途                                       |
| -------- | ------------------------------------------ |
| feat     | 新增功能                                   |
| fix      | 修复缺陷                                   |
| docs     | 文档                                       |
| refactor | 保持外部行为的结构调整                     |
| perf     | 性能优化                                   |
| test     | 测试                                       |
| style    | 格式调整，不改变逻辑；不是所有界面样式修改 |
| build    | 构建或依赖                                 |
| ci       | 自动检查、部署工作流                       |
| chore    | 其他维护                                   |
| revert   | 撤销改动                                   |

基于 Issue 的分支优先通过 Issue 页面右侧 Development 中的 **Create a branch** 创建，使用默认的 `编号-Issue名`；名称较长时缩短为 `编号-简短任务名`，例如 `12-subscription-api`、`28-map-marker`。从 `main` 创建，已有分支继续使用。操作教程见 [创建开发分支](../CONTRIBUTING.md#3-创建开发分支)。

```text
feat: (订阅) 新增兴趣订阅接口
fix: (地图) 修复活动标记点击异常
docs: (协作) 补充 PR 评审教程
```

不兼容变更在提交正文和 PR 的兼容性说明中写清影响与迁移方法：

```text
feat: (订阅) 调整订阅响应结构

兼容性说明：interests 改为 subscriptions，客户端需要同步修改。
```

建议 Squash merge；合并时检查最终提交信息，同样使用 `类型: (范围) 描述`。格式检查自动化待后续配置，当前为团队约定。

## Issue 和 PR 规范

使用模版提交 Issue 和 PR。如需更改或新增，请在 `.github/` 下提供模板后在此处同步。

### Issue 模板怎么选

在 GitHub 仓库的 **Issues → New issue** 中选择模板，按需填写表单后提交。目前有以下三种模板：

| 模板     | 适用情况                                                                           | 模板文件                                            |
| -------- | ---------------------------------------------------------------------------------- | --------------------------------------------------- |
| 子任务   | 一项可以独立完成的开发、文档、调研或基础设施工作，例如订阅接口、地图页面、租用域名 | [task.yml](../.github/ISSUE_TEMPLATE/task.yml)       |
| 父任务   | 需要多人协作和拆分的大功能，例如实现兴趣订阅、实现地图功能                         | [feature.yml](../.github/ISSUE_TEMPLATE/feature.yml) |
| Bug 报告 | 已有功能出现异常，需要提供复现方法并跟踪修复                                       | [bug.yml](../.github/ISSUE_TEMPLATE/bug.yml)         |

“子任务”模板也可以用于独立任务。父子关系需要在 GitHub 中另外关联，选择模板本身不会创建父子关系。

### 子任务模板

标题写清要完成的工作，例如“实现兴趣订阅保存接口”。表单内容如下：

| 字段           | 是否必填 | 填写方法                                         |
| -------------- | -------- | ------------------------------------------------ |
| 背景与目标     | 否       | 为什么要做这项工作，完成后能实现什么结果         |
| 工作范围       | 否       | 列出本任务包含的内容，必要时说明与其他任务的分工 |
| 验收条件       | 否       | 写可检查的结果，可使用`- [ ]` 勾选清单         |
| 依赖和参考资料 | 否       | 关联 Issue、接口契约、设计稿或资料；无则写“无” |

例如“实现兴趣订阅保存接口”可以这样填写：

```markdown
### 背景与目标
用户选择感兴趣的领域后，系统需要保存订阅，供后续推荐使用。

### 工作范围
实现订阅的保存与查询接口，补充接口说明。兴趣选择页面由另一个任务负责。

### 验收条件
- [ ] 保存订阅后再次查询，结果一致
- [ ] 重复保存相同兴趣不会产生重复记录
- [ ] 用户只能查询和修改自己的订阅

### 依赖和参考资料
关联父任务 #12；接口字段见双方确认的接口文档。
```

提交后设置负责人、模块标签、Milestone 和 Project；优先级在 Project 的 **Priority** 字段中设置。如果属于某个父任务，在父 Issue 中创建或添加子 Issue。需求审批和状态流转见[协作流程](workflow.md)。

### 父任务模板

标题写功能名称，例如“实现兴趣订阅”。表单内容如下：

| 字段               | 是否必填 | 填写方法                                                                 |
| ------------------ | -------- | ------------------------------------------------------------------------ |
| 用户场景与整体目标 | 否       | 从用户角度说明功能用途和最终体验                                         |
| 范围与边界         | 否       | 本阶段包含什么，哪些内容留待以后                                         |
| 拆分计划           | 否       | 列出接口契约、前端、后端、联调等工作，作为创建子 Issue 的依据            |
| 整体验收条件       | 否       | 写完整用户流程的验证标准，例如选择兴趣、保存、重新进入页面后看到相同结果 |
| 依赖与参考资料     | 否       | 写依赖的功能、设计稿或讨论记录                                           |

提交后设置负责人、Milestone 和 Project，再按拆分计划创建或关联真正的子 Issue。正文里的任务清单用于说明计划；GitHub 的子 Issue 关系用于跟踪每项工作的负责人和进度。父任务的验收以完整功能可用为准。

### Bug 报告模板

标题直接描述异常，例如“重新进入兴趣页面后订阅选项丢失”。表单内容如下：

| 字段                 | 是否必填 | 填写方法                                                                   |
| -------------------- | -------- | -------------------------------------------------------------------------- |
| 复现步骤             | 否       | 按顺序写操作，让队友可以照着复现                                           |
| 预期行为             | 否       | 说明正常情况下应该出现的结果                                               |
| 实际行为             | 否       | 说明实际出现的结果或报错                                                   |
| 环境与版本           | 否       | 写设备、系统、浏览器或 APP 版本、测试地址和提交 SHA                        |
| 截图、日志及关联任务 | 否       | 补充有助于定位的截图、日志及相关 Issue；日志提交前移除密码、令牌和私有内容 |

例如复现步骤可以写“登录测试账号 → 选择‘人工智能’并保存 → 离开页面 → 重新进入兴趣页面”，并分别写明预期仍被选中、实际未被选中。测试地址和提交 SHA 帮助队友确认是否在验证同一版本。

### PR 模板

创建 PR 时，正文会自动带入 [PR 模板](../.github/pull_request_template.md)。标题沿用上面的 `类型: (范围) 描述`，例如 `feat: (订阅) 实现兴趣订阅`。按下面各节填写，HTML 注释是填写提示，提交后的正文中不会显示。

| 章节             | 填写内容                                                                          |
| ---------------- | --------------------------------------------------------------------------------- |
| 关联 Issue       | 完整解决且已验收时写`Closes #编号`；部分完成或还需要后续验收时写 `Refs #编号` |
| 改动说明         | 说明本次实现的结果，让评审者知道需要关注哪些改动                                  |
| 验证方式与结果   | 写实际执行的命令或手动步骤、结果和未测内容，并据实勾选自测与检查项                |
| 预览与接口示例   | 提供可用的预览链接与版本标识，或接口调用示例；不适用写“无”                      |
| 部署与兼容性说明 | 写数据库迁移、配置项、依赖、接口兼容性、原生重打包及恢复限制；无则写“无”        |
| 文档             | 更新必要文档后勾选，或说明本次不需要更新文档的原因                                |

## AI 辅助开发规范

见 [AI 辅助开发指南](ai-development.md)。

## 网页预览构建边界

本地和后续原生构建继续使用相对资源基路径与 `VITE_API_BASE_URL`。CI 设置 `VITE_WEB_PREVIEW=true`、`VITE_WEB_BUILD_ID=fe-<SHA>-<run_id>-<attempt>`，并把 Vite base 设置为 `/__livelife/web-builds/<build_id>/`。仅网页预览启用字体、图片的共享哈希资源路径；地图 JSON、JS/CSS 及许可证保持不可变构建路径。升级 Vite 时必须检查 `experimental.renderBuiltUrl` 生成的 URL，并验证实际资源请求；实验性 API 依据见 [Vite 文档](https://vite.dev/guide/build#advanced-base-options)。

运行 `cd frontend && node --test scripts/*.test.mjs` 和 `npm run build` 进行前端检查。预览构建不要把本地 `.env` 中的开发地址或任何访问密码打入产物；真实 API 地址由受信控制器生成运行时配置。部署依赖、控制接口和启用步骤见 [部署说明](deployment.md#网页预览实现与维护)。


## 课程机构建环境

课程机工具链固定 Node 24.13.0、npm 11.6.2、Python 3.12、uv 0.12.23 和 Supervisor 4.3.0。GitHub 上的 build request 只触发调度，真实 Frontend checks / Backend checks 由课程机执行并回传。服务器使用 npm 国内镜像及清华 Python 镜像、锁定版本和缓存；本地开发仍可沿用自己的包源，不需要改锁文件。队列、隔离、工具校验及上线状态见[部署契约](deployment.md#课程机统一构建与队列)。

## Android 本地工程

Capacitor Android 工程已在 frontend/android 提供。工具版本、SDK/IDE 安装、网页同步、手机/模拟器运行和 debug 包隔离见[Android 教程](android-testing.md)。团队签名与自动打包不依赖每位成员的本机环境。
