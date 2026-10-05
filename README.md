# Livelife GitHub 协作操作指南

本分支用于通过 GitHub Pages 展示团队协作教程。`index.html` 已内嵌样式、脚本和 15 张真实 GitHub 页面截图，无需安装依赖或运行构建命令。

## 首次发布

1. 打开 https://github.com/TomoriKaho/Livelife/settings/pages 。
2. 在 **Build and deployment → Source** 选择 **Deploy from a branch**。
3. **Branch** 选择 `codex/github-pages`，目录选择 **/(root)**，点击 **Save**。
4. 等待部署完成，使用 Pages 设置页显示的访问链接。没有自定义域名时，通常为 https://tomorikaho.github.io/Livelife/ 。

## 更新教程

教程源文件位于文档工作分支的 `docs/github-guide.html`。修改并验证后，用它更新本分支的 `index.html`，提交并推送。Pages 启用后会随本分支更新重新部署。

本分支只保存发布页面；项目需求、Issue、Project、PR 和业务代码继续在原有位置维护。

本地查看可以直接用浏览器打开 `index.html`；所有截图均已内嵌。
