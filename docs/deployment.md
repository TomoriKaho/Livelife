# 测试环境与部署入口

## 当前实施状态

以下为已有实现和启用证据的索引，最新运行结果从 PR 自动评论及 Actions 核对。成员获取入口见[合并前的分支预览](#合并前的分支预览)。

| 能力 | 已记录的启用状态 | 证据 |
| --- | --- | --- |
| 后端构建与 HTTPS 测试部署 | 已接入，LIVELIFE_BACKEND_ENABLED=true | [main 部署](https://github.com/TomoriKaho/Livelife/actions/runs/37503098101)、[课程机控制运行](https://github.com/TomoriKaho/Livelife/actions/runs/37734442654) |
| 课程机统一检查与网页自动预览 | 已接入，LIVELIFE_FRONTEND_ENABLED=true；网页/API 无额外预览 key | [main 网页运行](https://github.com/TomoriKaho/Livelife/actions/runs/37613254277)、[PR 网页运行](https://github.com/TomoriKaho/Livelife/actions/runs/37613465083) |
| Android 测试包签名与分发 | 工程和自动链路已接入，LIVELIFE_ANDROID_ENABLED=true | [PR #45](https://github.com/TomoriKaho/Livelife/pull/45)、[实际分发运行](https://github.com/TomoriKaho/Livelife/actions/runs/37734472930) |
| 预览 PostgreSQL、迁移及数据库发布门禁 | 仓库已提供；服务器控制程序升级、依赖安装与线上验收尚待完成 | [启用与恢复教程](../deploy/README.md#预览数据库与启动门禁) |
| 正式发布与 iOS | 正式发布工作流和 iOS 工程尚未提供 | [正式发布约定](#客户端模式与后续正式发布约定) |

上述证据覆盖后端、网页及测试包发布，不代表完整成员验收。Android main 首次自动发布、完整关闭/重开清理和最新 APK 返回键真机回归仍需核对，历史证据见[验证记录索引](#验证记录索引)。业务接口、数据库及登录的范围由[架构说明](architecture.md)维护。

## 按任务阅读

- 成员：[分支预览](#合并前的分支预览)、[后端配对](#跨-pr-联调怎么指定)、[Android 下载](#android-下载入口)。
- 维护者：[安装与恢复](../deploy/README.md)、[构建队列](../deploy/BUILDING.md)、[网页发布](../deploy/WEB_PREVIEW.md)、[Android 分发](../deploy/ANDROID.md)、[控制接口](../deploy/CONTROL_API.md)。
- 验证：[团队测试与验收](testing.md)、[部署工具回归](../deploy/tests/README.md)。

## 分支与环境

| 来源 | 环境 | 更新规则 |
| --- | --- | --- |
| main 的已检查提交 | staging 共享测试后端 | 成功后切换，入口永久保留 |
| 打开的后端 PR | PR 最新入口与固定 SHA 实例 | 成功部署更新 PR 入口 |
| 尚未创建 PR 的分支 | 有期限的预览实例 | 推送或手动运行检查，保留 72 小时 |
| 前端连接另一后端 PR | 固定 SHA 的后端绑定 | 明确重新绑定才切换 |
| 已验收 Tag | production | 单独授权和部署，不属于 #29 |

main 是代码分支，staging 是测试环境。生产不会随 main 自动发布。后端使用可选 `DATABASE_URL` 和 Alembic 迁移，操作见[后端说明](../backend/README.md#数据库配置与健康检查)及[信息系统迁移](../backend/app/services/content/README.md#迁移验证与回滚)。独立/正式数据库启用账号及 Agent 前，维护者需核对目标数据库并执行 `uv run alembic upgrade head`，确认 `uv run alembic current`；预览环境的自动迁移需要先升级后文所述受信控制程序。账号邮件验证码需设置 `SMTP_HOST`、`SMTP_PORT`、`SMTP_FROM`，以及邮件服务要求的 `SMTP_USERNAME`、`SMTP_PASSWORD`；默认端口 587 使用 STARTTLS，465 使用 SMTP SSL。Agent 模型调用还需设置 Agent 会话密钥和兼容模型服务配置，详见[后端 Agent 服务配置](../backend/README.md#agent-服务配置)。凭证通过部署秘密注入，不能写入仓库或前端变量；部署工作流尚未自动配置这些变量，因此代码实现不代表共享测试服已启用数据库、邮件发送或模型服务。[自动准备数据库的开发入口](../backend/README.md#本地数据库自动准备)仅用于本机开发，不接入部署工作流。

临时测试账号入口默认开启，正式环境需在后端设置 `AUTH_TEST_LOGIN_ENABLED=false`；关闭入口不撤销已签发会话。共享身份和恢复限制见[后端测试账号说明](../backend/README.md#临时内置测试账号)。

后端启动会自动加载当前 checkout 的 `backend/.env`，但不覆盖进程环境中的值；位置、样例和重启要求见[后端配置说明](../backend/README.md#使用已有数据库或部署入口)。本机机密文件不随 Git 源码构建上传，此变更不表示 Actions 已具备 SMTP 秘密注入或线上已启用邮件服务。

新的预览启动器可自动准备每 SHA 独立的 PostgreSQL、执行迁移并核对业务表，启动后同时检查 hello 和数据库就绪状态。此能力需要先更新两台服务器上已安装的受信控制程序及课程机依赖，**仅重跑 Actions 不会启用**。现有入口在完成升级前仍可能 hello 成功而账号接口返回 `Database is not configured`。更新与验收步骤、同 SHA 保留数据和不同 SHA 从空库开始的限制集中见[预览数据库与启动门禁](../deploy/README.md#预览数据库与启动门禁)。SMTP 和真实模型凭证仍未自动注入。

新 SHA 检查并部署成功后才切换入口；仍被其他客户端固定绑定的旧版本继续保留。实例、端口和兼容产物由[部署工具](../deploy/README.md)维护。

默认仅改前端时连接 staging，随 main 更新；**主动指定另一个 PR 时固定其部署 SHA**。同一 PR 同时改前后端时，其自身预览跟随自己的最新成功部署，其他 PR 的固定绑定保持不变。

## API 地址与前端关联

以下为测试入口，末尾 `/` 属于 API 基地址：

```text
https://192.144.253.40/api/staging/                    main 共享测试后端
https://192.144.253.40/api/pr-40/                      PR #40 最新成功部署
https://192.144.253.40/api/versions/be-<完整40位SHA>/   不可变版本
```

请求 hello 时加 `test/hello`。网关去掉部署前缀，后端收到 `/test/hello`，响应仍为 `{"message":"hello world"}`。响应头 `X-Livelife-Backend-SHA` 提供版本，不修改业务 JSON。Uvicorn root-path 指向不可变入口，Swagger/OpenAPI 使用该前缀。

`/__livelife/versions.json` 提供已发布路由和 SHA。网页/API 使用 HTTPS，预览入口无需额外 key；业务账号接口使用 Bearer 会话令牌。网关仍剥离旧测试访问头和 Cookie，保留业务认证头和 Cookie。控制平面只有专用 SSH JSON 命令，不提供公网 bind/delete 接口。

### 成员如何获得测试链接

1. 从 main 创建功能分支，修改并提交；确保分支包含 main 的检查工作流，必要时先同步。
2. 推送分支，或在 Actions 选择 **Frontend build request** / **Backend build request → Run workflow**，按修改模块选择分支。请求由课程机检出固定 head SHA 检查，不使用 PR 合并模拟提交。
3. **Preview environments** 从 main 执行控制程序，提交课程机任务并回传检查结果；commit 上对应的 Frontend / Backend checks 成功后才发布。同仓库分支可执行，fork 不自动提交到课程机，也不取得部署秘密。
4. 已有 PR 时自动更新同一条说明，提供网页/API 链接、SHA 和状态；没有 PR 时从控制工作流 Summary 获取地址与到期时间。
5. 直接打开网页或 API 链接，无需输入预览 key。同一条自动评论提供已发布的网页和 API，核对状态及版本后测试。
6. 新提交更新 PR 入口；失败显示候选 SHA 并保留原成功部署，不能把旧版当成本次提交通过。

`workflow_dispatch` 和 `workflow_run` 控制工作流需要先进入 main。缺少真实后端入口或依赖的分支会明确跳过打包/部署，不生成虚假的成功地址。

### 跨 PR 联调怎么指定

通常不需要指定。#27 默认连接 staging；同一分支改后端时连接自己的部署。跨 PR 时：

1. 确认目标后端 PR 已部署最新提交，例如 #40。
2. **Actions → Preview environments → Run workflow**，operation 选 `bind`，frontend_pr 填 `41`，backend_target 填 `pr-40`。
3. 工具检查两个 PR 属于本仓库且打开，解析 #40 的成功部署，保存 `frontend:41 → be-完整SHA`。最新提交尚未部署时，报错并保留原绑定。
4. 返回 `api_base_url`、`api_path`、`backend_sha`、`frontend_sha`。网页开关启用后控制器立即更新运行时配置；未启用时只记录后端绑定。

#40 更新后，#41 仍连接原 SHA。需要切换时重新 bind；target 改成 `staging` 恢复默认，填 `be-完整SHA` 可选择仍存在的特定版本。#27 更新前端时先 lookup 原绑定，保留后端 SHA 并同步前端 SHA，不能每次推送都覆盖成 staging。

## 构建结果怎么判断

Backend build request / Frontend build request 的成功只证明通知已发出，不证明检查通过。验收应查看被测试提交 SHA 的 Backend checks / Frontend checks commit 状态、Preview environments 实际日志及 course-build-logs 附件。任务排队显示 pending；测试/构建失败显示 failure，原预览可能仍可访问，必须核对其版本。检查成功后发布失败是部署故障，不伪称测试失败或新页面已上线。

## 合并前的分支预览

main 的共享网页入口为 [staging 网页](https://192.144.253.40/staging/)。分支及 PR 使用各自自动评论或 Summary 中的 URL，不用 main 页面代替当前提交的预览。

推送后查看对应 build request 和 Preview environments，等待真实 Frontend / Backend checks 及发布结果。已有 PR 从自动评论进入网页/API 或 Android 下载页；无 PR 从控制运行 Summary 获取分支地址。检查失败或未发布时按[测试说明](testing.md#本地拉取)在本地验证。核对 SHA、后端配对和有效期；上一成功产物不能当作最新提交验收结果。

## Android 下载入口

main 的稳定下载页为 `https://192.144.253.40/downloads/android/staging/`，PR 为 `/downloads/android/pr-编号/`，每次构建另有独立 build-ID 下载页。PR 自动评论和 Actions Summary 提供下载页、二维码、版本和校验值；APK 不通过 Actions Artifacts 分发。

| 代码变化 | 默认后端配对 |
| --- | --- |
| 只有前端 | main 共享 staging |
| 前后端同时变化 | 同分支已成功部署的配套后端，固定 SHA |
| 已指定联调目标 | 保留所选固定 SHA |
| 只有后端 | 不自动打包，手动选择客户端和该后端构建 |

网页绑定可更新配置，已安装 APK 的固定配对需要重新打包。下载安装、覆盖升级和手动构建见[Android 教程](../frontend/android/README.md)；签名、包内配置与恢复见[分发维护](../deploy/ANDROID.md)。

## 预览保留与回收

main 入口长期保留；打开的 PR 保留至关闭，未关联 PR 的分支预览租约为 72 小时，成功部署续期。关闭或删除分支撤销对应入口，重开后复用尚在的产物或重新构建。

固定绑定与安装包独立保留后端，不按浏览人数计算。释放最后一个引用后等待一小时再清理；清理失败继续保留占用并重试，不静默回退 staging。具体引用、端口预约和中断恢复见[生命周期维护](../deploy/README.md#保留关闭重开和回收)，APK 有效期与覆盖升级见[安装教程](../frontend/android/README.md#5-下载安装和覆盖升级)。

## 客户端模式与后续正式发布约定

前端内部工具开关已经由源码构建配置控制，配置文件和详细教程见[前端 README](../frontend/README.md#内部调试工具与构建模式)。课程机预览构建参数由[网页发布说明](../deploy/WEB_PREVIEW.md#网页预览构建边界)维护。

后续正式发布遵循：选定 main 提交 → 生成 production 候选产物 → 成员验收该产物 → 固定 Tag → 发布正式 Release → 部署已验收产物。main push/PR 仍用于测试，不自动替换正式环境。正式发布建议由 `release.published` 触发，并过滤 `prerelease=true`；草稿和预发布不执行正式部署。Release 已公开与正式服务部署成功分别记录；部署失败保留上一成功服务并提供重试记录。

未来发布程序需校验候选提交、构建模式、目标平台和校验值，禁止复用同 SHA 的测试产物作为正式包；客户端和 API 配置匹配，生产配置缺失时拒绝发布。正式凭证通过 production 环境配置管理，不进入客户端 `.env` 或产物。

正式 API 配置、production 服务器部署和 release/tag 触发工作流尚未提供。production 客户端构建已剔除内部工具，但仍含样例业务数据。Android 已有测试签名分发，与正式发布分开维护。

参考：[GitHub Release 事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#release)、[部署环境](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments)。

## 发布与正式部署

staging 整体验收后记录 SHA，再建立 Tag、Release 与发布说明。Release 可附 APK、指南和版本信息。生产使用独立配置与明确授权，不复用临时预览清理；创建 Release 本身不会部署。

## 验证记录索引

历史记录保留为证据，不作为当前操作步骤。新的提交版本、检查结果及未测项记录在对应 PR / Actions。

- 后端初始化与环境管理：[PR #32](https://github.com/TomoriKaho/Livelife/pull/32)、[PR #34](https://github.com/TomoriKaho/Livelife/pull/34)、[main 运行](https://github.com/TomoriKaho/Livelife/actions/runs/37503098101)。
- 网页与统一构建：[PR #37](https://github.com/TomoriKaho/Livelife/pull/37)、[main 网页运行](https://github.com/TomoriKaho/Livelife/actions/runs/37613254277)、[PR 网页运行](https://github.com/TomoriKaho/Livelife/actions/runs/37613465083)。
- Android 工程及自动分发：[PR #41](https://github.com/TomoriKaho/Livelife/pull/41)、[PR #45](https://github.com/TomoriKaho/Livelife/pull/45)、[分发运行](https://github.com/TomoriKaho/Livelife/actions/runs/37734472930)。
- SSH 复用与恢复：[PR #46](https://github.com/TomoriKaho/Livelife/pull/46)、[后端控制运行](https://github.com/TomoriKaho/Livelife/actions/runs/37734442654)、[前端控制运行](https://github.com/TomoriKaho/Livelife/actions/runs/37734442730)。
- 独立服务器验证、旧 Basic/key 迁移和当时的备份位置：[迁移前部署记录](https://github.com/TomoriKaho/Livelife/blob/fbdc35694a2aa3f84ae5dc1a2737eceee27c16e3/docs/deployment.md#故障回滚与验证记录)。
- Android 候选包校验值、设备安装及早期启用记录：[迁移前 Android 记录](https://github.com/TomoriKaho/Livelife/blob/fbdc35694a2aa3f84ae5dc1a2737eceee27c16e3/docs/deployment/android-apk.md#实施记录)。
