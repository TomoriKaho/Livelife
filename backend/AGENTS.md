# 后端 Agent 要求

遵循根目录 AGENTS.md，并阅读 docs/architecture.md、docs/engineering.md、docs/testing.md；部署时阅读 docs/deployment.md。

- 已确定 Python + FastAPI + Pydantic，初始化任务固定运行时、依赖及检查工具。采用模块化单体；首阶段仅实现 docs/architecture.md 约定的 GET /test/hello，不引入数据库或真实业务服务。
- 后续持久化采用 PostgreSQL + SQLAlchemy + Alembic；采集与推荐使用独立 Python worker，Redis + Celery 和 pgvector 待专项确认。目标目录按需创建，不为未来模块生成空工程。
- 校验身份、资源权限和输入，不依赖客户端进行权限控制。
- 使用接口契约和统一错误结构；不兼容变更需说明迁移和客户端影响。
- 数据库结构变更使用可追踪迁移，说明测试、部署和回滚限制。
- 采集和推荐任务设计幂等、重试及日志；不在请求中直接执行长时间采集。
- 信息保留来源链接、时间和处理依据，Agent 回答不伪造来源。
- 测试使用独立数据和凭证，日志不输出令牌、邮箱内容或其他秘密。
