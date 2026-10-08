# 测试与验收教程

## 三个层次

| 层次 | 验证内容 | 位置 |
|---|---|---|
| 开发者自测 | 单项行为、错误处理和基本检查 | 本地或分支预览 |
| PR 验证 | 本次改动符合任务、不会引入明显回归 | Actions、队友本地或预览 |
| 整体联调 | 多项改动组合及阶段目标 | main 对应共享测试服 |

自动检查通过、PR 评审通过、Issue 验收通过分别提供不同证据。构建成功不能证明业务正确，网页通过不能证明手机原生能力可用。

当前先采用本地测试：作者按任务自测，评审者拉取 PR，在本地准备相应版本并验证。统一的预览链接与测试包入口需要后续基础设施建设，配置并验证可用后再启用。

## 发 PR 前操作

1. 逐项阅读 Issue 验收条件，确认依赖和接口版本。
2. 启动本地环境，或按 [部署教程](deployment.md#合并前的分支预览) 推送分支并部署预览。
3. 执行工程中实际提供的格式、类型、相关测试和构建命令。前后端现有命令与运行条件见 [工程规范](engineering.md#目录与启动命令)。
4. 手动验证成功、空数据、错误及权限相关情形。
5. 查看 git diff，确认没有秘密或无关文件，更新接口和使用文档。
6. 主分支变化后同步并验证受影响部分，记录测试提交。
7. PR 中填写执行命令、手动测试步骤、结果和未测内容；有预览环境时提供链接和版本。接口改动可附调用示例，排查问题时可附日志摘要。前端 PR 无需提交界面截图或录屏。

## 队友如何验证未合并 PR

### 本地拉取

在无待处理改动的工作区，先 fetch，再创建自己的评审分支。例如 PR 的来源为同仓库 12-subscription-api：

```bash
git fetch origin
git switch -c review/12 origin/12-subscription-api
```

按工程启动文档运行，按 PR 步骤验证。若已有同名本地分支，使用另一个名称，不覆盖已有工作。跨仓库 PR 可使用 GitHub CLI 的 `gh pr checkout <编号>`，前提是已安装并认证。评审完成切回原分支；不要顺手修改作者分支并推送。

### 预览链接与测试包

以下为后续启用时的使用方法。团队将先建设分支构建、预览部署、测试数据、版本标识、测试包分发和资源清理，并在部署文档提供真实入口；目前先按上面的本地拉取方法进行 PR 验证。

打开 PR/分支提供的预览 URL，确认页面显示或部署记录标识的提交 SHA；否则可能测试了旧版本。前端接共享后端时检查接口兼容性；接口一起变更时使用配套后端。

Actions 若配置了构建附件，可在 Actions → 对应运行 → Artifacts 下载测试构建。它不是永久 Release，需记录有效期和构建版本。Android 安装适当签名的测试 APK；iOS 按所配置的测试分发渠道进行，不能把任意 IPA 当成可安装包。

## 首阶段 Demo 验收

以下是完整验收清单。前端已有构建、行为测试及浏览器检查；真实后端联调、另一名成员复现与真机结果尚未完成。此阶段仅 hello 接口真实联调，业务演示使用前端样例数据，不适用下节完整 MVP 的登录、订阅持久化及共享测试服要求。

### 网页与接口

- 按正式工程文档安装和启动客户端、后端，记录提交 SHA、运行环境和实际地址；不能用 design 原型运行成功代替正式工程验证。
- 样例引导、地图、详情、日历和其他页面能按 README 动线跳转，演示数据和未实现操作有清楚说明。
- `GET /test/hello` 返回 HTTP 200、JSON `{"message":"hello world"}`；前端通过真实请求展示 message。
- 验证加载状态、后端不可达、非 200 和错误响应格式的提示及重试，不用 Mock 成功掩盖联调失败。
- 验证地图拖动、缩放、建筑选择、二维/三维切换和详情返回；楼层、定位、活动不被误认作真实信息。三维不能正常运行的设备可切换二维入口，仍记录三维问题。

### 最小 Android 验证包

- 使用正式客户端同一版本构建、安装测试 APK，记录 Android 系统、设备型号、WebView 版本和构建标识；手机浏览器预览不能代替 APK 验证。
- 验证启动、资源加载、地图操作、详情跳转及返回键。返回键先关闭当前弹层，再返回上一页面；顶层页面遵循平台退出行为，不循环跳转。
- 检查安全区、窄屏、输入框聚焦和键盘弹出/收起后的布局，记录地图性能和设备上的明显卡顿或崩溃。
- 用手机可访问的开发后端地址完成 hello 请求及失败重试。电脑 localhost 不是手机后端地址，需核对监听、网络、防火墙、跨域和测试包网络策略。
- 验证包不要求定位授权、推送、真实登录或商店发布。Android 验证需后续单独安排任务，不直接改写 #20/#23 的网页验收范围。

### 复现记录

另一名成员按文档复现网页 Demo；Android 验证任务另提供真机记录，条件具备时由另一名成员复现安装和操作。记录日期、前后端 SHA、安装包标识、实际命令、网络配置、演示数据来源、步骤、结果及未测项。正式运行命令与包入口由实现任务补齐，仅为实际执行的项目填写“已通过”，保留未测项。

## 前端内部工具开关验收

同一个提交分别验证 preview 和 production，模式选择、环境变量优先级及启动教程见[工程规范](engineering.md#内部调试工具与构建模式)。

1. `npm run dev`：帮助页显示接口测试；关闭本地开关并重启后隐藏，正常帮助内容可用。
2. `npm run build:preview`、`npm run check:internal-tools -- true`、`npm run preview`：帮助页显示测试工具，真实后端启动后 hello 成功；请求失败仍显示可理解的错误。
3. `npm run build:production`：构建自动确认所有输出 chunk 不含测试组件和 hello 测试代码。刷新预览页，正常帮助内容保留，接口测试入口不出现，访问帮助页也不加载对应异步 chunk。
4. 尝试 `VITE_INTERNAL_TOOLS=true npm run build:production` 和 `VITE_INTERNAL_TOOLS=invalid npm run build:preview`，预期构建拒绝；不要将这种预期失败报告为 CI 异常。
5. 服务器预览仍执行原有运行时配置、不可变资源、许可证及后端 SHA 校验，`check-preview-build.mjs` 同时确认内部测试代码存在。

记录提交 SHA、mode、Node/npm、实际步骤和结果。浏览器模拟响应与真实 API 联调分别记录。production 工具检查通过不等于业务就绪或正式部署完成。

## MVP 验收清单

以下适用于后续完整业务阶段，不是首阶段 hello Demo 的验收范围。

### 兴趣订阅

- 首次进入、已有订阅、修改和重复保存行为符合约定。
- 保存后重新查询一致，错误时不显示伪成功。
- 未登录被拒绝，不可修改其他用户数据。
- 前后端字段一致，接口文档与实现一致。

### 地图

- 地点坐标和地图坐标系一致，标记位置正确。
- 地点、活动及详情链接关联正确。
- 无活动、加载失败和权限拒绝有可理解提示。
- 目标平台真实设备验证地图渲染、点击和导航行为；如后续接入地图 SDK，追加其验证。

### 工程和文档

- 共享测试服版本明确，前后端可连通。
- 新成员按照文档能准备环境和启动项目。
- 没有把测试数据或凭证泄漏到公开记录。
- 已知问题记录为 Issue，并说明是否阻碍 MVP 交付。

推送若纳入版本范围，额外验证授权/拒绝、前台/后台、重复提醒、点击跳转；不同系统和厂商真机分别记录。模拟发送成功不能保证系统通知送达。

## 客户端本地检查记录（2026-10-06）

检查基于 PR #30 的 `40627f9` 及审查修复提交，代码检查版本 `7d5f3e2`。环境为 macOS、Node.js `25.8.0`、npm `11.11.0`、Playwright Chromium；未使用真实账户或业务后端。

- 安装：在 frontend/ 执行 `npm ci --cache /private/tmp/livelife-pr30-npm-cache`，通过。临时缓存用于绕过本机默认 npm 缓存权限问题，其他机器可使用普通 `npm ci`。
- 构建：`npm run build`，类型检查与 Vite 构建通过；仍有大于 500 kB 的产物提示。
- 地图：`npm run map:prepare`，从本地快照生成成功，没有下载数据；重新生成的数据与已提交版本一致。
- 现有行为测试：`node --test scripts/*.test.mjs`，35 项全部通过，覆盖地图几何、2D、抽屉、输入区布局和收藏。
- 浏览器：七个页面加载、进入地图、2D/3D 切换、搜索与选择建筑；帮助页往返以及 hello 连接中禁用重复点击、失败后重试已检查。构建预览下以 320、390、1280px 宽度检查测试区，没有横向溢出；错误响应提示后可重试获得模拟成功。
- hello：以浏览器模拟响应验证 HTTP 200 的 `hello world` 成功；错误字段类型、其他 message、缺失字段、无效 JSON、HTTP 201/500、网络失败及超时均进入错误分支。另检查本地后端不可达的实际失败提示。模拟成功不等于真实后端联调已通过。

OSM 可见署名由 #31 在 v0.1.0 阶段补齐；真实后端 hello 联调、Android/iOS、完整触摸手势与正式部署仍待验证。AI 本地检查不替代成员正式评审。

## 后端本地检查记录（2026-10-07）

检查基于 PR #32 的 `927028e` 和 CORS 修复提交 `0917890`，环境为 macOS、uv `0.10.9`、Python `3.12.13` 和 Playwright Chromium。

- 按工程规范执行 `uv python install 3.12`、`uv sync --locked` 和 `uv run python --version`，通过。
- 在 backend/ 执行 `uv run pytest`，10 项测试全部通过；`uv run ruff check .`、`uv run ruff format --check .` 和 `uv lock --check` 均通过。
- 按文档启动 Uvicorn，`curl -i http://127.0.0.1:8000/test/hello` 返回 HTTP 200、JSON `{"message":"hello world"}`。
- 使用已有客户端开发页面 `http://127.0.0.1:8765` 和构建预览页面 `http://127.0.0.1:8766`，在真实浏览器中通过 `fetch` 请求默认后端地址 `http://localhost:8000/test/hello`，两者均返回 HTTP 200 和约定 JSON，没有模拟响应。

本记录验证后端契约及浏览器跨域连通性；完整页面交互验收、另一名成员复现、手机局域网、Android/iOS 和正式部署仍待验证。临时后端验证结束后关闭，AI 检查不替代成员正式评审。

## 共享测试服约定

- main 合并后的部署成功才更新环境版本标识；失败记录真实状态。
- 测试账号、测试数据与正式环境隔离，使用模拟通知或受控设备，避免真实群发。
- 数据重置提前告知正在联调的成员，记录重置方法和负责人。
- 分支预览不覆盖共享测试服。预览中的数据库迁移也不能操作正式数据库。
- 测试报告记录提交 SHA、地址、设备/系统、步骤和结果。

## 发现 Bug 和验收完成

通过 Bug 表单记录最短复现、预期/实际、环境、截图和日志摘要。日志先移除密码、令牌和私有内容。将缺陷关联到相关父 Issue/Milestone，阻塞项标记明确原因。

任务验收完成后，在 Issue 记录证据并关闭。父 Issue 只有整体流程通过才关闭。MVP 最终验收记录确定的提交 SHA，供 Tag 和 Release 使用；发布不能悄悄换成后来未测的提交。

## 后端部署基础设施验证

`test_rpc_input.py` 覆盖 SSH JSON 输入边界：使用真实子进程管道，故意保持写端打开，确认收到完整 JSON 后返回；另外验证嵌套、转义、Unicode 跨块、旧格式/换行格式兼容、大小限制及非法输入。实际服务器验证也仅用受限 SSH 的 snapshot 操作，保持 stdin 打开，不用部署请求代替只读检查。

公开测试入口有独立 Nginx 集成测试 `test_access_nginx.py`：使用临时目录、自签测试证书、随机回环端口和模拟上游，验证无需预览凭证的 API/静态资源访问、旧 key 入口 404、遗留凭证剥离，以及业务认证透传和业务 401 原样返回。CI 安装 Nginx 后运行；本地缺少 Linux Nginx/OpenSSL 时明确 skip，在服务器独立临时网关验证，不修改共享后端。

#29 的工具不依赖业务后端即可检查引用与环境管理。先按工程规范安装控制工具依赖，再运行 `python -m unittest discover -s deploy/tests -v`。Supervisor 集成测试需要本地 Unix socket 权限；没有安装 Supervisor 时该项明确 skip，不能当成通过。

#27 同一命令加入网页测试，覆盖双分支及 PR 别名、固定配对、前后端完成顺序、后端-only 复用 main、分支选择迁移、到期/关闭/重开、旧任务晚到、配额、非法产物、候选持久引用及真实 SIGKILL 后恢复。前端执行 `node --test scripts/*.test.mjs`，验证配置校验、加载失败和旧 HTML/新配置不匹配；原有地图与页面行为测试一起运行。测试环境需要 Node 24.13.0。

实际 HTTPS 网页还须检查无需 key 直接访问、缓存与 gzip、刷新/哈希路由、2D/3D 地图、字体/图片/许可证，以及 hello 响应的后端 SHA。代码测试通过不代表 main 工作流已启用；本次服务器实测和剩余验收以 [部署记录](deployment.md#网页预览实现与维护) 为准。另一名成员在 PR 记录版本、步骤和结果，AI 自查不替代正式评审。

自动测试覆盖：

- main 与两个预览独立分配端口；两个管理进程同时部署不分配重复端口。
- 后端 PR 更新后，跨 PR 前端继续连接原 SHA；释放后端 PR 后旧 SHA 仍被前端保留。
- main 永不被释放；普通前端默认连接共享 main。
- 候选后端/网关失败保留上一部署；旧构建不能覆盖新部署或关闭记录。
- 最后引用释放后延迟回收、分支租约到期、重复释放幂等。
- 课程机清理失败保留待清理端口，后续重试；实例重新创建需先完成原清理。
- 拒绝非法 owner/SHA、tar 路径穿越、符号链接及非后端文件；控制 job 不执行 artifact 脚本。
- 实际 Supervisor 子进程被终止后自动重启，重复移除不会处理其他进程。
- 启动候选之前，从另一数据库连接确认清理预约已提交；成功部署后预约与引用一起转换为有效实例。
- 对真实控制子进程注入 SIGKILL，分别在候选启动后和路由发布后、数据库最终提交前终止：旧 main 引用保留，候选端口不会被复用，恢复和清理后候选进程退出，原 main 进程继续运行。
- 验收与 main 部署交错执行时，真实部署锁覆盖检查、测试、清理和路由恢复；正常或失败的验收结束后，排队的 main 部署路由保留。

### 一次性服务器验收脚本

`deploy/smoke-servers.py` 使用独立测试注册表，但共享项目网关，因此只允许在真实注册表没有实例和待清理预约时运行。它从空表检查之前到全部清理、路由恢复之后一直持有真实部署锁；测试期间其他部署和恢复任务会等待。维护者应在无共享后端的初始化窗口运行，预留足够的工作流等待时间；共享后端已经存在时使用独立测试网关。

维护者先在公网机准备一个 JSON 文件，包含三个不同 SHA 的后端包记录。每项形如 `{"sha":"完整40位GitSHA","bundle":"/绝对路径/backend.tgz"}`，包需包含构建导出的运行依赖与 Linux wheel，然后执行：

```bash
sudo -u livelife /opt/livelife/control-venv/bin/python \
  /opt/livelife/control/smoke-servers.py /绝对路径/three-backends.json
```

网关使用现有 HTTPS，测试请求不发送预览凭证。脚本退出时只清理测试注册表登记的实例和候选，并在仍持有真实部署锁时恢复真实注册表的路由；清理失败保留测试状态用于排查。不要绕过锁或手动清空共享路由。

两项故障回归可以独立运行：

```bash
deploy/.venv/bin/python -m unittest discover -s deploy/tests -p test_interrupted_deploy.py -v
deploy/.venv/bin/python -m unittest discover -s deploy/tests -p test_smoke.py -v
```

前者需要 Supervisor 和本地 Unix socket 权限，在本机临时目录创建并清理测试子进程；后者验证文件锁和路由交错，不连接服务器。

正式后端就绪后的服务器验收：

1. 配置 HTTPS、密钥及 GitHub Variables/Secrets，部署 main 和两个不同 SHA 的后端 PR。记录完整 SHA、端口和真实 hello 响应。
2. 无预览凭证直接请求 hello 应返回 HTTP 200 和约定 JSON；检查 X-Livelife-Backend-SHA 与 PR 记录相同。业务鉴权接入后另验证业务接口的未登录与越权响应。
3. 在另一个前端 PR 建立固定绑定，更新目标后端 PR，确认两个固定 URL 分别返回正确版本；用响应头区分，不改变 hello JSON。
4. 关闭后端 PR，确认其旧版本仍被前端引用；关闭前端 PR，经过清理宽限期确认实例、路由和隧道释放。不要为了测试缩短共享配置，使用独立测试注册表。
5. 制造候选启动失败、项目隧道中断、课程机暂时不可达，分别验证回滚、自动恢复和清理重试。
6. reopened 后恢复或重新部署当前提交；检查 PR 说明、Summary 与实际服务一致。
7. main 检查通过后验证共享入口更新；失败时版本保持原样。

2026-10-07，部署测试共 37 项通过，包括真实 Supervisor 崩溃重启；ruff、actionlint、shell 语法和文档链接/锚点检查通过。两台服务器已完成三个临时 Git 版本的 HTTPS、认证、独立端口、固定绑定保留和回收实测。另在独立目录验证 #24 / PR #32 的原始后端提交：8 项 pytest、ruff、格式检查、hello 打包通过；其锁定依赖的 Linux wheel 已在课程机离线安装，HTTPS 与保留/回收再次通过。临时环境全部清理。

同日根据 PR #34 评审补充故障回归后，完整部署测试增至 43 项并全部通过；新增的真实 SIGKILL、启动前预约提交及验收/部署交错测试覆盖上述两项问题。ruff、actionlint、shell 语法与文档链接/锚点检查通过。这次验证在本机临时环境进行，服务器控制程序需在部署修复版本后生效。

GitHub CI 成功不能代替完整服务器验收。#24 后端已合入当前分支，main 完整工作流、PR 自动说明与重新打开的实际事件链路仍待部署工作流合并后验证；上述独立验收不代表正式应用上线。


## 课程机构建结果的判断

Backend build request / Frontend build request 的成功只证明通知已发出，不证明检查通过。验收应查看被测试提交 SHA 的 Backend checks / Frontend checks commit 状态、Preview environments 实际日志及 course-build-logs 附件。任务排队显示 pending；测试/构建失败显示 failure，原预览可能仍可访问，必须核对其版本。检查成功后发布失败是部署故障，不伪称测试失败或新页面已上线。

维护者验证应覆盖：两个全项目槽位及第三个任务排队；push/PR 同 SHA 去重；旧排队提交替换；构建失败/worker 重启；日志分页；SHA/模块不匹配拒绝；源码路径和静态包链接拒绝；沙箱无法读取 ~/.ssh、控制数据库或部署凭证；原成功路由、固定绑定与回滚引用保持。新路径安装和完整 GitHub 链路以[实施状态](deployment.md#当前实施状态)为准。

## 前端内部工具开关本地记录（2026-10-07）

在 `feat/frontend-internal-tools` 分支执行，Node.js 24.13.0 / npm 11.6.2 的 39 项现有行为测试通过；preview / production 类型检查与构建、实际产物组件/请求/样式标记检查通过。课程机原命令设置 `VITE_WEB_PREVIEW=true` 后仍自动选择 preview，不可变资源、共享资源和许可证检查通过。production 强行启用开关、preview 使用非法值均按预期拒绝。

Playwright Chrome 实测本地两种静态构建：preview 的帮助页异步加载测试组件并通过真实 FastAPI hello 返回 `hello world`，production 的帮助页保留普通帮助及反馈内容，未出现测试入口。验证使用当前 backend 源码及已有依赖环境，没有模拟成功响应；控制台仍有原有 favicon.ico 404。正式部署、原生打包与另一名成员评审未在本次执行。

## Android 测试包操作

本文介绍 #28 的 Android 测试包。网页、APK 和后端各有独立版本；网页测试通过不能代替手机验收。完整 Actions 是否已启用，以[维护者实施记录](deployment/android-apk.md#实施记录)为准。

### Android 手绘渲染回归

2026-10-08 在 Redmi Note 12 Turbo、Android 15、Android System WebView `131.0.6778.260` 上发现 PR #41 的 `0.1.0-test.7` 滑动后闪屏、文字和界面元素消失。独立 WebView 诊断应用中，用户确认从加载前关闭手绘效果后恢复正常；软件绘制避免元素消失但仍卡顿。改用页面外生成的透明 PNG 装饰后，用户确认诊断应用中的问题已解决。这是诊断应用验证，不是已经更新、验收了分发 APK，也不代替另一名成员正式评审。

公共手绘渲染变更的复现步骤：

1. 安装包含本次修改的测试 APK，记录客户端 SHA、版本号、手机系统和 WebView 版本；旧 APK 不会随网页更新。
2. 在“我的”、日历、兴趣和 Agent 页面连续上下拖动、松手回弹，确认文字、图标和按钮始终可见，没有闪屏。
3. 在“我的”和 Agent 之间反复往返，确认手绘外观保持一致，已缓存的相同装饰不逐个重新生成；Agent 样例气泡颜色在本次应用会话内保持一致，首次进入也应复用启动预热的默认装饰。打开“我的”八个子页面（资料、兴趣、收藏、账户、密码、通知定位、外观、帮助），确认默认装饰不逐个生成；预热不得提交表单或调用 hello。
4. 切换屏幕尺寸、方向或地图选中状态，确认新纹理尺寸和高亮正确，旧任务不能覆盖新状态；验证地图 2D/3D 与页面切换。首次地图加载期间，拖动下方附近建筑卡片与活动抽屉，再立即离开页面；确认操作有响应，取消后没有旧场景或纹理覆盖新页面。快速切换五个底部入口，确认旧选中项没有遗留白底。
5. 本地 debug 可通过 Chrome WebView 调试检查 `.sketch-bitmap` 图片已加载，公共装饰没有 `svg.sketch-render`。模拟 PNG 编码失败或快速离开页面，确认文字与点击仍可用、取消的纹理不发布；恢复后重新进入页面应能生成。

缓存只在当前应用进程内复用。启动会限时预热七个页面的默认布局；超时、尺寸变化和未预热交互状态仍需生成纹理，关闭进程后重新准备；不把全部启动时间或 3D 地图性能问题都归为手绘问题。

本次本地验证：43 项前端行为测试通过，包含 Worker 缓冲区传输前后几何、颜色、勾线、庭院和屋顶一致性。预览及 production 构建通过，正式产物内部工具剔除检查通过。浏览器检查页面往返、360px 尺寸、PNG 失败/取消/恢复与打包 Worker 加载。手机诊断中，用户确认 Worker 后加载期间响应好很多；启动预热完成后，首次进入日历、兴趣、Agent、我的、详情和引导页均测得零次 PNG 编码；补充子页面预热后，手机八个“我的”子页面也均为零次，且没有缺失应显示的默认装饰。地图静止时应无连续绘制，拖动、缩放和展开时仍更新；新分发 APK 与成员正式验收结果另行记录。

### 1. 根据分工准备环境

只开发 Vue 页面：安装 Node.js 24.13.0 / npm 11.6.2，按[工程规范](engineering.md#目录与启动命令)启动网页即可。只验收 APK：有 Android 手机和浏览器即可，不需要 Android Studio。

负责原生适配、插件、权限和调试的成员安装 Android Studio 2025.2.1 或更新的稳定版。Mac 选择与 CPU 匹配的 Apple Silicon/Intel 安装包。首次启动完成 SDK 安装向导，再进入 SDK Manager 安装：

- Android SDK Platform 36；
- Android SDK Build-Tools 36.0.0；
- Android SDK Platform-Tools（含 adb）；
- Android SDK Command-line Tools；
- 没有手机时安装 Android Emulator，并在 Device Manager 创建模拟器，Apple Silicon 选择 ARM64 镜像。

项目使用 JDK 21、Gradle 8.14.3、Android Gradle Plugin 8.13.0。在 Android Studio → Settings → Build, Execution, Deployment → Build Tools → Gradle 中选择 JDK 21；如果自带 JDK 不是 21，通过下载 JDK 或本地路径指定。不要为了本机 IDE 版本随意升级仓库的 Gradle、SDK 或 Capacitor 版本。

Mac 的 SDK 默认位于 `~/Library/Android/sdk`。Android Studio 可生成未提交的 android/local.properties；终端构建需设置 ANDROID_HOME 和 JAVA_HOME，例如：

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
# 换成你实际安装的 JDK 21 路径；先确认 java -version 为 21。
export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"
java -version
adb version
```

Android Studio 内置 JDK 不一定被 java_home 识别，可直接指定其真实路径。Windows/Linux 从 SDK Manager 查看 SDK 路径，配置相同变量。使用系统 Gradle 无需安装：本地命令使用仓库提交的 Gradle Wrapper。

### 2. 本地运行到手机或模拟器

在 frontend/.env.local 中配置手机可访问的后端，示例：

```dotenv
VITE_API_BASE_URL=https://192.144.253.40/api/staging/
```

该地址是共享测试后端，会随 main 更新。APP 内 localhost 指手机自身，不是开发电脑。本地 HTTP 网络例外不在本任务开启；使用项目 HTTPS 入口。业务登录、定位和推送尚未实现，页面大部分是明确标注的样例。

```bash
cd frontend
npm ci
node --test scripts/*.test.mjs
npm run android:sync
npm run android:open
```

android:sync 会构建 preview 网页并执行 Capacitor sync；修改网页后重新同步，Android Studio 里的原生工程才会包含最新页面。不要设置 VITE_WEB_PREVIEW=true，否则资源会指向网页专用的远程构建路径。

在 Android Studio 打开 frontend/android，等待 Gradle 同步完成，选择设备后点击 Run。也可以：

```bash
npm run android:debug
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

真机：在手机“关于手机”连续点击版本号开启开发者选项，打开 USB 调试，用数据线连接并在手机确认电脑的调试授权。`adb devices` 应显示设备为 device；unauthorized 需要在手机确认。模拟器在 Device Manager 点击启动后会出现在设备列表中。

本地 debug 包名为 io.github.tomorikaho.livelife.dev.local，名称“Livelife 本地调试”；团队分发包名为 io.github.tomorikaho.livelife.dev，名称“Livelife 测试”。两者可以共存，签名和数据独立。本地 debug 由 Android 工具自动签名，分发包由腾讯云专用测试密钥签名；开发者不需要索取服务器私钥。

查看原生日志：Android Studio 的 Logcat 选择设备和应用；也可执行 `adb logcat`。在电脑 Chrome 的 chrome://inspect/#devices 调试本地 debug WebView。团队 release 测试包不开放远程 WebView 调试，问题用版本、现象及日志记录。

### 3. PR 的自动测试包

前端/原生相关 PR 创建、更新、重开后，现有 Frontend build request 发出请求；受信控制器在网页检查通过后调度课程机 Android 构建。后端配套未就绪时等待后端完成或定期核对，不占用 Android 构建槽位。

流程：课程机拉取 SHA → 检查前端 → 构建网页 → Capacitor 同步 → Gradle 生成未签名 APK → 腾讯云读取产物并校验 → 签名并验证 → 发布下载页 → 更新 PR 的同一条自动评论。Android checks 表示 APK 检查/签名/发布结果，实际测试日志在 Preview environments 的 course-build-logs 中。

默认配对：

| 代码变化 | 后端 |
|---|---|
| 只有前端 | main 共享 staging |
| 前后端同时变化 | 同分支已成功部署的配套后端，固定 SHA |
| 已指定联调目标 | 保留所选固定 SHA，另一 PR 更新不会自动改变 APK |
| 只有后端 | 不自动打包，按下一节手动触发 |

PR 评论显示下载页、二维码、versionCode、客户端 SHA、后端模式/SHA/API 和有效期。前端网页链接与 APK 下载页是两个入口；在手机上扫描二维码，进入下载页再下载 APK。

稳定入口：main 为 `https://192.144.253.40/downloads/android/staging/`，PR 为 `/downloads/android/pr-编号/`。每次构建还有独立的 build-ID 下载页。文件名和校验值对应具体安装包，稳定页更新不会改变已经安装的 APK。

### 4. 手动选择客户端与后端

仓库 → Actions → Preview environments → Run workflow，工作流分支选择 main；operation 选择 android-build。

| 输入 | 填法 |
|---|---|
| client_ref | 客户端分支、Tag 或完整 SHA，默认 main |
| frontend_pr | 希望记录下载入口的 PR 编号；后端-only PR 也可填；留空生成独立临时下载页 |
| backend_target | default 沿用配对；staging 使用共享后端；pr-42 解析 #42 已部署版本；be-完整SHA 使用已有固定实例 |
| frontend_branch | Android 手动构建无需填写 |

例如 #42 只有后端改动：client_ref=main、frontend_pr=42、backend_target=pr-42。点击运行，系统确认 #42 是同仓库打开的 PR、其当前后端版本已经部署，再固定该 SHA。结果显示在本次 Actions Summary 及 #42 自动评论里。

指定 pr-42 不意味着跟随 #42：后续 #42 更新后要重新运行，才能得到连接新版后端的新 APK。default 保留已显式指定的目标。staging 跟随 main；实际 hello 响应 SHA 会显示在 APP 内。

不能为 fork 自动取得签名或部署权限；维护者先将要验证的代码导入同仓库分支，再按普通流程构建。

### 5. 下载、安装和覆盖升级

1. 手机扫码或打开 PR 下载页，核对客户端 SHA、后端和有效期。
2. 点击“下载 APK”。浏览器可能提示安装包风险或需要授权：在系统设置中允许当前浏览器“安装未知应用”。测试结束后可关闭该授权。
3. 打开下载的文件并安装“Livelife 测试”。Android 7/API 24 是工程最低版本，设备 WebView、根证书和地图性能仍需实际验证。
4. 在“我的 → 帮助与反馈 → 接口连通性测试”核对 versionCode、客户端 SHA、后端模式及加载时 SHA，再点击测试连接。
5. 记录实际响应后端 SHA 和测试步骤，避免只依据下载页判断手机里已经更新。

所有 PR 共用一个团队测试应用。新 APK 的 versionCode 全局递增，正常覆盖安装会保留该应用数据。不同 PR 不能作为两个独立测试应用同时安装；本地 .local 调试包可以与它共存。

旧 APK 可能比手机上已有包的 versionCode 小，系统会拒绝降级。需要切回旧代码时，手动选择旧客户端 SHA 重新构建，得到更大的 versionCode。不要把卸载重装当作无损切换：卸载会清除应用数据。若遇到签名不一致，先确认安装的是本地 debug 还是团队包，不要索取或重建团队签名私钥。

默认测试包 7 天到期；main 最新成功包永久保留，被替换的旧 main 包再保留 7 天。PR 关闭/合并会撤销该 PR 的入口并释放包。手机不会自动卸载，到期或关闭后接口测试明确提示失效，重新下载新包；内置样例页面仍可查看。

安装包引用与网页引用独立，不根据访问人数计算。仍有效的包保留固定后端；释放最后一份引用后，后端经过宽限期再清理。

### 6. 失败、重跑与上一成功包

打开 PR 的 Android 状态及 Preview environments 日志，区分排队、依赖安装、Gradle、产物校验、签名与发布失败。本次失败时，页面和评论保留上一成功包，并明确它不代表最新提交。

- 自动请求失败：重跑原 Frontend build request 的全部 jobs，或在该分支手动运行 Frontend build request，再查看 Preview environments。
- 想强制重新生成 APK：使用上一节 android-build；版本号会递增。
- 只重跑 Preview environments 的旧自动通知，可能复用原请求/任务；不要把它当作“强制重新构建”。
- 排队超过 30 分钟会失败；任务命令最多 20 分钟、整体预算 30 分钟；源码锁等待最多 10 分钟。日志会说明原因，确认资源和下载条件后重新发起。
- 后端没有部署成功时不能默默换成 staging；先修复后端或主动选择可用目标。
- 下载页不可用或 APK 状态读取失败时，先检查网络、有效期和 PR 是否已关闭，不通过关闭版本校验掩盖问题。

Actions 附件只保存日志和版本/校验记录 7 天；APK 从下载页分发，不作为 GitHub Artifact 副本。本任务不创建正式 Release。

### 7. 真机验收记录

由另一名成员在 PR 评论中填写，未执行项目写“未测”，不要用网页或模拟器结果替代真机结果：

```text
设备 / Android / WebView：
测试日期：
versionCode / APK SHA-256：
客户端 SHA / 后端模式 / 加载时 SHA / 实际响应 SHA：
安装、覆盖升级：
启动、字体、图片、许可证入口：
地图 2D / 3D、拖动缩放、建筑与活动详情：
返回键关闭弹层、页面返回、顶层退出：
安全区、键盘弹出与收起：
外部署名链接由系统浏览器打开，返回后应用保留原页面：
真实 hello、断网/错误提示、过期提示：
结果及未测项：
```

发现问题附上复现步骤和版本；构建成功和 AI 自查不替代成员正式评审。


### 外部网页与地图故障区分

地图使用包内数据，不依赖在线 OpenStreetMap 瓦片。角落的署名链接通向外部版权页；Android 的 Capacitor 默认导航策略把外部地址交给系统浏览器，配置不应把外部域名加入 `server.allowNavigation`。验收时点击署名、返回应用，再检查地图与底部导航。外部网站超时应只影响浏览器，不应替换应用的本地页面。

临时绘制诊断应用使用普通 WebView，与正式测试包的外链策略不同，不能用其外部网页错误认定 APK 地图崩溃。若实际 APK 出现同样问题，记录包版本、完整错误地址和操作步骤，并检查 WebView 错误与进程退出日志；不要仅凭网站超时推断地图渲染进程崩溃。

2026-10-08：用户在 `0.1.0-test.9` 真机确认点击地图署名会打开系统浏览器。返回后的地图状态尚未单独记录，不将这一项计为全地图验收通过。


### 手绘磁盘缓存验证（#43）

启动教程见[工程规范](engineering.md#手绘-png-持久化缓存)。自动行为测试包含键兼容性和 IndexedDB 不可用降级；真实 IndexedDB 和绘制链路需在浏览器或调试 WebView 验证：

1. 在 frontend/ 执行 `npm run dev`，打开开发地址。等待界面准备完成，在该页面开发者工具 Console 执行：

   ```js
   await (await import('/scripts/sketch-cache.browser.mjs')).verifySketchCache()
   ```

   成功返回检查列表；失败抛出对应原因。此脚本只在开发服务使用，构建产物不包含该脚本。它创建并最终删除独立测试数据库，不清除应用数据库。
2. 检查涵盖连接关闭后 PNG 仍存在、容量按最近访问淘汰、删除、事务中断不产生候选、磁盘命中不编码、损坏 PNG 重建并再次命中、注入存储拒绝/配额错误后仍显示装饰，以及队列销毁后不发布晚到结果。注入配额错误不等于真实磁盘已填满。
3. 单独进行应用启动测试：先清理仅装饰数据库，启动并记录 `Livelife sketch preparation` JSON。完全结束进程后重启，比较 generated/diskHits、累计读取/编码时间和准备总时间。不要只在同一进程切页面，或用内存命中代替磁盘命中。
4. 测试页面尺寸变化、覆盖升级、改变渲染/字体兼容版本和主题命名空间后不会错误复用。Android 完全清除应用存储会删除其他数据，测试时先确认设备上没有需要保留的业务数据。
5. 测量数据库中 metadata 的 size 合计和条目数（PNG 内容默认最多 32 MiB/512 条），记录其与实际数据库物理占用的区别；不把这个数当作原始像素或进程内存。

2026-10-08 本地检查：46 项行为测试、preview/production 构建和 production 内部工具剔除检查通过。真实浏览器的上述存储与绘制检查通过。电脑浏览器测得第一次默认准备 239 次编码、第二次 239 次磁盘命中/0 次编码；准备总时间约 4.75 秒与 0.85 秒，属于该设备的一次测量，不是跨设备性能承诺。Android 数据另记录；诊断 WebView 不能代替分发 APK 的完整验收和另一名成员正式评审。

同日 Redmi Note 12 Turbo / Android 15 / WebView 131.0.6778.260 的独立诊断 WebView 测量：完全停止并重新启动诊断进程后，首次默认预热 generated=239、diskHits=0、elapsedMs=21294；再次重启 generated=0、diskHits=239、elapsedMs=9813。PNG 内容合计 13,164,722 字节、239 条。此诊断通过 USB 加载开发代码，保留 SVG 参数构造、布局和解码成本；结果不能作为分发 APK 的绝对启动耗时或全项验收。
