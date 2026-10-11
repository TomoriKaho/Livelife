# 后端开发

后端使用 FastAPI 和 Pydantic，采用模块化单体。当前提供 `GET /test/hello` 连通性接口、存活与数据库就绪检查，以及[通用信息系统](app/services/content/README.md)的内部采集协议、持久化与查询服务。信息系统尚未接入真实平台或前端；无业务登录。HTTP 契约见[连通性检查 API](app/api/demo/API.md)和[健康检查 API](app/api/health/API.md)，共享约定与接口索引见[API 入口](../docs/api.md)，整体技术路线见[架构说明](../docs/architecture.md)。

## 后端安装、启动与检查

后端使用 Python 3.12（`>=3.12,<3.13`）和 uv 管理依赖，精确依赖版本由 `backend/uv.lock` 锁定。先按 [uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/) 安装 uv；macOS 已有 Homebrew 时可执行 `brew install uv`。仓库固定 Python 3.12 系列，补丁版本不限定。

从仓库根目录，在独立终端执行：

```bash
uv --version
cd backend
uv python install 3.12
uv sync --locked
uv run python --version
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`uv sync --locked` 创建 `backend/.venv` 并安装锁定的运行及开发依赖；无需手动激活虚拟环境。已有可用 Python 3.12 时可跳过 `uv python install 3.12`。安装依赖或下载 Python 需要访问对应下载源。当前 hello 服务无需数据库、凭证或后端 `.env` 配置。

服务监听 `http://127.0.0.1:8000`；8000 被占用时先检查占用者，或使用其他空闲端口并同步前端 `VITE_API_BASE_URL`。启动后保持此终端运行，按 Ctrl+C 停止。在另一个终端验证：

```bash
curl -i http://127.0.0.1:8000/test/hello
```

预期为 HTTP 200、`Content-Type: application/json` 和 `{"message":"hello world"}`。`curl` 成功只验证接口；浏览器联调还需符合下节 CORS 配置。

以下检查均在 backend/ 执行：

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv lock --check
```

测试默认把临时数据库放在 `backend/.pytest_cache/tmp/` 下，每次运行使用独立子目录，避免 Windows 全局 `Temp/pytest-of-<用户名>` 的权限问题及并行运行互相清理。该目录已被 Git 忽略，测试产物会保留在对应子目录中供排查。显式传入 `--basetemp` 或设置 `PYTEST_DEBUG_TEMPROOT` 时沿用调用方的配置。

测试覆盖 hello、CORS、健康检查，以及信息系统的迁移、持久化、批次回滚、幂等和查询。数据库连接成功测试使用内存 SQLite，信息持久化使用临时 SQLite 文件；连接失败测试模拟 SQLAlchemy 异常。PostgreSQL 离线迁移 SQL 有自动检查，真实 PostgreSQL 连接及并发仍需独立环境验证。专项步骤见[信息系统](app/services/content/README.md#迁移验证与回滚)。

## CORS 与浏览器联调

本地服务直接接受浏览器跨域请求，来源白名单在 `app/main.py`：

- `http://localhost` 和 `http://127.0.0.1` 的 5173、8765、8766 端口；
- Android / Capacitor 原生来源 `https://localhost`。

仅允许 GET 和 Accept 请求头，暴露 `X-Livelife-Backend-SHA` 响应头。该版本头由测试部署网关注入，本地 Uvicorn 不自动生成。Origin 的协议、主机和端口必须完全匹配；自定义前端端口或手机局域网网页需明确添加对应来源。`curl` 成功不等于浏览器 CORS 已通过。

前端地址配置和界面操作见[前端联调教程](../frontend/README.md#api-地址与联调)。公网预览通过同源网关访问 API，路由前缀、版本头和环境配对由[部署文档](../docs/deployment.md#api-地址与前端关联)维护。

## 数据库配置与健康检查

`DATABASE_URL` 是可选服务端环境变量，由 `app/core/config.py` 从进程环境读取；当前代码不自动加载后端 `.env` 文件。未设置或值为空时应用仍可启动，hello 和存活检查可用，就绪检查返回 HTTP 503。

需要测试已有本地 PostgreSQL 时，在启动服务的同一终端设置 SQLAlchemy URL：

```bash
export DATABASE_URL='postgresql+psycopg://<用户名>:<密码>@127.0.0.1:5432/<开发数据库名>'
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动前替换占位字段，并自行准备独立开发数据库；不要提交真实凭证。服务启动时创建 Engine 和 Session 工厂，实际连接由请求触发；进程退出时释放连接池。URL 或驱动配置错误可能阻止启动，连接失败时先核对地址、端口、数据库和账号权限。

在另一个终端检查：

```bash
curl -i http://127.0.0.1:8000/health/live
curl -i http://127.0.0.1:8000/health/ready
```

存活检查不访问数据库；就绪检查执行 `SELECT 1`，仅验证连接，不验证业务表或迁移状态。响应和失败行为见[健康检查契约](app/api/health/API.md#健康检查)。现有自动部署仍通过 hello 检查服务，部署启用状态见[部署入口](../docs/deployment.md#当前实施状态)。

已提供 `migrations/`、Alembic 环境和首个信息表迁移。设置开发数据库的 `DATABASE_URL` 后，在 backend 目录执行 `uv run alembic upgrade head` 和 `uv run alembic current`。应用不会自动创建表或执行迁移；信息系统使用前需要手动升级。迁移、使用和会删除信息数据的回退操作见[信息系统说明](app/services/content/README.md#迁移验证与回滚)。连接就绪检查仍只执行 `SELECT 1`，不验证迁移版本。

## 目录职责与请求处理

- `app/main.py`：创建应用、生命周期和 CORS；`app/api/router.py`：统一注册 hello 和健康检查 router。
- `app/api/`：按模块组织路由包，模块内的 `router.py` 处理 HTTP 路径、参数校验、依赖注入和响应映射，`API.md` 维护契约；`app/schemas/`：Pydantic 请求与响应模型。
- `app/core/`：配置；`app/db/`：Engine、Session 工厂、UTC 时间类型及请求依赖；`app/db/models/`：共享 ORM Base 与信息模型。
- `app/services/`：按业务域组织服务用例，`content/` 实现信息汇总和提供，`ingestion/` 定义信源适配协议；`app/repositories/sql/`：集中信息查询与原子写入。
- `alembic.ini`、`migrations/`：迁移配置、环境与版本脚本，导入完整模型 metadata。
- `tests/`：接口、CORS、健康检查、信息服务与迁移行为测试。

当前已实现的路由模块如下；`demo` 是代码模块名，对外路径仍为 `/test/hello`：

```text
app/api/
├── __init__.py
├── router.py             # 汇总注册各模块 router
├── demo/
│   ├── __init__.py
│   ├── router.py         # hello 连通性检查
│   └── API.md
└── health/
    ├── __init__.py
    ├── router.py         # 存活与数据库就绪检查
    └── API.md
```

需要数据库的路由通过 `app/db/dependencies.py` 的 `get_session` 获取 Session；未配置时返回 HTTP 503。依赖在请求结束时关闭 Session，不负责提交事务。后续业务用例显式接收 Session，并负责提交或回滚；repository 只执行数据操作，不提交事务。

### 服务职责

`content/` 和 `ingestion/` 已实现[信息系统内部契约](app/services/content/README.md)，其他包目前只有职责说明。跨模块产品规则以[架构说明](../docs/architecture.md#模块边界)和模块契约为准。

| 服务包 | 职责方向 |
| --- | --- |
| `accounts/` | 账户、登录凭据校验、会话生命周期和身份查询 |
| `preferences/` | 用户资料、兴趣标签、个性化设置及通知偏好 |
| `content/` | 已实现通用信息汇总、持久化和查询；分类及摘要后续接入 |
| `locations/` | 地点查询及附近活动检索 |
| `favorites/` | 活动收藏、取消收藏和列表查询 |
| `reactions/` | 表情表态、表情与分数映射及聚合结果 |
| `agent/` | 问题处理、基于资料的回答、来源引用和历史对话 |
| `ingestion/` | 已实现信源适配协议与批次导入入口；真实渠道、调度及自动提取后续接入 |
| `recommendations/` | 按偏好筛选内容及生成可解释候选 |
| `notifications/` | 提醒计划、设备关联、推送请求及送达记录 |

新增业务先按[契约协作流程](../docs/api.md#接口契约协作)确认接口，再创建 `app/api/<模块>/` 路由包及同目录的 `API.md`，按需要添加 schema、服务用例、repository 与模型。现有空业务路由文件尚未注册，不提供对应 API。各模块契约从公共入口链接，组织方法见[接口指南](../docs/api.md#模块契约怎么组织)。采集与推荐的独立 worker 在实际任务需要时创建，可复用服务与数据访问层，不在请求内执行长时间采集。
