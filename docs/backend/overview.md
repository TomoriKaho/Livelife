# 后端总览

后端位于 `backend/`，采用 Python、FastAPI、Pydantic、PostgreSQL、SQLAlchemy 和 Alembic。当前提供应用入口、健康检查、可选数据库连接、Session 管理和迁移配置；业务服务目录用于表达领域边界，尚未包含具体业务用例。

## 目录结构

```text
backend/
├── app/
│   ├── main.py              # 创建 FastAPI 应用、生命周期、CORS 和总路由
│   ├── api/                 # HTTP 路由模块，类似 Flask Blueprint
│   │   ├── router.py        # 统一注册 APIRouter
│   │   ├── health.py        # /health/live、/health/ready
│   │   └── 业务路由文件      # 按契约逐步加入
│   ├── schemas/             # Pydantic 请求与响应模型
│   ├── core/                # 配置和公共基础设施
│   ├── db/                  # PostgreSQL、SQLAlchemy Engine 和 Session
│   │   └── models/           # ORM Base 与业务 ORM 模型
│   ├── repositories/        # 持久化访问边界
│   │   └── sql/              # SQLAlchemy 查询和写入
│   └── services/             # 按业务域组织的业务用例
├── migrations/              # Alembic 环境和版本迁移
├── tests/                   # 后端自动化测试
├── alembic.ini              # Alembic 配置
├── pyproject.toml           # 依赖、pytest 和 Ruff 配置
└── uv.lock                  # 锁定依赖
```

## 请求处理边界

请求从 `main.py` 创建的 FastAPI 应用进入 `api/` 路由。路由负责路径、参数校验、依赖注入和 HTTP 响应；需要数据库时通过 `db/` 提供的 Session 访问持久化层。业务流程放在 `services/`，数据读写放在 `repositories/sql/`，数据结构放在 `db/models/` 和 `schemas/`。服务用例显式接收 Session，并负责事务提交或回滚；repository 只执行数据操作。

## 当前服务分块

`services/` 当前按产品领域预留以下包。每个包目前仅表示职责边界，不代表对应功能已经实现：

| 服务包 | 负责范围 |
| --- | --- |
| `accounts/` | 注册、登录、退出、当前用户、密码和身份鉴权 |
| `preferences/` | 用户资料、兴趣标签、推荐开关和通知偏好 |
| `content/` | 信息流、文章和活动内容 |
| `locations/` | 地点、地图关联和附近查询 |
| `favorites/` | 活动收藏与取消收藏 |
| `reactions/` | 表情表态、表情目录及分数映射 |
| `agent/` | Agent 问答、来源依据和历史对话 |
| `comments/` | 评论或互动能力；是否纳入产品范围待确认 |
| `ingestion/` | 公开信源采集、去重、分类和内容提取 |
| `recommendations/` | 根据用户偏好生成推荐 |
| `notifications/` | 通知偏好、设备和推送记录 |

首个业务契约确定后，在相应服务包中添加具体用例，再由 API router 调用。没有契约时不应继续扩展空的通用 service、repository 或业务模型。

## 数据库基座

`DATABASE_URL` 是可选环境变量，使用 PostgreSQL SQLAlchemy URL，例如 `postgresql+psycopg://user:password@localhost:5432/livelife`。未配置时应用仍可启动，存活检查可用，就绪检查返回未就绪。Alembic 只负责迁移，不在应用启动时自动执行；当前迁移为空基线，没有预建业务表。

## 验证入口

在 `backend/` 目录运行：

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

具体 API 规划见 [API 规划](api.md)。
