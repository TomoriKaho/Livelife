# 地图活动查询 API

标准后端 `app.main:app` 注册本接口，只读、无需登录。HTTP 层调用信息系统 `content.map_query`；活动入库时统一解析地点，查询时统一完成时间、关键词、半径过滤和排序。地图客户端不再通过地点文本猜测建筑。

## GET /locations/activities

| 查询参数 | 类型与默认值 | 含义 |
| --- | --- | --- |
| `as_of` | 带时区 ISO 时间，可选；默认服务端当前时刻 | 时间窗口起点；翻页沿用首个响应的值 |
| `activity_before` | 带时区 ISO 时间，可选 | 窗口终点（不含）；默认北京时间今天至后天之后的零点 |
| `latitude`, `longitude`, `radius_m` | 可选，须一起提供 | WGS84 查询中心，半径大于 0、至多 50000 米 |
| `timestamp` | 有中心时必填，Unix 毫秒 | #82 最近设备位置时间；超过两分钟或超前十秒返回 422 |
| `keyword` | 可选，1–500 字 | 标题、正文、发布方和地点原文的字面子串搜索 |
| `limit`, `offset` | 1–100 默认 100；非负默认 0 | 过滤后分页，按活动开始时间、UUID 升序 |

返回 `as_of`、`window_end`、`items`、`nearby_buildings` 和 `next_offset`。完整字段见当前服务 `/docs`：

- `items` 保留 #84 的 `id/title/summary/platform/source_url/location/start_at/end_at`，增加 `source_name/place/location_resolution/distance_m`。`place.id` 是统一地点 ID，`place.building_id` 才是地图建筑 ID；房间和已明确的楼层见解析结果，未知保持 null。
- `distance_m` 为设备坐标到地点登记点的球面直线距离，不是建筑轮廓距离、步行距离或室内距离。无查询中心时为 null。
- `nearby_buildings` 每项包含 `place/distance_m/first_activity_at`。信息系统在半径内优先按最早匹配活动选建筑，不足五栋时按距离用已登记的无匹配活动建筑补位。目录或范围不足时可以少于五栋；无中心时为空。建筑选择基于全部过滤结果，与当前分页无关。
- 附近活动返回半径内的全部匹配活动，不再被五栋建筑卡片截断。只有唯一解析到地点且有开始时间的记录进入地图查询，歧义和未匹配记录仍保留在信息系统。

时间窗口为 `[as_of, window_end)`。已结束活动被排除；没有结束时间的活动按时间点处理，不假设其仍在进行。`as_of` 可以用于历史重放，但设备时间戳仍必须新鲜。分页沿用首个响应的两个时间边界；`next_offset` 非空时继续。offset 分页不是数据库快照，期间新增数据可能移动分页位置，客户端按 ID 去重。

例：

```bash
curl --get http://127.0.0.1:8000/locations/activities \
  --data-urlencode 'as_of=2026-11-11T10:00:00+08:00' \
  --data-urlencode 'keyword=讲座' --data-urlencode 'limit=20'
```

附近查询另外传入 `latitude=39.98857`、`longitude=116.30452`、`radius_m=300` 和当前设备 `timestamp`。位置由 #82 平台适配器获取，精度仍由客户端展示，不把精度值当搜索半径。

默认 `Cache-Control: no-store`；无数据库配置返回 503；缺少成组参数、无时区时间、逆序窗口和过期位置返回 422，错误体使用 `detail`。未注册地点的空库返回空列表；数据库缺表属于未迁移的配置错误，不伪装成空结果。

## 接入和兼容性

先迁移并按[信息系统目录导入说明](../../services/content/README.md#地点目录导入与旧数据回填)初始化地点，再通过汇总服务导入活动。读请求不写库、不采集外部信息；只有显式导入工具回填旧记录。

相比原 #84，筛选和排序发生在分页前，地点关系来自后端，响应增加结构化字段；前后端应一起更新。旧 Demo 的 `POST /events/nearby` 仅供独立演示，新地图只调用本标准接口。设备坐标参与查询但不写入业务表；GET 参数可能进入服务器访问日志，日志留存由部署配置管理。
