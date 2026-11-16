# 账号活动收藏 API

所有路径使用账户 `Authorization: Bearer <access_token>`，不接受客户端指定所有者。返回 `Cache-Control: no-store`。缺失、过期或撤销凭证为 401（含 `WWW-Authenticate: Bearer`），未配置数据库为 503，字段校验为 422，错误沿用 FastAPI `detail`。

## 对象与保留规则

使用信息系统 `information_items.id` 的稳定 UUID。可收藏对象须具有活动日期或明确开始时间，且平台不为 `demo`；不存在、纯文章、演示对象不能新建收藏（404）。前端演示字符串 ID 不提交，非法 UUID 返回 422。文章收藏不复用本资源。

同一账户对同一 UUID 只有一条收藏，保留至主动取消或注销账号；退出登录不清空服务端收藏。不迁移旧前端演示收藏。

活动存在并符合上述条件时展示**最新字段**，未知保持 null，不以旧快照补全。收藏时只保存标题、来源平台/名称/链接、活动日期和起止时间快照，不保存正文、原始数据或地点副本。原记录清理或不再符合活动条件时，保留 UUID 和快照，返回 `available: false`，地点为 null。客户端标注“内容已不可用 · 收藏时信息”，不提供有效活动跳转，仍可取消。

当前信息系统没有审核下架或取消/改期状态；这些由 #110/#109 引入。届时须同步本服务的可用性判断，避免隐藏条目继续作为有效活动返回。本次不声明已实现审核下架。

## 接口

| 方法与路径 | 成功结果及特殊规则 |
| --- | --- |
| `PUT /favorites/activities/{target}` | 200，`FavoriteItem`；重复操作不新增、不改变首次收藏时间或快照。已有不可用收藏也可重复 PUT |
| `DELETE /favorites/activities/{target}` | 204；本人未收藏或原记录已清理也成功，不影响他人 |
| `GET /favorites/activities/{target}` | 200，本人收藏摘要或不可用快照；本人未收藏为 404，不透露他人状态。供收藏跳转地图使用，不是公共详情接口 |
| `GET /favorites/activities` | 200，`FavoritePage`；筛选、分页见下文 |
| `POST /favorites/activities/status` | 请求 `{"ids":["<uuid>"]}`，最多 100 个；返回 `{"saved_ids":["<uuid>"]}`，只含请求中本人已收藏 ID。允许空数组、重复输入；输出不重复 |

完整类型由 OpenAPI 的 `FavoriteItem/FavoritePage/FavoriteIds` 维护。条目含 `id/saved_at/available/title/platform/source_name/source_url/activity_date/start_at/end_at/location/place/status`；地点复用 `MapPlace`，未知为 null。

### 列表与时间

`status` 可省略或指定 `upcoming/ongoing/ended/unknown`；`limit` 默认 20、范围 1–100；`offset` 默认 0、非负。按首次收藏时间和 UUID 倒序，先过滤后分页。响应为 `items/as_of/counts/total/next_offset`；`counts` 始终包含本人所有收藏的四类数量，`total` 为总和，`next_offset: null` 表示结束。

`as_of` 默认服务端当前时刻，亦接受带时区 ISO 时间；翻页沿用首个响应值，重新加载重取当前时间。offset 分页不是数据快照，并发增删可移动位置，客户端按 ID 去重。以 UTC 比较绝对时间，界面显示北京时间。

| 已知时间 | 分类 |
| --- | --- |
| 缺少开始时间，包括只有日期 | `unknown`（时间待定），不推测零点或全天 |
| 当前时刻小于开始时间 | `upcoming`（待开始） |
| 已到开始时间，结束时间已知且尚未到结束时间 | `ongoing`（进行中），区间 `[start_at, end_at)` |
| 已到结束时间；或只有开始时间且已到该时间点 | `ended`（已结束）；后者注明“结束时间未知，按时间点分类”，不代表已核实实际结束 |

不可用收藏按快照时间分类，并额外显示不可用标记。活动更新后使用新时间，不以收藏时间分类。

## 本地联调与迁移

先导入真实活动，登录取得账户令牌，再使用实际信息 UUID 调用上表接口。例如 `GET /favorites/activities?status=upcoming&limit=20&offset=0` 配合 `Authorization: Bearer <account-token>`；不能直接发送占位符。

`0006_activity_favorites` 在当前 `0003_place_resolution` 后新增表和索引，不修改既有账号、活动、对话。账户 FK 为 CASCADE，注销亦显式清理；信息 UUID 刻意没有级联 FK，允许保留被清理活动的快照。降级删除收藏表及全部收藏，不影响原活动；收藏无法恢复。

PR #99 有独立 Agent 历史迁移；合并后须协调 Alembic 迁移链并验证单一 head，不能把未合并分支当当前依赖。开发入口自动迁移其本地库，独立库按[后端教程](../../../README.md#数据库配置与健康检查)升级；不在未确认的共享库操作。

在 backend 执行 `uv run pytest tests/test_favorites.py`。真实 PostgreSQL 并发检查执行 `uv run --locked --group local-db pytest tests/test_favorites.py --local-postgres`，只使用独立临时数据库。前端联调见[个人页说明](../../../../frontend/src/pages/more/README.md#账号活动收藏)。
