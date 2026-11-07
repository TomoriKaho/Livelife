# Agent 对话 API

API 前缀为 `/agent`。本模块服务未登录用户；所有会话读取、发送和反馈请求都必须携带 `Authorization: Bearer <session_token>`。令牌只在创建会话时返回，数据库保存 HMAC 摘要。会话在最后一次提问后 24 小时过期。

## `POST /agent/sessions`

创建会话并返回 `session_id`、一次性明文 `session_token` 和 `expires_at`。创建和发送请求都计入按来源 IP 的小时限制。当前默认每小时 30 次。

## `GET /agent/sessions/current`

返回该令牌所属当前会话的消息及来源。会话 ID 不能代替令牌授权。消息和来源快照保存在同一条短期会话记录中。

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
| `usage` | `input_tokens`, `output_tokens`, `estimated` | 本次用量；缺少模型 usage 时使用估算 |
| `done` | `message_id`, `status` | 正常完成 |
| `error` | `code`, `retryable` | 模型流或服务异常 |

同一 `client_request_id` 的已完成请求只重放已保存回答，不再次调用模型；尚未结束的请求返回 `409`。资料不足时返回固定提示，不调用模型。

## `POST /agent/messages/{message_id}/rating`

请求：`{"rating":"like"}`、`{"rating":"dislike"}` 或 `{"rating":null}`。只能修改当前会话中的已完成助手消息。

## `POST /agent/sessions/close`

删除当前匿名会话和其中的消息、来源及用量统计。不存在单独的跨会话用户档案。

## 限制与错误

- 默认每会话 5 次/分钟、每会话固定最多 1 个活跃请求；默认每来源 IP 30 次/小时；每会话 UTC 日 token 上限默认 100,000。频率和 token 上限可由后端环境变量覆盖。
- 超频、并发或 token 额度用尽返回 `429` 和 `detail.code`；适用时带 `Retry-After`。
- 会话 token 缺失/错误返回 `401`；会话过期返回 `404`；问题过长返回 `413`；未配置数据库或会话密钥返回 `503`。
- IP 限流使用 Uvicorn 可信代理解析后的连接地址，再保存 HMAC 摘要；应用不直接信任请求中的 `X-Forwarded-For` 字符串。
- 只有当前公开信息表中的记录可进入模型上下文。来源正文视为不可信输入；模型必须引用资料且不能补造信息。

## 配置与本地联调

模型地址、模型名、API key、会话 HMAC 密钥及限制项见[后端 Agent 配置](../../../README.md#agent-服务配置)。迁移由本地开发入口自动执行；独立数据库环境需按后端 README 手动运行 Alembic。模型服务收到用户问题、最近对话及有限的公开来源片段；日志不记录完整 prompt 或密钥。
