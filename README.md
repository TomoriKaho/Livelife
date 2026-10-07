# Livelife

面向北京大学学生的信息汇总与个性化推送系统。通过多源采集、去重整合、兴趣筛选和 Agent 查询，帮助用户及时发现校园及领域相关信息，并提供原文来源。

## 产品目标

- 信息流：汇总校园公告、活动及领域内容。
- 兴趣订阅：按照用户兴趣组织信息，并支持提醒。
- 校园地图：展示地点及关联活动，进入详情和原文。
- Agent 查询：基于可检索的信息回答问题，提供依据和来源。
- 长期支持开源自部署和云服务；课程阶段优先完成校园场景。

## 技术路线与当前状态

[Issue #19](https://github.com/TomoriKaho/Livelife/issues/19) 的技术路线已确认：客户端采用 Vue 3 + TypeScript + Vite + Vue Router，地图采用 Canvas 2D + Three.js，APP 采用 Capacitor；后端采用 Python + FastAPI + Pydantic。后续持久化采用 PostgreSQL + SQLAlchemy + Alembic，采集与推荐使用独立 Python worker，课程机后端采用 Python 虚拟环境和 Supervisor 直接运行，公网 API 采用 Nginx + SSH 隧道。具体实施阶段与待专项选型事项见 [工程规范](docs/engineering.md#技术栈与实施阶段)。

最终交付目标是 Android/iOS APP，网页用于开发和演示；首阶段同时安排最小 Android 验证包，iOS 后续验证，小程序不纳入当前范围。

后端已实现本地 `GET /test/hello` 演示接口。后端 main/分支自动部署已接入，网页预览由 #27 扩展；课程机统一检查/构建与新的 Actions 调度已随 PR #37 合入 main，完整事件链路与网页启用状态以[部署说明](docs/deployment.md#当前实施状态)为准；数据库、登录和其他业务接口仍属后续工作。
frontend/ 已从 design 分支 `4d95af0` 迁入 Vue 客户端，包含引导、地图、详情、日历、兴趣、Agent 和个人页，以及依赖锁文件、环境变量样例、构建和行为测试。当前支持本地网页演示；development / preview 构建的“我的 → 帮助与反馈 → 接口连通性测试”可发起真实 hello 请求；production 构建剔除内部工具。模式与操作教程见[工程规范](docs/engineering.md#内部调试工具与构建模式)。backend/ 已提供 FastAPI hello 服务及测试；完整成员验收和 Android/iOS 工程尚未完成；本分支新增网页构建、运行时配置和预览控制，启用状态见部署说明。地图数据是本地 OSM 快照，活动、账户、定位与 Agent 内容为样例。OSM 界面署名由 [#31](https://github.com/TomoriKaho/Livelife/issues/31) 跟进。

首次参与请依次阅读下面的贡献指南、协作流程、工程规范。前后端安装、环境配置、启动及检查入口，以及客户端构建步骤统一放在 [工程规范](docs/engineering.md#目录与启动命令)。

## 首阶段 Demo 目标

以下为首阶段完整验收目标；客户端网页已实现，后端联调、另一名成员复现与 Android 验证仍待完成：

- 已将 design 页面迁入 frontend/，保留地图、活动详情、日历、兴趣、Agent、个人页及引导页的演示和基本跳转。
- 后端仅实现 `GET /test/hello`，设计响应为 HTTP 200、JSON `{"message":"hello world"}`；前端真实请求并显示结果，请求失败时明确提示。契约见 [架构说明](docs/architecture.md#首阶段接口契约)。
- 活动、兴趣、账户和 Agent 继续使用前端样例数据并标明演示性质；不接入数据库、真实登录、采集、推荐、模型或上传服务。
- 完成本地网页演示；使用同一前端生成最小 Android 验证包，验证地图、详情跳转、返回键、布局和接口请求。Android 使用手机可访问的开发后端地址，不使用电脑 localhost 作为手机入口。
- 提供安装、配置、启动与演示步骤，另一名成员按文档复现并记录提交版本、环境和结果。验收要求见 [测试说明](docs/testing.md#首阶段-demo-验收)。

演示动线：样例引导 → 校园地图与建筑活动 → 活动详情 → 日历列表 → Agent/个人页演示；通过“我的 → 帮助与反馈 → 接口连通性测试”展示 hello 联调；需要先配置并启动真实后端。样例定位、楼层、活动和账户不表示真实位置、教室占用或登录状态。iOS、真实定位、系统推送与商店发布留到后续阶段。

任务衔接：[#20](https://github.com/TomoriKaho/Livelife/issues/20) 与 [#23](https://github.com/TomoriKaho/Livelife/issues/23) 当前按网页演示验收；[#24](https://github.com/TomoriKaho/Livelife/issues/24) 实现 hello 接口，[#25](https://github.com/TomoriKaho/Livelife/issues/25) 完成网页联调及复现。新增 Android 验证目标需后续单独安排任务，不视为这些 Issue 已增加 APP 验收要求。自动部署继续由 [#18](https://github.com/TomoriKaho/Livelife/issues/18) 独立推进。本次不修改远程任务或状态。

## 目标目录结构

以下是完整目标结构。frontend/ 已包含网页实现，backend/ 已包含 hello 服务及测试；业务后端模块、原生工程、数据库与部署部分按后续任务创建；该树不代表所有目录均已存在。design 分支作为原型来源，不作为长期并行维护的第二套业务客户端。迁移规则见 [工程规范](docs/engineering.md#原型迁移与目录职责)。

```text
Livelife/
├── frontend/
│   ├── src/
│   │   ├── pages/          # 页面及页面专属子组件
│   │   ├── components/     # 公共组件
│   │   ├── router/         # 页面导航
│   │   ├── api/            # API 请求与错误处理
│   │   ├── types/          # 接口与业务类型
│   │   ├── data/           # 明确标注的演示数据
│   │   ├── assets/         # 地图、字体、图片及许可证
│   │   ├── plugins/        # 手绘等 Vue 插件
│   │   └── platform/       # Web/原生能力适配
│   ├── scripts/            # 地图处理与资源检查
│   ├── tests/
│   ├── android/            # Capacitor 原生工程
│   └── ios/                # 后续创建
├── backend/
│   ├── app/
│   │   ├── main.py         # 服务入口
│   │   ├── api/            # 路由
│   │   ├── schemas/        # Pydantic 请求和响应
│   │   ├── core/           # 配置及公共基础设施
│   │   ├── services/       # 后续业务逻辑
│   │   ├── db/             # 后续连接及数据库模型
│   │   └── workers/        # 后续独立任务入口
│   ├── migrations/         # 后续 Alembic 迁移
│   └── tests/
├── docs/
├── deploy/                 # 前后端预览管理与服务器部署工具
└── .github/
```

根目录继续保留 README、CONTRIBUTING 和 AGENTS 指引；前后端分别维护依赖、锁文件、环境配置样例及忽略规则。数据库、worker、iOS 和部署目录仅在对应阶段需要时创建，首阶段无需占位工程。

## 开发与协作导航

| 文档                                      | 阅读目的                                         |
| ----------------------------------------- | ------------------------------------------------ |
| [贡献指南](CONTRIBUTING.md)（必读）        | 新成员从领取任务到交付的完整步骤                 |
| [协作流程](docs/workflow.md)（必读）       | 整体协作流程                                     |
| [AI 辅助开发指南](docs/ai-development.md)（待完善） | AI 使用教程、人机分工、评审与执行边界             |
| [测试说明](docs/testing.md)（待完善）      | 本地自测、合并前预览、测试服联调、验收和缺陷报告 |
| [部署说明](docs/deployment.md)   | 分支与环境映射、Actions 配置教程、实际验证与发布回滚     |
| [工程规范](docs/engineering.md)（待完善）  | 技术选型状态、目录、编码和提交规范               |
| [架构说明](docs/architecture.md)（待完善） | 模块边界、数据流和接口协作                       |
| [Agent 要求](AGENTS.md)（待完善）          | AI 工作入口；前后端另有目录级要求                |

图文操作教程：[GitHub 协作操作指南](https://tomorikaho.github.io/Livelife/contributing/)，由 github-pages 分支发布和维护。

## 交付路径

功能分支开发 → 推送分支 → 自测或按需预览 → PR 检查与评审 → 合并 main → 部署共享测试服 → 整体验收 → 固定版本 Tag → Release 与正式部署。
