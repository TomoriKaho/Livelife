# 连通性与健康检查 API

本文维护当前路由目录中的 hello 和健康检查契约。hello 由 [test.py](test.py) 实现，健康检查由 [health.py](health.py) 实现，统一通过 [router.py](router.py) 注册。响应字段类型见 [hello 模型](../schemas/hello.py)、[health 模型](../schemas/health.py)及生成的 OpenAPI。

共享约定、接口索引和 OpenAPI 入口见[API 文档入口](../../../docs/api.md)；启动、CORS 和数据库配置见[后端 README](../../README.md)。以下路径不包含部署前缀。

## GET /test/hello

用于检查客户端与后端连通性。

| 项目 | 约定 |
| --- | --- |
| 方法与路径 | `GET /test/hello` |
| 身份要求 | 无需登录 |
| 请求 | 无请求体，无必需查询参数 |
| 成功状态 | HTTP 200，`application/json` |
| 响应字段 | `message`：字符串，值为 `hello world` |

请求与成功响应：

```bash
curl -i http://127.0.0.1:8000/test/hello
```

```json
{"message":"hello world"}
```

未知路径返回 HTTP 404、`{"detail":"Not Found"}`；对 hello 使用 POST 返回 HTTP 405、`{"detail":"Method Not Allowed"}`。沿用 FastAPI 的 `detail` 响应，不为演示接口增加业务错误包裹。

网络不可达、客户端超时及无效响应的处理见[客户端调用说明](../../../frontend/src/api/README.md#hello-调用与失败处理)。测试网关提供 `X-Livelife-Backend-SHA` 版本头，本地 Uvicorn 不自动生成；配对规则见[部署入口](../../../docs/deployment.md#api-地址与前端关联)。

## 健康检查

两个接口均为 GET，无请求体或必需查询参数，无需登录，返回 `application/json`。字段类型和可选值由 `HealthResponse` 定义，可从 OpenAPI 查看；接口不返回数据库地址、凭证或底层连接异常。

| 方法与路径 | 条件 | 状态码 | 响应 |
| --- | --- | --- | --- |
| `GET /health/live` | 应用可响应，不访问数据库 | 200 | `{"status":"ok","database":null}` |
| `GET /health/ready` | 未配置数据库 | 503 | `{"status":"not_ready","database":"not_configured"}` |
| `GET /health/ready` | 数据库连接或查询触发 SQLAlchemy 异常 | 503 | `{"status":"not_ready","database":"unavailable"}` |
| `GET /health/ready` | 数据库 `SELECT 1` 成功 | 200 | `{"status":"ok","database":"connected"}` |

就绪成功仅表示连接可用，不代表业务表、迁移或业务功能就绪。未配置数据库时 hello 仍可调用；当前部署探针仍使用 hello。配置、调用命令和迁移限制见[后端说明](../../README.md#数据库配置与健康检查)。
