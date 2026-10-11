# 后端 Agent 要求

遵循根目录 AGENTS.md，并阅读 docs/architecture.md、docs/engineering.md、docs/testing.md；部署时阅读 docs/deployment.md。

- 已确定 Python + FastAPI + Pydantic，初始化任务固定运行时、依赖及检查工具。采用模块化单体；当前真实业务接口仍未实现，仅提供健康检查。
- 后续持久化采用 PostgreSQL + SQLAlchemy + Alembic；db/ 管连接和 Session，db/models/ 管 ORM Base 与模型，repositories/sql/ 集中执行 SQL 查询与写入，services/ 下已有按业务域划分的职责占位包。互动采用 reactions 表情表态，后端维护表情与分数映射；repository 接收显式 Session，不负责事务；业务用例负责提交/回滚。占位包不代表业务契约或实现已确定。采集与推荐使用独立 Python worker，Redis + Celery 和 pgvector 待专项确认；其他目录按需创建。
- 校验身份、资源权限和输入，不依赖客户端进行权限控制。
- 使用接口契约和统一错误结构；不兼容变更需说明迁移和客户端影响。没有确定契约时不创建空业务路由或 501 占位接口。
- 数据库结构变更使用可追踪迁移，说明测试、部署和回滚限制。
- 采集和推荐任务设计幂等、重试及日志；不在请求中直接执行长时间采集。
- 信息保留来源链接、时间和处理依据，Agent 回答不伪造来源。
- 测试使用独立数据和凭证，日志不输出令牌、邮箱内容或其他秘密。
