# 个人资料 API

基址使用后端 API 基址，不含部署前缀。本模块维护兴趣标签目录，以及当前登录用户的资料读取与更新；成功及错误响应遵循 FastAPI 的 JSON 结构，不增加统一响应包裹。

身份说明：`GET /profile/me` 与 `PATCH /profile/me` 使用 `Authorization: Bearer <access_token>`。当前身份依赖是 [deps.py](deps.py) 中的临时实现（由 Bearer 令牌摘要派生稳定用户标识），只用于在账户系统合并前保持路由、契约与前端调用稳定。账户系统（#65）合入 main 后，该文件整体替换为真实登录校验，并把 `user_profiles.user_id` 补到 `users.id` 外键；替换前不得用于正式环境。

## `GET /profile/interests`

无需登录。返回固定兴趣标签目录，供页面勾选：

```json
[{"tag":"sport","label":"体育运动"},{"tag":"film","label":"电影放映"}]
```

标签标识与 `frontend/src/pages/onboarding/options.js` 的 `interests` 一致；服务端以本目录为唯一校验来源。

## `GET /profile/me`

需要 Bearer 令牌。首次读取时创建空资料。响应：

```json
{"display_name":"","bio":"","interests":[]}
```

## `PATCH /profile/me`

需要 Bearer 令牌。请求字段均可省略，只更新出现的字段：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `display_name` | string | 去除首尾空格后 1–32 字符 |
| `bio` | string | 去除首尾空格后不超过 200 字符 |
| `interests` | string[] | 不超过 10 个、必须来自标签目录、不可重复；整体替换已有选择 |

成功返回更新后的同一结构；`interests` 按标签目录顺序返回。

| 条件 | 状态码 | 说明 |
| --- | --- | --- |
| 成功 | 200 | 返回更新后的资料 |
| 兴趣标签不在目录内或重复 | 400 | `detail` 说明原因 |
| 缺少、失效或过期凭证 | 401 | 响应带 `WWW-Authenticate: Bearer` |
| 字段类型或长度不符合约束 | 422 | FastAPI 校验错误 |
| 未配置数据库 | 503 | `detail` 为 `Database is not configured` |

资料与兴趣写入在同一次事务内完成；兴趣整体替换不保留旧标签。受保护接口响应带 `Cache-Control: no-store`。
