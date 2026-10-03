# 团队贡献指南

## 首次参与

1. 阅读 [README](README.md)，确认产品目标和当前实现状态。
2. 阅读 [工程规范](docs/engineering.md) 与 [协作流程](docs/workflow.md)。
3. 在团队 GitHub Project 中查看当前 Milestone，确认自己的任务及依赖。
4. 如果你是Agent，另需读取 [AGENTS.md](AGENTS.md)。不同工具的自动发现机制不同，必要时在提示中明确要求读取。

## 从任务到交付

### 领取任务

打开已有 Issue，确认目标、范围、验收条件和依赖。每项任务明确一名主负责人（Assignee）。范围不清楚时先在 Issue 中讨论，避免产生冲突。

### 建立分支

确认工作区没有未处理的改动，再执行：

```bash
git status
git switch main
git pull --ff-only
git switch -c feat/12-subscription-api
```

分支名为示例，编号换成真实 Issue。使用 `feat/`、`fix/`、`docs/` 等清晰名称；当前文档工作使用明确指定的 `doc` 分支。不要覆盖或丢弃别人的本地改动。

### 实施与自测

按 [架构约定](docs/architecture.md) 实现，按 [测试教程](docs/testing.md) 验证。涉及界面准备截图；接口准备调用示例；文档验证链接和命令说明。可先开 Draft PR 获取反馈，不将草稿当成已准备好验收。

本地全套部署不方便时，先推送分支，再按 [预览环境教程](docs/deployment.md#合并前的分支预览) 触发部署。推送不等于合并，不必先创建 PR。该能力需维护者先配置完成。

### 提交 PR

检查 `git diff` 和 `git status`，确认没有密钥、临时产物或无关修改。按 [commit 规范](docs/engineering.md#commit-规范) 提交，推送后在 GitHub 创建 PR，base 选 main，compare 选功能分支。填写自动出现的模板，关联 Issue，提供验证方法和结果，请至少一位队友评审。

### 评审与合并

作者处理意见，评审者检查范围、实现、验证和兼容性。需要的自动检查通过后再合并，建议使用 Squash merge，并检查最终提交标题。检查规则和保护分支须由维护者配置；未配置时仍遵守团队约定。

合并后观察测试服部署，完成必要联调。Issue 满足验收条件才关闭；父 Issue 在整体功能验收后关闭。不能把“PR 合并”直接等同于“功能已上线”。

## 非代码任务与规范修改

域名注册、选型调研等也使用 Issue，写明交付物和可检查结果；它们可以没有 PR。实际密码与密钥通过受控渠道提供，Issue 中仅写配置说明。

规范修改走 PR，在描述中说明改变的约定和影响，负责人评审后合并。会议和群聊形成的新决定及时写入正式文档。GitHub 网页模板需进入默认分支后才能正常供成员使用。
