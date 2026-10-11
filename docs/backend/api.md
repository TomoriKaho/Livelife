# 后端 API 接口

后端使用 FastAPI 的 `APIRouter` 组织接口。它承担与 Flask Blueprint 类似的模块注册职责：每个接口域维护自己的 router，由 `backend/app/api/router.py` 统一注册，`main.py` 只负责创建应用和注册总 router。

## 当前接口

| Router | 方法与路径 | 用途 |
| --- | --- | --- |
| `health` | `GET /health/live` | 进程存活检查，不依赖数据库 |
| `health` | `GET /health/ready` | 检查可选 PostgreSQL 连接 |

当前没有业务 router。这样 OpenAPI 只描述已经存在的健康检查契约；首个业务契约确定后，再新增对应模块。

## 新增业务接口的约定

新增接口时，为对应域创建一个 `APIRouter` 文件，在 `router.py` 注册，并同时确定请求/响应 schema、鉴权要求、错误结构、分页规则和时间格式。路由只处理 HTTP 校验、依赖注入和响应映射；业务流程放入 `services/`，持久化操作放入 `repositories/sql/`，ORM 模型放入 `db/models/`。

示例：

```text
backend/app/api/
├── router.py       # 统一注册
├── health.py       # /health
```

确认某个业务契约后，才按业务域添加 `accounts.py`、`content.py` 等 router 及其 schema/service。未确定的业务不创建空文件或返回 501 的接口。
