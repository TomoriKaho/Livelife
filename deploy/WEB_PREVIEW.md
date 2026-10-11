# 网页预览实现与维护

#27 使用已有 HTTPS 443 和 Nginx，静态网页目录为 `/opt/livelife/web`；没有新增预览监听端口。网页通过同源 API 路径访问课程机后端；当前网页/API 直接访问，不要求预览 key。

运行时配置、静态文件和回滚由本文维护。入口和成员配对步骤见[部署入口](../docs/deployment.md)，RPC 字段见[控制接口](CONTROL_API.md#网页控制接口)。

## 地址和配对契约

以下地址均以 `https://192.144.253.40` 为前缀：

| 环境 | 网页路径 | 自动后端 |
| --- | --- | --- |
| main | `/staging/` | main 共享测试后端 |
| 无 PR 分支 | `/preview/branch-<摘要>/` | staging；自身后端改动时使用配套版本 |
| 打开的 PR | 原分支路径及 `/preview/pr-<编号>/` | 同上；两者指向同一部署 |
| 后端-only PR | `/preview/pr-<编号>/` | 自身后端，复用 main 最近成功前端 |
| 显式联调 | 网页地址不变 | bind 解析时的固定 SHA |

摘要是原分支名 UTF-8 的 SHA-256 前 32 位，不把分支名拼入路径。控制器根据 GitHub 当前 head、PR 状态和合并基线的 Git 树判断改动；自身后端未成功部署时显示等待/失败，保留上一成功页面。仅前端更新而 backend 目录树相同时可复用自身上一后端。前后端构建谁先完成都可以，配套成功后才发布。

无 PR 分支租约为 72 小时，成功部署续期；定期核对不续期。main 永久保留，打开的 PR 保留至关闭。PR 关闭/合并、分支删除、手动释放或过期撤销入口；其他环境的固定引用不受影响。重开优先复用尚在的产物，否则等待新构建。GitHub 仅上传构建日志并保留 7 天；课程机任务/网页包默认保留 7 天，这与公网已部署文件生命周期不同。

## 前端构建和运行时配置

`Frontend build request` 仅在 push、PR opened/synchronize/reopened 和手动选择分支时记录请求，不拉取项目或执行 npm。课程机使用固定 Node 24.13.0 / npm 11.6.2，按锁文件执行 npm ci、全部现有行为测试、类型检查和 Vite build，并由受信 prepare-frontend.py 打包。真正的结果回传为 SHA 上的 `Frontend checks`，日志由 Preview environments 展示并保留 7 天。静态包留在课程机，公网机直接通过 SSH 获取，不经过 GitHub Runner 上传大包。

`Preview environments` 从 main 读取控制代码，验证 GitHub 来源、当前提交、PR 状态与产物身份；fork 不提交课程机构建任务，也不取得部署凭证。只解析静态包，不执行产物中的脚本。安全边界参考 [workflow_run 官方说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run)。

每个入口的 `runtime-config.json` 最少包含：

```json
{
  "schema_version": 1,
  "environment": "main",
  "frontend_sha": "完整40位前端提交SHA",
  "build_id": "fe-完整SHA-构建运行编号-重试次数",
  "api_base_url": "https://192.144.253.40/api/staging/",
  "backend_mode": "staging",
  "backend_sha": "加载配置时的完整40位后端SHA"
}
```

示例中的中文为占位说明，不能直接用于发布。环境标识仅 main 或 branch-32位摘要；后端模式 staging / own / fixed。网页按当前入口读取配置后初始化 API；配置失败禁用接口测试并显示错误，不回退 localhost，样例页面仍可查看。配置 build_id 与当前 HTML 不一致时提示刷新，避免更新期间把旧页面标成新版本。

“我的 → 帮助与反馈 → 接口连通性测试”显示前端 SHA、构建号、后端模式和加载时 SHA；真实 hello 响应头记录实际后端 SHA。staging 可随 main 变化；own/fixed 的响应 SHA 不匹配时报告错误。网页切换配对仅更新配置，不重建前端；APK 使用[包内原生配置](ANDROID.md#原生配置契约)，需要重新打包。

## 网页预览构建边界

本地和后续原生构建继续使用相对资源基路径与 `VITE_API_BASE_URL`。课程机构建设置 `VITE_WEB_PREVIEW=true`、`VITE_WEB_BUILD_ID=fe-<SHA>-<run_id>-<attempt>`，并把 Vite base 设置为 `/__livelife/web-builds/<build_id>/`。仅网页预览启用字体、图片的共享哈希资源路径；地图 JSON、JS/CSS 及许可证保持不可变构建路径。升级 Vite 时必须检查 `experimental.renderBuiltUrl` 生成的 URL，并验证实际资源请求；实验性 API 依据见 [Vite 文档](https://vite.dev/guide/build#advanced-base-options)。

运行 `cd frontend && node --test scripts/*.test.mjs` 和 `npm run build` 进行前端检查。预览构建不要把本地 `.env` 中的开发地址或任何访问密码打入产物；真实 API 地址由受信控制器生成运行时配置。部署依赖、控制接口和启用步骤见 [网页配置](#网页预览实现与维护)。

## 静态文件、配额与恢复

JS/CSS、地图及许可证使用 `/__livelife/web-builds/<build_id>/`；字体和图片通过共享 `/__livelife/web-assets/assets/<哈希文件名>` 分发，硬链接按物理文件去重。HTML/config 无缓存，不可变资源长期缓存，已生成 gzip 文件由 [gzip_static](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html) 分发。API 独立限流，静态资源不参与 API 限流；目录列表关闭。项目日志由 `/etc/logrotate.d/livelife` 轮转。

每个环境保留当前和上一成功部署，分别登记 `web:<部署ID>` 后端引用，与 `frontend:<PR或分支标识>` 的选择记录和APK 引用分开。回滚恢复原部署的前端和后端配对；回滚后自动核对保持该页面，下一次成功前端构建才推进。候选发布之前提交持久化后端引用，网关验证成功才提交站点；失败保留旧页面。进程中断后 recover 先恢复数据库已提交的路由，再清理候选引用/文件。

默认物理网页上限 2 GiB，按去重后的文件 inode 计量；发布先回收经过宽限期的闲置文件，仍不足拒绝候选。无引用文件至少保留一小时。压缩包 64 MiB、展开 256 MiB、10000 条目；拒绝重复路径、穿越、链接和特殊文件。SSH JSON 请求上限 96 MiB，后端压缩包仍为 20 MiB。

当前字体原始约 22.2 MB、gzip 约 14.7 MB。5 Mbps 下首次完整字体传输理论约 24 秒，实际受协议和网络影响；共享缓存与 gzip 已实现，字体转换/拆分另行安排。

## 维护者启用顺序

1. 合并前运行前端行为测试/build、部署 unittest、ruff、actionlint 和服务器手动验证；由另一名成员正式评审。人工验证不需要启用自动网页开关。
2. 更新公网机 `/opt/livelife/control` 中的受信工具、项目 nginx.conf 和 logrotate 配置，创建 livelife 可写 `/opt/livelife/web`。先备份项目代码、网关配置和 SQLite，更新时持有项目锁；依赖保持现有 Python 控制环境。检查配置后只重载 livelife-gateway。既有后端操作须验证兼容。
3. 工作流合入 main 后设置 Repository Variable `LIVELIFE_FRONTEND_ENABLED=true`。后端开关保持现状；网页开关关闭不删除已部署页面，只停止自动网页管理。
4. 手动运行 Frontend build request，选择 main；等待 Preview environments 成功，检查 `/staging/` 配置/版本、直接访问、真实 hello。
5. 用两个开发分支和各类 PR 验证自动链接、单条评论、同分支配对、跨 PR 固定绑定、失败保留、关闭/重开与资源清理。尚未发 PR 的信息由控制 Actions Summary 给出。
6. 记录实际 SHA、构建 run、访问及测试结果。成员步骤见[预览验证](../docs/testing.md#预览链接与测试包)，网页与部署工具回归见[专项检查](tests/README.md#后端与网页环境回归)。

单条 PR 自动评论使用 `<!-- livelife-preview -->`，兼容升级旧后端评论，提供页面/版本/模式/API/状态；不包含认证信息。安装包由独立 Android 开关控制，正式发布另行安排。
