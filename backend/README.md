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
uv run --locked --group local-db python -m app.dev --port 8000 --reload
```

`uv sync --locked` 创建 `backend/.venv` 并安装锁定的运行及开发依赖；无需手动激活虚拟环境。已有可用 Python 3.12 时可跳过 `uv python install 3.12`。上面的开发启动命令还会安装 `local-db` 依赖组中的 PostgreSQL 程序，自动初始化数据库、启动数据库、执行 Alembic 升级，然后启动 API；无需 Docker、管理员权限或手填 `DATABASE_URL`。首次安装依赖、数据库程序或 Python 需要访问下载源。详情见[本地数据库自动准备](#本地数据库自动准备)。

服务监听 `http://127.0.0.1:8000`；8000 被占用或出现 Windows `WinError 10013` 时可将命令的 `--port 8000` 改为 `--port 18000`，并同步前端 `VITE_API_BASE_URL`。启动后保持此终端运行，按 Ctrl+C 停止 API 和本次使用的本地数据库进程，数据继续保留。在另一个终端验证：

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

测试覆盖 hello、CORS、健康检查、开发启动流程，以及信息系统的迁移、持久化、批次回滚、幂等和查询。默认测试使用 SQLite 和模拟异常，不启动 PostgreSQL；另检查 PostgreSQL 离线迁移 SQL。可用 `uv run --locked --group local-db pytest --local-postgres` 验证真实本地 PostgreSQL 的迁移、写入、重启保留与进程停止；真实并发和渠道接入另行验证。专项步骤见[信息系统](app/services/content/README.md#迁移验证与回滚)。

## CORS 与浏览器联调

本地服务直接接受浏览器跨域请求，来源白名单在 `app/main.py`：

- `http://localhost` 和 `http://127.0.0.1` 的 5173、8765、8766 端口；
- Android / Capacitor 原生来源 `https://localhost`。

仅允许 GET 和 Accept 请求头，暴露 `X-Livelife-Backend-SHA` 响应头。该版本头由测试部署网关注入，本地 Uvicorn 不自动生成。Origin 的协议、主机和端口必须完全匹配；自定义前端端口或手机局域网网页需明确添加对应来源。`curl` 成功不等于浏览器 CORS 已通过。

前端地址配置和界面操作见[前端联调教程](../frontend/README.md#api-地址与联调)。公网预览通过同源网关访问 API，路由前缀、版本头和环境配对由[部署文档](../docs/deployment.md#api-地址与前端关联)维护。

## 数据库配置与健康检查

### 本地数据库自动准备

在 backend 目录使用开发入口：

```powershell
# 若此前手动设置过连接串，先移除，以选择自动本地数据库。
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
uv run --locked --group local-db python -m app.dev --port 18000 --reload
```

`local-db` 依赖组固定 `pgembed==0.2.0`，由 uv 下载并校验锁文件中的平台安装包；包内带真正的 PostgreSQL 程序，不替换为 SQLite，也不安装 Windows 系统服务。普通 API 和部署依赖不包含该组。当前安装包覆盖 Python 3.12 的 Windows x64、Linux x64/ARM64 和 macOS 15+ ARM64；其他平台使用下节的独立 PostgreSQL。安装包来源与平台列表见 [pgembed](https://pypi.org/project/pgembed/0.2.0/)。

首次启动创建独立 PostgreSQL 集群及 `livelife` 数据库，自动执行 `alembic upgrade head`；之后复用已有数据并补齐新迁移。程序位于 `.venv` 的依赖包内，数据和数据库日志位于 `backend/.local/postgres/`，均已被 Git 忽略。迁移失败会中止 API 启动并清理数据库进程，不报告虚假的就绪状态。`--reload` 只重启 API 子进程，父进程保持数据库运行。

数据库由 pgembed 选择可用地址：Windows 仅监听 `127.0.0.1` 的空闲端口，Linux/macOS 使用本地 Unix socket。此开发库使用本机 trust 认证，仅用于自己的开发数据；不要用它承载正式或共享服务。控制台打印实际 `DATABASE_URL`，如需在另一个终端运行 worker 或检查迁移，复制该值到该终端的环境变量，并保持开发入口运行；不要照抄固定的 5432 端口。开发入口只为自身及子进程设置连接串，不修改系统环境变量或 `.env` 文件。

`--data-dir <目录>` 可指定其他本地数据目录；路径相对当前终端，默认路径始终相对 backend。停止后保留该目录即可保留数据，不要把数据放进 `.venv`。正常 Ctrl+C 或 API 启动失败会关闭数据库；多个开发入口共用同一数据目录时，由最后一个使用者退出时停止数据库。强制杀死父进程可能留下数据库进程，下次启动会复用；不要在数据库运行时直接删除数据目录。需要重置时先停止所有使用它的进程，再备份或重命名该目录。

### 使用已有数据库或部署入口

`DATABASE_URL` 是可选服务端环境变量，由 `app/core/config.py` 从进程环境读取；当前代码不自动加载后端 `.env` 文件。标准入口 `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000` 不安装、启动或迁移数据库；未设置连接串时 hello 和存活检查可用，就绪检查返回 HTTP 503。开发入口发现已有非空 `DATABASE_URL` 时拒绝自动准备，提示切换标准入口，避免迁移错误目标。

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

已提供 `migrations/`、Alembic 环境和首个信息表迁移。独立数据库需要设置 `DATABASE_URL` 后，在 backend 目录手动执行 `uv run alembic upgrade head` 和 `uv run alembic current`；开发入口只对自动管理的本地库执行升级。迁移、使用和会删除信息数据的回退操作见[信息系统说明](app/services/content/README.md#迁移验证与回滚)。连接就绪检查仍只执行 `SELECT 1`，不验证迁移版本。

## 目录职责与请求处理

- `app/main.py`：创建应用、生命周期和 CORS；`app/api/router.py`：统一注册 hello 和健康检查 router。
- `app/dev.py`、`app/db/local.py`：本地开发启动入口、专属 PostgreSQL 生命周期和自动迁移；部署仍使用 `app.main:app`。
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
