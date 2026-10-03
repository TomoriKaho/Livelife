# GitHub 协作流程与操作教程

## 各对象的职责

| 对象 | 回答的问题 | 本项目使用方式 |
|---|---|---|
| Issue | 做什么，怎样完成 | 需求、缺陷、调研、文档和设施任务 |
| 子 Issue | 大任务怎样拆分 | 分别分配和验收前端、后端等任务 |
| PR | 代码或文档改动能否合并 | 改动评审与自动检查 |
| Project | 当前谁在做什么 | 团队长期工作台与多个视图 |
| Milestone | 阶段承诺交付什么 | MVP 等阶段范围和截止日期 |
| Release | 实际交付哪个版本 | Tag、发布说明、安装包和部署材料 |
| Actions | 哪些步骤可以自动执行 | 检查、构建、预览和部署 |

父子 Issue 表示拆分，依赖表示先后顺序。Issue 与 PR 可一对多或多对一。Project 可汇总多个仓库；Milestone 属于仓库，一个 Issue/PR 同时只能归入一个 Milestone。Release 基于 Git Tag，不直接从 Milestone 自动生成。合并 PR、完成 Milestone、发布 Release、部署正式服是不同事件。

## MVP 示例：从目标到任务

在仓库 Issues 页面找到 Milestones，创建“实现 MVP 版本”，填写目标日期和验收范围：订阅可保存与修改、地图显示地点与活动、文档完整、测试服联调通过、可发布 v0.1.0。

任务编号为示例：

```text
实现 MVP 版本
├─ #10 实现兴趣订阅
│  ├─ #11 定义接口契约
│  ├─ #12 实现后端接口
│  ├─ #13 实现兴趣设置页面
│  └─ #14 联调与验收
├─ #20 实现地图功能
│  ├─ #21 地图方案与数据结构
│  ├─ #22 地点、活动查询接口
│  ├─ #23 地图页面和详情入口
│  └─ #24 联调与验收
├─ #30 使用与部署说明
├─ #40 初始化 uni-app（若选型确认）
├─ #41 初始化后端
├─ #42 配置自动检查
├─ #43 搭建测试服
├─ #44 注册域名、DNS 和 HTTPS
└─ #45 MVP 整体验收
```

实际交付任务明确设置 Milestone，不假设子任务自动继承。父任务用于概览，关闭数量不等于工作量；父子项一起统计可能造成重复观感。

## 创建与填写 Issue

点击 Issues → New issue，选择仓库表单。当前提供普通任务、大功能和 Bug 模板；合并到默认分支后可在网页使用。

普通任务填写背景、范围、验收条件、依赖和参考资料。标题描述结果，如“实现订阅查询与更新接口”。右侧设置负责人、Labels、Milestone 和 Project。每项任务有一名主负责人，多人可参与。

验收条件应可验证，例如：未登录被拒绝、只能操作自己的订阅、保存后查询一致、接口文档更新。不要只写“开发完成”。小步骤用勾选清单，不必每个函数单建 Issue。

大功能写整体目标、边界和整体验收；Bug 写复现步骤、预期、实际、设备及版本、截图或日志；调研写需回答的问题和预期结论；域名等非代码工作写可检查结果，可以没有 PR。

### 创建子 Issue

1. 打开父 Issue，正文下方点击 Create sub-issue。
2. 输入标题、正文，设置负责人等字段，点击 Create。
3. 连续创建可选择 Create more sub-issues。

若要先使用统一表单，先通过 New issue 建立任务，再打开父 Issue，点击 Create sub-issue 旁的菜单 → Add existing issue，搜索编号或标题关联。至少 Triage 权限才能添加子任务。子 Issue 有独立状态和编号；父任务完成前验证整体功能，而不是仅查看子项是否关闭。

### 依赖与阻塞

使用可用的依赖关系功能，或在正文明确写“依赖 #11”。任务阻塞时评论说明原因、所需行动和关联任务；父子关系不能代替依赖。任务范围变化同步正文，避免完成标准只存在群聊中。

## Project 设置教程

创建一个团队 Project，添加相关 Issue。进入表格视图，最右侧添加字段，New field → Single select，创建 Priority，选项 P0、P1、P2。若已存在 Priority，直接使用。

| 优先级 | 定义 | 示例 |
|---|---|---|
| P0 | 立即处理，阻塞团队或交付 | 主分支不能构建、测试服不可用 |
| P1 | 本阶段优先完成 | 订阅 API、地图基础展示 |
| P2 | 可后做或延期 | 非必要动画和优化 |

这是团队约定，Priority 属于 Project，不是 Issue 全局字段。表单中的文字不会自动映射为它；本项目不重复使用优先级标签。父子优先级分别判断，优先级不取代依赖顺序。

状态采用 Backlog → Ready → In Progress → In Review → Done。Ready 表示依赖和范围明确；In Review 包含评审或待验收；Done 表示满足验收。Issue 的 Open/Closed 与 Project 状态不同，需约定同步。

### 避免看板混乱

给父 Issue 设置 `epic` 标签（维护者先创建该标签），保存以下视图：

1. 当前阶段：筛选当前 Milestone，排除 epic，按 Status 分组。
2. 功能概览：只显示 epic，查看整体进度。
3. 我的任务：按 Assignees 筛选当前成员。
4. 全部任务：表格展示所有阶段，便于整理。

在视图顶部设置过滤条件，使用 UI 选择字段和值，再保存视图。父子任务均可加入 Project，但不同时堆在日常看板。看板主要追踪 Issue，不把关联 PR 重复当作另一项需求。阶段结束后归档完成项；筛选仅改变视图，归档移出日常列表，均不删除 Issue。

Project 的 Workflows 中可配置自动加入任务、关闭后设 Done 等内置规则。PR 打开后更新关联 Issue 等复杂联动需 API/Actions 另行实现；父子关系也不自动把所有子任务加进 Project。

## 开发、提交和 PR 教程

先完成 [贡献指南](../CONTRIBUTING.md) 的建分支步骤。开发后运行真实存在的检查，按 Issue 自测，准备截图或接口例子。检查差异后提交：

```bash
git status
git diff
git add docs/workflow.md
git commit -m "docs(workflow): 补充协作流程"
git push -u origin docs/workflow-guide
```

路径和分支为示例，按实际替换；优先明确选择文件，避免不加检查地提交整个工作区。commit 格式见 [工程规范](engineering.md#commit-规范)，不设置提交模板。

main 已变化时，可在功能分支执行 `git fetch origin`、`git merge origin/main`，处理冲突后重跑相关检查。团队尚未约定 rebase 时不要擅自重写共享分支历史。

在 GitHub 点击 Compare & pull request，或 Pull requests → New pull request；base 选 main，compare 选自己的分支。标题用 `feat(subscription): 实现兴趣订阅接口` 等格式。正文由模板预填，补充关联、改动、验证、截图及兼容性。未完成选 Draft；准备好后 Ready for review，并请求队友评审。

完整解决且已验收时写 `Closes #12`；部分实现或合并后还需验收时写 `Refs #12`（普通引用，不自动关闭）。关闭关键字在目标为默认分支时发挥关联/合并关闭作用。不要误用 Closes 关闭整体父任务。

评审者先看 Issue 验收标准和 PR 范围，再看实现、测试和兼容性。使用 Comment、Request changes 或 Approve；作者处理意见，必要时更新测试证据。至少另一名成员批准，必要检查通过，再 Squash merge。维护者在 Settings 的 Rules/Branches 中为 main 配置 PR 评审、必要检查和讨论解决要求；可用性依套餐与仓库而异。

## 阶段验收与发布

共享测试服验证所有功能、真机能力和文档。记录验收提交 SHA 与已知问题。完成开发 Milestone 后，可另建“发布 v0.1.0”Issue 追踪构建、正式部署和发布说明，失败不能视作发布完成。

1. 选定已验收提交，不能随手发布继续变化的 main 最新代码。
2. 创建 v0.1.0 Tag，固定这次提交。
3. 构建相应产物，在 Releases → Draft a new release 选择 Tag。
4. 填写新增功能、修复、兼容性、部署方法和已知问题，上传 APK 等附件。
5. 按 [部署流程](deployment.md) 验证正式运行后公开发布；发布前版本可保留草稿，测试版本可标为 pre-release。

Release 是交付页面，不仅是安装包。GitHub 自动提供 Tag 源码压缩包。Android 可附 APK；iOS 使用合法签名和 TestFlight/App Store 等渠道，上传 IPA 不等于所有人能安装；后端和网页仍需部署。GitHub Release 也不代表应用商店审核通过。

## 参考

- [Issue 与子 Issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues)
- [Issue/PR 模板](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates)
- [Project](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects)
- [单选字段](https://docs.github.com/en/issues/planning-and-tracking-with-projects/understanding-fields/about-single-select-fields)
- [关联 PR 与 Issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)
- [Milestone](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/about-milestones)
- [Release](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
