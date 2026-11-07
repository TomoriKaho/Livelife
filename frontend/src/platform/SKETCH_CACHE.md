# 导航手绘 PNG 缓存

公共卡片、按钮、标签与日历标记已迁移为[静态资源](../assets/sketch/README.md)，不进入这个数据库。当前缓存只服务[手绘模块](../plugins/README.md)保留的底部导航动态合成，不再保存或恢复整套页面准备记录。

## 存储与兼容

[sketch-cache.ts](sketch-cache.ts) 使用 IndexedDB `livelife-sketch-cache`。Android 数据属于应用内 `https://localhost`，网页按来源隔离；卸载、清除应用数据或回收缓存后，导航会按需重新生成。缓存不存业务内容、账号或凭证。

磁盘键包含兼容命名空间 `pencil-png-v1:rounded-font-v1:default-theme`、设备像素比和完整导航 SVG。导航尺寸、笔触、颜色、选中态、字体及主题影响兼容性；改动导航视觉算法时同步更新命名空间。静态资源由构建哈希更新，不依赖该命名空间。

导航 PNG 磁盘内容上限收紧为 **4 MiB / 512 条**，内存队列预算为 **4M 像素（约 16 MiB RGBA）**，这些均不是实测进程总内存。写入在同一事务中插入并淘汰最旧记录，首次写入也会按新预算回收旧页面 PNG。旧数据库 v2 的 `prepared` 存储保留以兼容覆盖安装，但没有读取或写入它的运行时代码；不再用旧整套缓存阻塞启动。

存储打不开、事务超时（1 秒）、空间不足或损坏时，退回导航生成；不隐藏文字或阻止点击。PNG 解码后校验尺寸，损坏记录移除后重新生成。普通静态装饰不受 IndexedDB 失败影响。

## 清理与验证

开发者工具 Application → IndexedDB 可删除仅 `livelife-sketch-cache`；先关闭同来源应用页。不要用 Android“清除应用数据”作为日常装饰清理，它可能同时删除其他数据。

在 frontend 目录启动开发服务后，在浏览器 Console 执行：

```js
await (await import('/scripts/sketch-cache.browser.mjs')).verifySketchCache()
```

脚本创建并删除独立测试数据库，覆盖跨队列磁盘复用、容量淘汰、事务中断、损坏重建、存储失败与晚到任务取消，不清除应用缓存。Node 测试另覆盖键兼容性与 IndexedDB 不可用降级；真实浏览器及 Android 渲染按[手绘回归](../plugins/README.md#android-手绘渲染回归)验证。
