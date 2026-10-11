# 健康检查 API

本模块提供进程存活与数据库就绪检查。[router.py](router.py) 定义 `/health` 路由，由[总路由](../router.py)注册。响应字段类型见 [HealthResponse](../../schemas/health.py)和生成的 OpenAPI。

共享约定、模块索引和 OpenAPI 入口见[API 文档入口](../../../../docs/api.md)；启动与数据库配置见[后端 README](../../../README.md)。以下路径不包含部署前缀。

## 健康检查

两个接口均为 GET，无请求体或必需查询参数，无需登录，返回 `application/json`。字段类型和可选值由 `HealthResponse` 定义，可从 OpenAPI 查看；接口不返回数据库地址、凭证或底层连接异常。

| 方法与路径 | 条件 | 状态码 | 响应 |
| --- | --- | --- | --- |
| `GET /health/live` | 应用可响应，不访问数据库 | 200 | `{"status":"ok","database":null}` |
| `GET /health/ready` | 未配置数据库 | 503 | `{"status":"not_ready","database":"not_configured"}` |
| `GET /health/ready` | 数据库连接或查询触发 SQLAlchemy 异常 | 503 | `{"status":"not_ready","database":"unavailable"}` |
| `GET /health/ready` | 数据库 `SELECT 1` 成功 | 200 | `{"status":"ok","database":"connected"}` |

就绪成功仅表示连接可用，不代表业务表、迁移或业务功能就绪。未配置数据库时 hello 仍可调用；当前部署探针仍使用 hello。配置、调用命令和迁移限制见[后端说明](../../../README.md#数据库配置与健康检查)。
