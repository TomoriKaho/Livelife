# Agent 对话 API

## 长期多会话

账号会话永久保留，直至用户删除或注销。新接口仅以账户 Bearer 认证及路径中的会话 UUID 定位资源；所有操作核对所有者，其他账号与不存在资源统一返回 404。登录令牌有效期不影响历史保留。旧 header 接口仅保留为当前账号的兼容入口。

- `POST /agent/sessions` 创建空会话，返回 `session_id/title/created_at/updated_at/expires_at`（长期会话 expires_at 为 null）；兼容返回的 session_token 不作为跨设备恢复所需凭据。
- `GET /agent/sessions?query=&limit=20&offset=0` 按最近提问时间、ID 倒序列出本账号会话；query 对标题及消息做字面子串查找，返回 items 和 next_offset。
- `GET /agent/sessions/{session_id}?limit=50&before=` 返回最近一页消息（页内按顺序升序）、会话元数据及 next_before；before 为消息顺序号。保留状态、请求标识、引用快照及反馈，不因刷新把 pending 改成 failed。
- `POST /agent/sessions/{session_id}/messages/stream`、`POST /agent/sessions/{session_id}/messages/{message_id}/rating` 沿用现有流和反馈语义。
- `DELETE /agent/sessions/{session_id}` 永久删除会话、消息及引用；活跃请求未结束时返回现有 429 user_request_in_progress，不退还额度。

发送可以携带 `location: {latitude,longitude,accuracy,timestamp}`；时间戳为 Unix 毫秒，位置必须在两分钟内、最多允许十秒设备时钟超前。无授权/过期位置前端不附带，不阻塞提问；服务端不采纳过期位置。服务端接收时间（同时标注北京时间）与有效位置只加入本轮最新 user message 的上下文并计入输入预算，坐标不写入对话数据库或日志。用户原文或模型回答主动提到的地点仍属于消息正文。

升级迁移一次性清除升级前的所有开发对话，不迁移、不认领匿名行；保留账户与额度，旧在途预留保守计入已用并解除活动标记。不会在每次启动清空新会话。迁移降级不能恢复已删除的旧对话，部署前需停止在途请求并配套更新客户端。

API 前缀为 `/agent`。所有端点（包括创建）必须携带账户接口签发的 `Authorization: Bearer <access_token>`。新客户端使用路径中的会话 ID；下列兼容端点仍可携带 `X-Agent-Session: <session_token>` 定位对话；服务端同时核对账户与会话所有者，不能用 Agent token、会话 ID 或客户端提交的 user_id 代替账户认证。内置共享测试账号始终返回 403，即使本地显式开启空白登录。

兼容 Agent token 只在创建时返回，数据库保存 HMAC 摘要；新客户端不保存该令牌，只缓存按账号和 API 地址绑定的当前会话 ID。历史保存在服务端，关闭页面或重新登录不会删除会话。

## 临时新对话与置顶

客户端“新建对话”只切换至唯一临时条目，不调用创建接口；首次发送时才创建会话并发送消息。重复点击复用该条目，空历史进入页面也不创建。临时选中提示绑定账号/API 地址，消息草稿仅在当前页面内存保留。创建或发送失败显示重试，已取得会话 ID 后重试复用它，不再次创建。

`PATCH /agent/sessions/{session_id}` 请求 `{"is_pinned":true}` 或 `false`，返回 `SessionSummary`。仅本人可操作；不存在或他人会话为 404，认证错误沿用现有 401/403。字段严格为布尔值，不接受额外字段。摘要增加 `is_pinned`；列表先按置顶降序，再按更新时间、UUID 倒序，分页及查找沿用该顺序。操作幂等，不改变对话更新时间、消息或额度。

迁移 `0007_agent_pins` 新增布尔字段，已有会话默认未置顶，不删除历史。部署前执行升级；降级只移除置顶状态，不删除消息。

## `POST /agent/sessions`

创建会话并返回 `session_id`、一次性明文 `session_token` 和 `expires_at`。创建和发送请求都计入按来源 IP 的小时限制。当前默认每小时 30 次。

## `GET /agent/sessions/current`

兼容端点返回该凭据所属会话的完整消息与来源；仍必须同时携带账户认证。新客户端使用分页路径接口，消息与引用快照存于独立消息表。

## `POST /agent/messages/stream`

请求为 JSON：

```json
{
  "content": "百讲今天有什么活动？",
  "client_request_id": "e6c13b76-9ca8-4c62-9388-4ad3a864d13e"
}
```

问题去首尾空白后必须为 1–4000 字符；不接受附件。成功返回 `text/event-stream`：

| 事件 | 数据 | 含义 |
| --- | --- | --- |
| `message_start` | `message_id`, `request_id` | 创建回答消息 |
| `citation` | `rank`, `information_id`, `title`, `source_url`, `platform`, `source_id`, `published_at`, `activity_location`, `activity_start_at`, `activity_end_at`, `registration_deadline_at`, `snippet` | 检索到的来源 |
| `delta` | `text` | 新增回答文本 |
| `usage` | `input_tokens`, `output_tokens`, `estimated` | 本次用量；缺少模型 usage 时按实际发送的消息内容字符数估算 |
| `done` | `message_id`, `status` | 正常完成 |
| `error` | `code`, `retryable` | 模型流或服务异常 |

同一 `client_request_id` 的已完成请求只重放已保存回答，不再次调用模型；尚未结束的请求返回 `409`。模型已配置时，即使本轮没有检索到来源，也会将问题和有限历史交给模型，以支持问候、能力介绍和澄清；校园事实仍必须由本轮新检索到的公开记录支撑。历史对话仅用于理解指代和上下文，不能作为事实证据或沿用旧来源。若模型未配置且没有检索来源，返回“我目前没有找到足够的公开资料来回答这个问题。”。

## `POST /agent/messages/{message_id}/rating`

请求：`{"rating":"like"}`、`{"rating":"dislike"}` 或 `{"rating":null}`。只能修改当前会话中的已完成助手消息。

## `POST /agent/sessions/close`

删除当前账户拥有的会话和其中的消息、来源；用户用量不删除、不返还。仍有活动请求时返回 429，先结束请求再关闭。

## 限制与错误

- 默认每用户 5 次/分钟、每用户最多 1 个活跃请求（跨会话、跨登录令牌共用）；默认每来源 IP 30 次/小时；每用户 UTC 日 token 上限默认 100,000。频率和 token 上限可由后端环境变量覆盖。
- 超频、并发或 token 额度用尽返回 `429` 和 `detail.code`；适用时带 `Retry-After`。
- 账户凭证缺失、撤销、过期或账户删除返回 401 和 `WWW-Authenticate: Bearer`；共享测试账号返回 403。兼容 header 端点凭据缺失返回 401 `session_token_required`、错误 token 返回 401 `invalid_session`；路径 ID 端点不存在或不属本人返回 404 `session_not_found`。新会话没有时间过期；仅兼容显式过期的旧记录返回 404 `session_expired`。问题过长返回 413；未配置数据库或会话密钥返回 503。
- IP 限流使用 Uvicorn 可信代理解析后的连接地址，再保存 HMAC 摘要；应用不直接信任请求中的 `X-Forwarded-For` 字符串。
- 只有当前公开信息表中的记录可作为事实证据并生成来源引用。来源正文、用户消息和历史对话均视为不可信输入；历史只帮助补全明确的追问（例如“这个课的老师是什么”），检索仍需从公开记录取得新证据。模型不得声称能访问尚未接入的实时课表、选课、提醒或地图操作能力。

用量预留和缺少模型 usage 时的输入估算共用模型请求的消息组装逻辑：计入系统提示、公开记录包装及裁剪后的历史，排除未发送的旧消息与被截断内容；预留另包含最大输出额度。估算仍为字符数近似，不等同于供应商账单。用户额度行在事务中加锁，创建/关闭对话不会重置计数；完成按实际 usage 或估算结算，失败、取消或活动租约过期保守计入预留额，避免中途断开恢复额度。跨 UTC 日清零已用额但保留在途预留，结算归入完成日。旧会话上的用量列仅为迁移兼容保留，不再作为限制依据。

## 登录失效与迁移

每个 HTTP 操作复用账户会话校验。SSE（含已完成回答重放）在开始、每个事件输出前及等待上游时每秒使用新数据库会话重新检查账户登录态；发现撤销、过期或删除后关闭上游流并发送 `error: {code: "authentication_required", retryable: false}`，不再发送后续内容或 done。整个流还受 `AGENT_LLM_TIMEOUT_SECONDS` 的总时限限制（不只是网络空闲超时），时限早于活动租约；持续输出不能占用超过租约后再开启并发模型请求。已经发送给供应商的请求无法撤回，仍保守结算；正在输出的片段不可能追溯收回。内部清理使用已授权的用户和请求标识，不依赖失效凭证，且重复清理不重复扣费。

迁移 `0005_agent_account_auth` 添加可空的 `agent_sessions.user_id` 和独立 `agent_user_usage` 表；旧匿名行曾保留 NULL；`0006_agent_history` 按开发阶段决定一次性删除全部旧会话，并建立独立消息表及长期会话索引。账户注销同时删除其 Agent 对话与额度记录。新旧客户端鉴权不兼容，必须一起更新网页/Android；旧客户端无法调用受保护端点。降级移除归属与用户额度，回退旧 API 会恢复匿名能力，需先撤下模型凭证并限制入口。

当前检索只查询公开信息，尚无 LLM 工具调用框架。后续工具调用必须由服务端沿用已验证的用户身份、再核对操作权限；不能信任模型生成的 user_id，也不能向模型传递账户令牌或 API Key。

## 配置与本地联调

模型地址、模型名、API key、会话 HMAC 密钥及限制项见[后端 Agent 配置](../../../README.md#agent-服务配置)。迁移由本地开发入口自动执行；独立数据库环境需按后端 README 手动运行 Alembic。模型服务收到用户问题、最近对话及有限的公开来源片段；日志不记录完整 prompt 或密钥。

## 上下文预算与历史恢复

完整消息永久保留与模型输入裁剪分离。每轮从本会话读取最近 8 条已完成消息、最近有原始来源的任务及其用户问题、少量与本轮问题匹配的历史片段，不生成新的摘要事实。追问按这些线索重新读取公开信息；已经删除的公开记录不以旧回答或引用片段替代为当前证据。新轮次的引用编号仅对应本轮来源。

`AGENT_MAX_CONTEXT_CHARS` 约束历史文本与公开记录文本的数据预算；有来源时历史最多占一半，剩余留给证据，防止长历史挤掉来源。系统提示和固定包装是额外的有界开销，用量预留及估算仍计入实际发送的全部消息。优先保留当前问题，再保留任务线索，最后填充近期对话；不无限拼接历史。服务端时间和有效定位随本轮问题计入同一历史文本预算。

历史保留 completed/failed/cancelled/pending 原状态。仍在有效租约中的 pending 不由客户端改写；租约过期后读取详情会将该请求恢复为 failed、释放活动标记并保守结算预留，重复读取不重复扣费。#71 的上游异常终态与 #72 的失败重试语义仍由各自任务独立修复，不能把本功能视为这些问题已解决。
