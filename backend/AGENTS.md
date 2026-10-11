# 后端 Agent 要求

遵循根目录 AGENTS.md 和 CONTRIBUTING.md 的文档结构、拆分及分工约定，并阅读 docs/architecture.md、backend/README.md、docs/testing.md。接口任务同时阅读 docs/api.md 和对应模块契约；部署时从 docs/deployment.md 进入 deploy 的相关说明。

- 已确定 Python + FastAPI + Pydantic，采用模块化单体；当前能力、运行时和检查命令见 backend/README.md 及 API 契约，按已授权任务扩展模块。
- 后续持久化采用 PostgreSQL + SQLAlchemy + Alembic；采集与推荐使用独立 Python worker，Redis + Celery 和 pgvector 待专项确认。目标目录按需创建，不为未来模块生成空工程。
- 校验身份、资源权限和输入，不依赖客户端进行权限控制。
- 使用已确认的接口契约和错误结构；不兼容变更需说明迁移和客户端影响。
- 新接口先确认契约，再实现路由、模型与客户端 Mock；不自行引入未确认的认证、响应包裹或错误码。资源权限和错误状态须验证实际行为。
- 同一 PR 核对路由、Pydantic 模型、生成的 OpenAPI、示例、模块说明及测试；接口变化同步受影响调用方。
- 数据库结构变更使用可追踪迁移，说明测试、部署和回滚限制。
- 采集和推荐任务设计幂等、重试及日志；不在请求中直接执行长时间采集。
- 信息保留来源链接、时间和处理依据，Agent 回答不伪造来源。
- 测试使用独立数据和凭证，日志不输出令牌、邮箱内容或其他秘密。

- 文档随本模块改动更新对应 README 或专题说明。docs/api.md 维护共享规则与索引，实际模块需要独立契约时就近维护 API.md；接口少时保留入口中的章节，不预建空模块。部署字段在 deploy 对应文档维护，专项测试放模块附近，docs/testing.md 维护团队验收入口。只更新受影响内容与必要导航，不重复追加状态和验证记录。
