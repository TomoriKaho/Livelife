# 连通性检查 API

本模块提供 hello 接口，用于客户端与后端连通性测试。[router.py](router.py) 定义路由，由[总路由](../router.py)注册 `/test` 前缀及 demo 标签。响应字段类型见 [HelloResponse](../../schemas/hello.py)和生成的 OpenAPI。

共享约定、模块索引和 OpenAPI 入口见[API 文档入口](../../../../docs/api.md)；启动与 CORS 见[后端 README](../../../README.md)。以下路径不包含部署前缀。

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

网络不可达、客户端超时及无效响应的处理见[客户端调用说明](../../../../frontend/src/api/README.md#hello-调用与失败处理)。测试网关提供 `X-Livelife-Backend-SHA` 版本头，本地 Uvicorn 不自动生成；配对规则见[部署入口](../../../../docs/deployment.md#api-地址与前端关联)。
