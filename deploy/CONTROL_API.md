# 部署控制接口

本文维护受限 SSH JSON 请求、输入边界与返回字段，供控制器和维护工具使用。它们不属于业务 FastAPI；前后端业务契约见[API 入口](../docs/api.md)。服务器初始化、密钥与恢复见[维护说明](README.md)。

## 后端控制接口

部署工具使用同一专用 SSH JSON RPC，响应 JSON，失败时非零退出且包含 error。generation 为 `GitHub run_id * 1000 + run_attempt`，自动部署使用原始构建 run 的 generation：

公网入口以一个完整 JSON 对象作为请求边界，按块读取并限制总输入 96 MiB；不等待 SSH stdin 的 EOF 才执行。兼容旧控制器不带换行的请求，新控制器在 JSON 后附换行。引号、转义、嵌套对象和数组必须解析完整，不接受同一已读块里的额外非空白数据。客户端优化包括 SSH 压缩、15 秒 keepalive 和连续 3 次无响应断开；单次 RPC 上限 1800 秒，控制 job 上限 45 分钟。自动控制器使用 main 上的实现。日志仅记录操作名称和请求字节数，不输出请求体或凭证。

`livelife-recover.service` 直接执行 `public-entry.py recover`，无需 shell 拼接 JSON。强制 SSH 命令仍不带这个参数，继续只接收标准输入 JSON，不取得通用 shell 能力。

| op | 输入 | 行为 |
| --- | --- | --- |
| lookup | owner，如 frontend:41/main | 返回版本和 API 地址 |
| bind | frontend owner、target、generation、frontend_sha | 解析并保留固定引用；staging 显式跟随 main |
| release | owner、generation | 幂等释放，禁止 main |
| snapshot | 无 | 返回实例、引用与 branch_databases |
| collect / recover | 无 | 延迟清理 / 恢复进程、检查健康 |
| deploy | owner、sha、generation、可选 database；上传时另含 bundle、digest | 无包请求先复用已登记版本；不存在返回 upload_required，不占端口或更新 generation；上传校验完整包，不公开 HTTP 管理入口 |

后端 `deploy` / `deploy_built` / `recover` 对明确选择 `postgres-v1` 的 release 使用受信启动器准备按分支持久的 PostgreSQL（无 database 字段的历史请求保留按 SHA 隔离）、执行迁移、校验实际业务表，并要求数据库探针成功才发布。旧 metadata 无模式时保持 legacy；新产物通过 `backend/preview-runtime.json` 显式选择模式。失败沿用原有候选清理及旧引用保留语义。RPC 不接收任意数据库连接、凭证或模式修改字段。生命周期和升级见[预览数据库说明](README.md#预览数据库与启动门禁)。

`deploy` / `deploy_built` 可带 `database: {"branch":"feature", "source_branch":"main"}`，新自动控制器始终发送；PR base 来自可信 GitHub metadata，未开 PR 默认 main。可选 `source_owner` 是来源分支尚未升级时的旧预览引用（如 `pr:82`）。公网仅首次登记来源，后续请求沿用既有记录；`snapshot` 额外返回 `branch_databases`。课程机接收由公网解析的 `database: {id, branch, source, source_branch, copy_mode}`，source 只能是受校验的分支库或旧实例 ID，不接受任意路径、连接或凭证。release metadata 固化配置，recover 不需要重传；回收不删除分支数据。 `copy_mode` 由公网依据原有同分支引用选择：同分支旧预览升级为 `full`（所有业务数据及原 Agent 密钥），新分支为 `public`（仅公开数据、独立密钥）；公网部署请求不接受调用方指定此字段。旧记录缺少该字段时仍按 `public` 处理，已初始化库不重新导入；模式在来源记录和 release metadata 中固定。

新实例 ID 为 `be-<40位代码SHA>-<32位分支摘要>`，旧 `be-SHA` 仍有效；lookup 返回的 `backend_sha` 和响应版本头仍为代码 SHA。所有客户端应使用返回的 `api_base_url`；网页及 APK 校验允许可选 32 位后缀，同时仍强制 SHA、origin、路径匹配。历史固定版本 URL 不变，固定代码不意味着数据库也冻结。来源、迁移失败与升级限制见[生命周期](README.md#预览数据库与启动门禁)。

课程机内部只读请求 `{"op":"health_policy","port":18000}` 按已安装 release metadata 返回 `runtime_mode` 和 `require_database`；没有唯一匹配或模式非法时失败。课程机 ensure 同时返回这两个字段。公网 ensure 使用返回模式，独立 bind 健康检查重新读取课程机策略，不依赖进程缓存、不把 readiness 失败降级成 hello 成功。该操作不通过公网 dispatch 暴露。

维护者可用专用密钥测试控制接口，先在本地准备权限 600 的密钥与已核对的 known_hosts，再执行：

```bash
ssh -T -i /私有路径/actions_ed25519 \
  -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/私有路径/public_known_hosts \
  livelife@192.144.253.40 <<'JSON'
{"op":"snapshot"}
JSON
```

此密钥只能调用工具，不支持远程 shell、SCP 或隧道。lookup 示例为 `{"op":"lookup","owner":"main"}`；尚无部署时返回明确错误。普通成员使用 Actions 页面操作，避免分发部署私钥。

前端切换失败时保留旧绑定，关闭 PR 才释放它的引用。网页与 APK 分别使用后文的发布接口。

## 网页控制接口

原有后端操作兼容。以下操作同样通过既有 SSH 接口调用，不公开 HTTP 管理端点：

| op | 主要输入 | 作用 |
| --- | --- | --- |
| web_publish | environment、branch、pr、source_sha、generation、manifest+base64 bundle 或 build_id、target、mode | 校验静态包、保存等待记录、配对成功后原子发布 |
| web_lookup | environment | 返回状态、网页 URL、版本、API、到期时间及当前检查结果 |
| web_release | environment、generation | 撤销分支和 PR 别名；main 禁止释放 |
| web_rollback | environment、generation | 恢复上一成功页面及其后端引用 |
| web_note | environment、component、source_sha、generation、status | 记录经 GitHub 验证的构建状态 |

generation 使用原构建 run_id * 1000 + attempt；关闭和手动操作使用对应控制运行编号。内容与显式选择分别排序，旧上传、关闭后的晚到任务及前端更新不能覆盖较新的显式绑定。返回状态 ready / waiting / failed / released / superseded；waiting/failed 可能带上一成功版本，不能作为最新提交验收结果。

可在 Actions → Preview environments → Run workflow 使用 web-lookup / web-release / web-rollback，填写 frontend_pr 或 frontend_branch（二选一）。未发 PR 的显式绑定也可填写 frontend_branch；创建 PR 时迁移为永久 PR 选择记录。bind 的 backend_target 支持 staging、pr-编号及仍存在的 be-SHA；跨 PR 解析并固定最新成功 SHA，未部署最新提交时拒绝替换旧绑定。

## 构建控制接口

| op | 字段 | 返回/作用 |
| --- | --- | --- |
| build_submit | component=frontend/backend、sha、branch、run_id、attempt | job id、queued/running/终态；不等待构建结束 |
| build_status | job、offset=0 | 状态、最多 32 KiB 日志、新 offset、检查结果 manifest |
| deploy_built | owner、sha、generation、job、可选 database | 仅接受该 SHA 已通过的后端任务，复用测试 venv |
| web_publish_built | 原 web_publish 环境/配对字段、source_sha、job | 公网机从课程机取已通过的网页包，再按原契约发布 |

build_artifact 是公网机 → 课程机的内部操作，验证 frontend/sha 后返回包和 manifest；不提供浏览器下载接口。部署失败在 Preview environments 查看日志；检查失败查看 commit 状态和 course-build-logs；请求已成功但无实际状态时先确认新控制工作流已合入 main、enabled 至少一个开启，再查看控制运行与 build-worker 日志。

## Android 控制接口

现有受限 SSH JSON RPC 增加：

| op | 输入与结果 |
|---|---|
| apk_reserve | environment、branch、sha、generation、target、mode、explicit、force；分配版本并持久保留后端，返回内置配置 |
| apk_lookup | environment；返回本次状态、上一成功包及显式选择 |
| apk_publish_built | apk_id、job；从课程机读取已通过的未签名 APK，校验、签名、发布 |
| apk_fail | apk_id、error；记录失败、释放候选引用 |
| apk_release | environment、generation；关闭入口并释放该环境包，main 禁止释放 |

课程内部 build_submit 增加 component=android 和 config；build_artifact 增加 component=android，仍严格匹配已成功的任务及 SHA。android_tools 仅传输固定项目工具目录，是维护接口，不提供任意文件读取。
