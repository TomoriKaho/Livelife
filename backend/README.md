# 后端开发

后端使用 FastAPI 和 Pydantic，采用模块化单体。当前演示接口的契约见 [API 文档](../docs/api.md)，整体技术路线见[架构说明](../docs/architecture.md)。

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

测试覆盖 hello 响应、允许及拒绝的 CORS 来源、未知路径和不支持的方法。

## CORS 与浏览器联调

本地服务直接接受浏览器跨域请求，来源白名单在 `app/main.py`：

- `http://localhost` 和 `http://127.0.0.1` 的 5173、8765、8766 端口；
- Android / Capacitor 原生来源 `https://localhost`。

仅允许 GET 和 Accept 请求头，暴露 `X-Livelife-Backend-SHA` 响应头。该版本头由测试部署网关注入，本地 Uvicorn 不自动生成。Origin 的协议、主机和端口必须完全匹配；自定义前端端口或手机局域网网页需明确添加对应来源。`curl` 成功不等于浏览器 CORS 已通过。

前端地址配置和界面操作见[前端联调教程](../frontend/README.md#api-地址与联调)。公网预览通过同源网关访问 API，路由前缀、版本头和环境配对由[部署文档](../docs/deployment.md#api-地址与前端关联)维护。

## 目录职责

- `app/main.py`：FastAPI 入口及中间件配置。
- `app/api/`：路由；`app/schemas/`：Pydantic 请求和响应；`app/core/`：公共配置。
- `tests/`：接口及 CORS 行为测试。

业务持久化阶段再创建 services、db 和 migrations，采集与推荐通过独立 worker 运行。接口契约与客户端协作先在[共享 API 文档](../docs/api.md#接口契约协作)确定。
