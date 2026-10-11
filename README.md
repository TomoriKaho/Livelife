# Livelife GitHub 协作操作指南

本分支用于通过 GitHub Pages 展示团队协作教程。`contributing/index.html` 已内嵌样式、脚本和 15 张真实 GitHub 页面截图，无需安装依赖或运行构建命令。

## 首次发布

1. 打开 https://github.com/TomoriKaho/Livelife/settings/pages 。
2. 在 **Build and deployment → Source** 选择 **Deploy from a branch**。
3. **Branch** 选择 `github-pages`，目录选择 **/(root)**，点击 **Save**。
4. 等待部署完成，使用 Pages 设置页显示的访问链接。没有自定义域名时，通常为 https://tomorikaho.github.io/Livelife/contributing/ 。

## 更新教程

源文件为本分支的 `contributing/index.html`。从 github-pages 创建独立任务分支，直接修改源文件，通过 PR 评审后合入 github-pages。团队规则的主要来源是 main 上的 CONTRIBUTING.md 和 docs/workflow.md，页面提供图文操作入口，避免另维护一套规则。

仓库文档迁移与网页更新分别交付；先合并仓库文档，再合并引用新位置的网页变更，避免链接指向尚不存在的文件。Pages 随发布分支更新，推送、合并与发布按该次授权执行。

验证页面目录、文档链接、复制按钮、截图放大和窄屏显示。截图日期保留为原始日期，正文规则以最新仓库文档为准。

本分支只保存发布页面；项目需求、Issue、Project、PR 和业务代码继续在原有位置维护。

本地查看可以直接用浏览器打开 `contributing/index.html`；所有截图均已内嵌。

网站根目录的 `index.html` 是导航首页，协作教程放在 `contributing/`，后续其他静态页面可放在各自目录。
