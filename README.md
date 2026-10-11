# Livelife

面向北京大学学生的信息汇总与个性化推送系统。通过多源采集、去重整合、兴趣筛选和 Agent 查询，帮助用户发现校园及领域信息，并提供原文来源。

## 产品目标

- 信息流：汇总校园公告、活动和领域内容。
- 兴趣订阅：按照兴趣组织信息，并支持提醒。
- 校园地图：展示地点及关联活动，进入详情和原文。
- Agent 查询：基于可检索的信息回答问题，提供依据和来源。

最终目标是 Android/iOS APP，网页用于开发和演示。课程阶段优先校园场景，长期支持开源自部署与云服务。技术路线和模块关系见[架构说明](docs/architecture.md)。

## 开始使用

首次参与先阅读[贡献指南](CONTRIBUTING.md)，再根据分工准备环境：

- [前端开发](frontend/README.md)：安装、网页启动、API 地址、构建和模块导航。
- [后端开发](backend/README.md)：安装、服务启动、CORS 和检查。
- [共享网页与 API](docs/deployment.md#合并前的分支预览)：获取分支预览及配对后端。
- [Android 测试包](frontend/android/README.md)：本地运行、下载安装；[真机验收](docs/testing.md#android-测试包操作)记录设备和结果。

## 目录结构

以下为当前主要目录；数据库、worker 和 iOS 工程在相应任务中创建。

```text
Livelife/
├── README.md
├── CONTRIBUTING.md
├── AGENTS.md
├── frontend/
│   ├── README.md
│   ├── AGENTS.md
│   ├── src/             # 页面、公共组件、API、平台适配与资源
│   ├── scripts/         # 资源处理、构建校验和 *.test.mjs 行为测试
│   └── android/         # Capacitor Android 工程
├── backend/
│   ├── README.md
│   ├── AGENTS.md
│   ├── app/             # FastAPI 入口、路由、响应模型及配置
│   └── tests/
├── docs/                # 架构、协作、API、部署和测试说明
├── deploy/              # 构建、部署及环境管理工具
└── .github/             # Issue / PR 模板与 Actions
```

## 开发与协作导航

| 文档 | 阅读目的 |
| --- | --- |
| [贡献指南](CONTRIBUTING.md) | 领取任务、分支、PR、工程规范、文档协作和 AI 使用 |
| [协作流程](docs/workflow.md) | 需求讨论、分工、Project、Milestone 和阶段交付 |
| [架构说明](docs/architecture.md) | 技术路线、模块职责和数据流 |
| [API 文档](docs/api.md) | 共享约定、模块契约入口和接口写法 |
| [部署说明](docs/deployment.md) | 测试环境、预览、配对和部署维护入口 |
| [测试说明](docs/testing.md) | 自测、PR 验证、真机验收和专项检查入口 |
| [Agent 要求](AGENTS.md) | AI 执行入口；前后端另有目录级要求 |

图文操作教程：[GitHub 协作操作指南](https://tomorikaho.github.io/Livelife/contributing/)。教程由 github-pages 分支维护，团队规则以仓库文档为准。
