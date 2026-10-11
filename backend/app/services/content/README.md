# 通用信息系统

为活动列表、日历、地图、推荐和 Agent 等后端模块提供共同的信息来源。当前包含可接入的采集接口、SQL 持久化与统一查询服务，使用 Python 内部调用；没有新增 HTTP 路由，也没有替换前端样例数据。对应需求为 [#60](https://github.com/TomoriKaho/Livelife/issues/60)，真实公众号渠道在 [#63](https://github.com/TomoriKaho/Livelife/issues/63) 接入，附近筛选由 [#61](https://github.com/TomoriKaho/Livelife/issues/61) 消费本模块数据。

## 三部分职责

```text
渠道适配器 InformationSource.fetch()
    → InformationInput
    → collect_information() 校验渠道归属
    → InformationAggregator.ingest() 校验、规范化、幂等保存
    → information_items
    → InformationProvider.get() / list()
    → Information → 各业务模块自己的服务 / API
```

- 获取：[`InformationSource`](../ingestion/source.py) 定义适配协议。公众号、树洞、知乎、小红书等适配器实现 `platform` 和 `fetch()`，产生统一输入；平台标识是可扩展字符串，不限于上述渠道。本次没有提供这些平台的客户端、账号接入或爬虫。
- 汇总：[`InformationAggregator`](aggregation.py) 保存记录并保留来源、原始正文和渠道原始字段；当前处理仅包括字段校验、UTC 时间规范化和正文首尾空白清理。不自动从文章推断活动时间、地点，不调用模型。
- 提供：[`InformationProvider`](provider.py) 返回独立于 ORM Session 的只读 Pydantic 对象，供其他后端服务组合使用。调用方按自己的业务要求组织列表、日历和地图接口。

数据库操作在 [`InformationRepository`](../../repositories/sql/information.py)，表结构在 [`InformationRecord`](../../db/models/information.py)。汇总服务负责事务；repository 不提交或回滚事务，查询服务不写入数据。

## 统一格式与缺失值

字段类型、约束及 JSON Schema 的主要来源是 [`schemas/information.py`](../../schemas/information.py)。`InformationInput.model_json_schema()` 和 `Information.model_json_schema()` 可用于内部契约检查；这些模型不注册到 FastAPI OpenAPI。

| 字段 | 输入规则与含义 |
| --- | --- |
| `platform` | 必填，小写字母开头，由小写字母、数字及下划线组成，最多 64 字符；例如 `wechat`、`pku_hole`、`zhihu`、`xiaohongshu` |
| `source_id` | 必填，平台内稳定且唯一，最多 255 字符；同一平台有多个账号时，适配器需包含账号命名空间，例如 `account-a:article-123` |
| `source_url` | 可选 HTTP/HTTPS 原文地址；无公开链接时保留 `None`，来源仍由平台和来源 ID 标识，不编造链接 |
| `title` | 可选标题，去除首尾空白后长度 1–500 |
| `content` | 必填且不能只有空白；输入正文原样另存 `raw_content`，统一输出去除首尾空白 |
| `fetched_at` | 必填，本次实际获取时间，不得用文章发布时间或入库时间代替 |
| `published_at` | 可选，来源平台提供的发布时间 |
| `activity_location` | 可选，最多 500 字符，已知的活动地点原文，例如“理科教学楼 101”；不是地图坐标或实时定位 |
| `activity_start_at` / `activity_end_at` | 可选，活动开始/结束时间；同时存在时结束必须晚于开始 |
| `registration_deadline_at` | 可选，报名截止时间 |
| `raw_payload` | 输入专用，可选 JSON 对象，保存适配器需要追溯的原始字段，默认为 `{}`；提供服务不返回它 |

所有时间必须带时区，例如 `2026-10-11T12:00:00+08:00`；保存和输出统一为 UTC，同一时刻序列化为 `2026-10-11T04:00:00Z`。不接受无时区时间。活动字段均可缺失，普通文章也可入库；未知值保持 `None`，不要填当前时间、默认地点或从示意地图推断。可选文本未知时传 `None`，不传空字符串。

输出 `Information` 在公共字段之外增加：

- `id`：系统 UUID，供消费模块引用，后续更新保持不变。
- `first_fetched_at`：首次成功入库那份快照的获取时间，后续更新保持不变；不是历史最早发布时间。
- `processed_at`：当前保存快照的处理时间，重放被忽略时不改变。

当前一条记录表示一个平台来源信息，附带最多一组已知活动时间和地点。多活动文章的拆分、跨平台同一活动的合并、坐标解析、分类、摘要、全文检索和访问控制需要后续明确契约；当前不自动执行。正文作为不可信内容传递，消费方显示 HTML 时须按自身渲染规则处理。

## 幂等、更新与失败

`(platform, source_id)` 有数据库唯一约束，使用数据库 `ON CONFLICT` 原子写入：

- 第一次获取创建记录；只有 `fetched_at` 更晚的输入才替换当前快照，更新时保留 UUID 和首次获取时间。
- 相同获取时间的重放、同时间不同内容和晚到的旧快照都被忽略。同时间冲突采用先成功保存的版本；适配器应稳定复用重试记录的获取时间。
- 新快照完整替换可变字段，缺失的活动字段会恢复为 `None`，不把旧活动信息错误地带到新版文章。
- 不同平台即使来源 ID 或正文相同也分别保存，不按正文相似度合并。
- 当前只保留最新原始正文与 `raw_payload`，不提供历史版本库。

`ingest(records)` 每批最多 1000 条，先完整遍历并校验，再在一个事务中保存。输入无效、采集迭代中失败、超过批量上限时不写入；SQL 写入或输出转换失败时整批回滚。空批返回 `()`。同一来源在一批出现多次时，返回一次最终快照，结果按来源首次出现的顺序排列。

每次汇总使用新的、尚未开启事务的 Session，由汇总服务提交或回滚；不要在已有读写事务的 Session 中调用 `ingest()`。调用方负责关闭 Session，不要混入其他模块的待提交修改。提供服务可在调用方的读取 Session 中使用，返回对象可在 Session 关闭后继续读取。

采集器负责网络访问、超时、重试、平台游标和权限；`collect_information()` 本身不联网、不调度、不吞掉异常，也不自动重试。渠道结果的 `platform` 必须与适配器一致。一次 `fetch()` 最多产生 1000 条，更多数据由适配器分页分批提交；只有保存成功后才推进对应游标。当前没有独立 worker、队列或游标持久化。

## 查询语义

`get(UUID)` 返回 `Information | None`。`list(InformationQuery(...))` 返回元组，默认 50 条，最大 100 条，`offset` 默认为 0。按 `fetched_at` 降序、UUID 降序排列；同一数据集合翻页顺序稳定，采集更新期间 offset 分页可能移动，当前不提供快照游标。

| 查询参数 | 规则 |
| --- | --- |
| `platform` | 精确匹配一个平台 |
| `fetched_after` / `fetched_before` | 获取时间范围 `[after, before)`，可只设一端 |
| `activity_after` / `activity_before` | 查询与该时间窗口相交的活动，窗口为 `[after, before)`，可只设一端 |
| `activity_location` | 地点文本包含匹配，`%`、`_` 等按普通字符匹配；不执行距离计算或坐标转换 |
| `limit` / `offset` | 数量及偏移，非负偏移，数量 1–100 |

活动有开始和结束时按区间相交查询，因此跨午夜活动也能被日历查到。只有开始时间时作为一个时间点匹配，不假设活动仍在持续。只有结束时间或完全未知时间的记录仍保留在通用列表中，但不进入活动时间查询。北京时间某一天应以 `+08:00` 的当天零点和次日零点传入，不用 UTC 零点代替本地日期边界。

## 本地准备与调用

后端运行时与依赖安装见 [backend README](../../../README.md)。本地开发推荐在 backend 目录运行 `uv run --locked --group local-db python -m app.dev --port 18000 --reload`，它会自动安装并启动 PostgreSQL、创建数据库和执行迁移。保持该终端运行，将控制台打印的 `DATABASE_URL` 设置到运行采集脚本或 worker 的另一个终端即可使用。数据保存在 `backend/.local/postgres/`，停止再启动仍会保留；安装平台、路径与排错见[本地数据库自动准备](../../../README.md#本地数据库自动准备)。

使用自己安装的 PostgreSQL 时，先准备独立开发数据库，再设置连接串并手动执行迁移；下列 PowerShell 示例中的凭证自行替换：

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://<用户名>:<密码>@127.0.0.1:5432/<开发数据库>'
uv run alembic upgrade head
uv run alembic current
```

迁移读取进程变量，不自动读取后端 `.env`。标准 `app.main:app` 入口不自动迁移；自动迁移仅发生在开发入口管理的本地数据库。没有数据库时 hello 和存活检查仍可用，信息持久化需要连接数据库及创建表。现有数据库连接探针只验证 `SELECT 1`，不能代替检查迁移版本。

在 backend 目录的 Python 进程中，下面例子使用人工样例演示写入与查询；无需启动 Uvicorn：

```python
from datetime import datetime

from app.db.session import Database
from app.schemas.information import InformationInput, InformationQuery
from app.services.content import InformationAggregator, InformationProvider

database = Database.from_environment()
if database.session_factory is None:
    raise RuntimeError("请先设置 DATABASE_URL 并执行迁移")

try:
    record = InformationInput(
        platform="manual",
        source_id="example:lecture-1",
        source_url="https://example.com/lecture-1",
        title="人工样例讲座",
        content="这是一条用于本地开发的信息样例。",
        fetched_at=datetime.now().astimezone(),
        activity_location="理科教学楼 101",
        activity_start_at="2026-10-12T19:00:00+08:00",
        activity_end_at="2026-10-12T21:00:00+08:00",
    )
    with database.session_factory() as session:
        saved = InformationAggregator(session).ingest([record])
    with database.session_factory() as session:
        provider = InformationProvider(session)
        detail = provider.get(saved[0].id)
        day = provider.list(
            InformationQuery(
                activity_after="2026-10-12T00:00:00+08:00",
                activity_before="2026-10-13T00:00:00+08:00",
            )
        )
    print(detail.model_dump(mode="json"))
    print([entry.model_dump(mode="json") for entry in day])
finally:
    database.close()
```

未来渠道接入实现这个协议，再交给汇总服务。示例仍是人工数据，不代表真实公众号可用：

```python
from app.services.ingestion import collect_information


class ExampleSource:
    platform = "manual"

    def fetch(self):
        # 真实适配器在这里访问已授权渠道，并转换为 InformationInput。
        return [record]


with database.session_factory() as session:
    saved = collect_information(ExampleSource(), InformationAggregator(session))
```

上面的适配器片段放在前一个示例的 `try` 内、`database.close()` 之前执行。内部服务只接收可信后端调用，不承担业务账号鉴权；当前应仅导入允许分发的公开或模拟内容，原始字段不得包含平台令牌、Cookie、账号密码或未经授权的私有数据。后续渠道接入须自行限定可采集、可分发范围。

## 迁移、验证与回滚

首个迁移 `0001_information` 创建信息表、来源唯一约束、活动区间约束及查询索引。升级不会修改已有 hello API，不会自动启动采集。部署前核对目标数据库和备份，按实际环境手动迁移；当前测试环境没有在本任务中配置数据库或运行远程迁移。

仅在可丢弃的开发数据库中，`uv run alembic downgrade base` 可回退首个迁移，**会删除信息表和全部信息数据**；需要保留数据时先导出并验证备份。再次 `upgrade head` 只重建表，不恢复已删除的数据。

在 backend 目录执行：

```bash
uv run pytest tests/test_information.py tests/test_migrations.py
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv lock --check
```

自动测试使用临时 SQLite 文件验证实际迁移、跨 Session 持久化、来源更新与幂等、失败回滚、查询过滤、时间窗口和分页；另生成 PostgreSQL 离线迁移 SQL。这些检查不等于真实 PostgreSQL 连接、并发写入或真实渠道采集已通过。PostgreSQL 验证时先在独立开发库执行迁移，再按上例写入、读取和重复导入，确认 UUID 稳定以及 `/health/ready` 可连接；正式环境操作遵循[部署入口](../../../../docs/deployment.md)。

`uv run --locked --group local-db pytest --local-postgres` 另在测试临时目录启动真实 PostgreSQL，验证自动建库、迁移、信息写入、重启后读取及停止进程；不会接触默认开发数据目录或 `DATABASE_URL` 指定的外部数据库。默认 `uv run pytest` 跳过这项集成测试，不下载数据库程序。该项不覆盖多进程并发或真实平台采集。
