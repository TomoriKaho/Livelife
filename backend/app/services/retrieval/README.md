# 信息索引与混合检索

本模块为 Agent 提供公开信息的分块、Embedding 调用、版本化索引及重建入口。
[`agent/retrieval.py`](../agent/retrieval.py) 负责关键词与向量召回、去重和排序，
对外仍使用原有 [Agent 引用契约](../../api/agent/API.md)。模型、worker 与 API 是独立进程。

## 检索行为

默认 `RETRIEVAL_MODE=keyword`。关键词在完整信息表上计算加权匹配，再选最多 64 条候选，
不再先截取最近 500 条。中文仍采用双字片段，去除明确的提问/时间词，最多使用 64 个关键词；
标题、地点、正文、来源名称分别加权。无结构化条件时要求至少 35% 的查询片段有字面匹配，
避免仅凭一个通用词返回大量资料。这是可回归的词法门槛，不是语言理解能力。

`hybrid` 同时调用配置的模型，对有效索引执行 pgvector 余弦精确检索。
每个原记录先取最相似片段，再选最多 64 条向量候选；相似度低于配置门槛的不进入融合。
两路按 Reciprocal Rank Fusion（常数 60）合并，同一原记录返回一次，最多 8 条。
明确追问中的已有来源可优先，但必须重新读取原记录并满足本轮条件；历史回答不成为事实。
每条命中记录向生成模型提供文章开头片段与最相关片段（相同片段不重复），避免只命中文章中段时遗漏开头的主讲人、参与方式等事实；仍按原记录返回一条引用。原记录标题、来源、日期与地点也进入模型资料背景。该有限上下文不代表读完全文，跨多个远距离片段的复杂问题仍需单独验证。

两路共享确定性筛选：

- `现在/此刻/正在` 要求明确的开始、结束时刻覆盖请求时间；只有日期或未知结束时间的记录不能证明“正在”。
- `今天/今日/昨天/明天/明日` 按 `Asia/Shanghai` 计算半开时间窗；活动日期可支持全天查询，
  `今晚/晚上` 采用 18:00 至次日 00:00，要求明确时间。跨日活动按区间相交处理。
- 从现有地点目录解析明确建筑和教室。`101` 不匹配 `1101`，二教不匹配三教，
  多地点共用的“教学楼”别名不能单独确定建筑。无目录或未知显式教室时返回空结果，不能放宽成任意教室。
- 完整字母数字课程号（例如 `MATH101`）按边界匹配。尚未实现任意自然语言时间解析、
  未登记地点消歧、多地点比较或设备坐标附近检索；不能据语义相似度声称这些约束已满足。
- 硬条件来自本轮问题；历史对话仅补充检索词和来源 ID，不能把历史生成的时间/地点当作本轮条件。

未命中不证明没有活动。无答案问题可能返回话题相关资料，例如活动介绍不包含主讲人手机号，
下游模型仍必须依据原契约说明未知；检索得分不能替代证据核查。

## 配置

所有变量仅在后端/模型进程中设置，`.env` 加载规则见[后端入口](../../../README.md#使用已有数据库或部署入口)。
API 和索引 worker 必须使用相同的模型、版本、维度、分块及查询前缀配置。

| 变量 | 默认值与用途 |
| --- | --- |
| `RETRIEVAL_MODE` | `keyword`；设为 `hybrid` 启用向量召回 |
| `EMBEDDING_BASE_URL` | 空；兼容 `/embeddings` 的基础地址，例如 `http://127.0.0.1:19073/v1`，禁止在 URL 中放凭证 |
| `EMBEDDING_API_KEY` | 空；模型服务的独立 Bearer 密钥，不复用对话模型密钥 |
| `EMBEDDING_MODEL` | `Qwen/Qwen3-Embedding-0.6B` |
| `EMBEDDING_MODEL_REVISION` | 空；启用时固定实际权重 commit SHA，不能在同一版本名下静默替换权重 |
| `EMBEDDING_DIMENSIONS` | `1024`，限制 1–2000；必须与返回维度一致，BGE 对照用 `512` |
| `EMBEDDING_TIMEOUT_SECONDS` | `10`，连接和读取超时；模型故障不长时间阻塞检索 |
| `EMBEDDING_QUERY_PREFIX` | Qwen 的英文任务指令与 `Query:` 前缀；文档编码不加查询前缀 |
| `RETRIEVAL_MIN_SIMILARITY` | `0.55`，范围 0–1；这是初始门槛，需在独立标注数据上按模型校准 |
| `RETRIEVAL_CHUNK_CHARS` | `600`，范围 100–2000；优先在段落或句末分块 |
| `RETRIEVAL_OVERLAP_CHARS` | `80`，必须小于块长度；保留相邻上下文 |
| `EMBEDDING_DEVICE` | 仅随附模型服务使用，默认 `cpu`；其他设备需实际验证 |

分块保留原始字符偏移和正文，所有片段附带原记录 ID、标题、来源、发布时间、活动日期、地点和时间。
模型/版本/维度/分块/查询前缀共同生成 profile；不匹配的旧 profile 不参与向量检索。
地址、密钥和相似度门槛变更不改变向量内容。模型输出必须数量和索引完整、维度正确、非零且有限，
接收后归一化；拒绝 HTML、损坏 JSON、重复索引、NaN/Infinity 及过大的响应。

## 本机安装与启动

在 `backend/` 运行。先准备 PostgreSQL 并完成迁移；使用本地开发入口时由它负责迁移，
在另一个终端使用其打印的连接串。独立数据库则明确设置自己的 `DATABASE_URL`。
首次运行需能下载公开模型，模型缓存默认由 Hugging Face 管理，可用 `HF_HOME` 指定目录。

```bash
uv sync --locked --group local-db
uv run --locked --group local-db python -m app.dev --port 18000
```

在独立终端为模型准备独立环境，避免普通 API 的 `uv sync` 移除模型依赖：

```bash
UV_PROJECT_ENVIRONMENT=.venv-embedding uv sync --locked --group embedding-server
export EMBEDDING_MODEL='Qwen/Qwen3-Embedding-0.6B'
export EMBEDDING_MODEL_REVISION='97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3'
export EMBEDDING_DIMENSIONS=1024
export OMP_NUM_THREADS=4
UV_PROJECT_ENVIRONMENT=.venv-embedding uv run --locked --group embedding-server \
  uvicorn app.embedding_server:app --host 127.0.0.1 --port 19073
```

PowerShell 使用 `$env:变量名='值'` 设置环境变量，命令写在同一行。
随附服务只加载固定 revision，禁用远程仓库代码，串行处理编码请求；忙时返回 429，
调用方走降级/重试。单请求最多 16 个输入、每个最多 8000 字符；模型序列长度上限取
1024 与模型自身上限的较小值，因此过长文本可能按模型 tokenizer 截断，分块应保持较小并实测。
不要为同一模型开启多个 Uvicorn worker，避免重复加载权重。默认仅监听 loopback；
跨主机服务须另配置访问控制、TLS、密钥和资源限额。

API/索引终端使用相同模型设置，另配置：

```bash
export EMBEDDING_BASE_URL='http://127.0.0.1:19073/v1'
export RETRIEVAL_MODE=hybrid
# DATABASE_URL 使用已核对的开发数据库连接串。
uv run --locked python -m app.services.content.catalog
uv run --locked python -m app.retrieval sync
uv run --locked python -m app.retrieval status
uv run --locked python -m app.retrieval watch
```

`catalog` 按现有[地点目录规则](../content/README.md)导入地点并补齐已有信息的关联。
API 进程需重启以读取自己的配置；worker 不会替 API 设置变量。模型 `/health` 成功只表示模型已加载，
不代表信息索引已构建或实际检索质量合格。普通 API 环境和自动部署不安装 `embedding-server` 组。

## 迁移、同步、重建与回退

迁移 `0009_hybrid_retrieval` 新增 `information_retrieval_state`、`information_retrieval_chunks`
及信息变更触发器，PostgreSQL 同时执行 `CREATE EXTENSION IF NOT EXISTS vector`。
**即使检索模式为 keyword，该迁移也要求数据库已安装可用的 pgvector 扩展文件，迁移角色有启用权限。**
本机 macOS ARM64 的 `pgembed==0.2.0` 包已检查到扩展文件并完成真实迁移；
其他平台、课程机及现有分支数据库必须逐环境检查，不能据此推断均已可用。

```sql
SELECT name, default_version, installed_version
FROM pg_available_extensions WHERE name = 'vector';
```

先核对目标数据库，备份后按既有部署流程运行 `alembic upgrade head` 和 `alembic current`。
`0011_merge_processing_retrieval` 将检索与信息处理的两条迁移链合为单一 head，
本身不修改数据或已有迁移；已升级至 `0009_hybrid_retrieval` 或 `0010_processing_diagnostics`
的数据库均继续执行 `upgrade head`，补齐另一条链后合流，无需重建数据库。
扩展不可用/权限不足时迁移失败，应安装匹配 PostgreSQL 版本的扩展或安排管理员启用，
不得跳过迁移后伪报就绪。现有 API 不能只更新源码而不迁移。

数据库触发器在同一信息事务中维护单调版本和待处理状态，迁移自动为已有信息建立待处理行。
直接 SQL 和正常采集写入都能触发；入库回滚时索引状态也回滚。重复的相同/旧采集快照仍受原有
`fetched_at` 幂等规则约束，不重新增加版本。删除信息时同步删除片段和任务，不保留幽灵来源。

worker 先读快照，释放事务，再生成向量。提交前按“原记录 → 状态”顺序加锁并核对版本；
中途更新、删除或重建导致的迟到结果丢弃。同一版本重复处理不重复写片段，多个 worker 的重复计算
可能发生但不会产生重复索引。首版建议只运行一个 worker，以减少重复计算与模型 429。
每条记录的片段整体替换并提交，失败只保存稳定错误码、尝试次数和重试时间，指数退避上限 300 秒。

`sync` 处理当前到期任务，遇到失败退出非零；`watch` 持续处理，空闲等待 5 秒。
`status` 显示总记录、待处理、失败和片段数。新信息在完成编码前可通过关键词查到；更新后旧版本
立即失效，不能继续用旧向量作为证据。服务故障、未配置、超时或向量 SQL 失败时，API 记录
`retrieval_degraded mode=keyword reason=...` 并使用关键词；查询 savepoint 失败不会破坏对话事务。
API 的查询向量在账户/IP 锁之外生成；历史在两次读取间变化时改用新关键词，不拿旧向量匹配新问题。

`status` 的 `records` 从原始信息表计数，并单独报告 `states`、`missing_states` 和 `missing_chunks`，
避免状态表缺失时误报已全量索引。`reconcile` 幂等补回缺失状态；`sync` 和 `watch` 启动时也会补回，
适用于只复制公开资料且已有迁移版本的分支数据库。它不重新生成向量或重置已有版本。
`check` 要求 hybrid 模式，真实调用模型并执行 pgvector 查询，存在缺失状态、待处理、失败或
有效版本缺失片段时退出非零。空库会明确报告零条资料。

```bash
uv run --locked python -m app.retrieval reconcile
uv run --locked python -m app.retrieval check
```

CI/CD 的模型安装、分支名单、配置注入、发布门禁及 worker 生命周期统一见
[RAG 部署](../../../../deploy/README.md#rag-模型与分支索引部署)。受信启动器使用可选的 Unix
`watch --lock-file <分支状态目录>/retrieval/worker.lock`，使同分支旧、新 API 共存时只有一个
活跃 worker；普通本机调用无需该参数。配置变更及组件启用不能仅靠推送业务源码完成。

修改模型/版本/分块参数时，先停止旧 profile 的 worker，再设置新配置，执行：

```bash
uv run --locked python -m app.retrieval rebuild
uv run --locked python -m app.retrieval sync
uv run --locked python -m app.retrieval status
```

`rebuild` 使全库索引版本失效，不删除原始信息；重建期间采用关键词兜底，未重新编码的旧片段不参与向量召回。
切回 `RETRIEVAL_MODE=keyword` 并重启 API 可停用模型调用。数据库回退至 `0008_merge_history_favorites`
会删除全部检索状态、片段及触发器；合流后的数据库还会删除信息处理任务、尝试及审核依据。
原信息表保留；先停 worker、备份两模块数据并切换兼容代码，不自动删除可能共享的 vector 扩展。
正式/共享数据库的安装、迁移和服务启停须按已授权目标执行；本任务没有自动修改共享部署。

## 验证与性能边界

```bash
uv run --locked pytest tests/test_hybrid_retrieval.py tests/test_agent.py tests/test_agent_history.py
uv run --locked --group local-db pytest tests/test_hybrid_retrieval.py --local-postgres
```

SQLite 只验证事务状态和词法筛选，向量查询必须用真实 PostgreSQL；可控向量替身不用于证明模型质量。
固定中文查询、Qwen/BGE 对照、资源采样及逐查询诊断见[评测入口](../../../evaluation/README.md)。

首版关键词加权和向量精确检索都会扫描相关信息/片段，按原记录去重后取 top-k；没有 HNSW，
没有“最近 500 条”的召回窗口，但吞吐随语料增长下降。状态重试与片段 profile/原记录关联已建 B-tree 索引。
加入近似索引前必须在目标数据量下测量，并验证带地点/时间过滤的召回；不能只追求低延迟而接受漏检。
目标服务器的 CPU/GPU、并发、索引构建耗时和资源占用，以及真实校园语料效果，需另行实测记录在 PR。
