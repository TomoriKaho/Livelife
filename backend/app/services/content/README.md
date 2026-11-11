# 通用信息系统

为活动列表、日历、地图、推荐和 Agent 等后端模块提供共同的信息来源。[#60](https://github.com/TomoriKaho/Livelife/issues/60) 的 Python 服务负责采集契约、SQL 持久化和统一查询。[#63](https://github.com/TomoriKaho/Livelife/issues/63) 本地 Demo 用独立 HTTP 入口验证公众号原文导入、[#61](https://github.com/TomoriKaho/Livelife/issues/61) 所需的附近活动筛选，以及 Agent 可读取的检索文本。

## 地点目录导入与旧数据回填

标准地图接口见[地图活动查询 API](../../api/locations/API.md)。`content.map_query` 负责时间、关键词、半径与建筑排序；`InformationAggregator` 在写入时调用 `LocationResolver`。前端只展示结构化地点，不重复匹配原文。`InformationQuery.order_by` 默认仍为采集时间倒序，地图显式选择 `activity`，按开始时间和 UUID 升序。

在已设置开发用 `DATABASE_URL` 的 backend 终端执行：

```bash
uv run --locked alembic upgrade head
uv run --locked python -m app.services.content.catalog
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
```

导入工具只添加缺失地点和别名，不覆盖已维护坐标；随后重新解析尚无 `place_id` 的旧记录，保留来源与采集时间。重复运行不会重复插入；歧义保留候选，不自动选一个地点。正式数据库操作仍需负责人授权，API 启动和 GET 查询均不会自动运行该工具。空目录返回空地图结果，不能靠前端匹配绕过目录初始化。

`places.json` 的具名建筑来自仓库 [campus.json](../../../../frontend/src/assets/maps/campus.json)，坐标是建筑轮廓顶点均值经原投影逆变换的 WGS84 建筑级参考点，不是门口或室内测绘。已有八个地点的稳定 ID 保留，其他地点采用带 OSM 建筑 ID 的目录 ID；后续地图替换需维护 `building_id` 映射。来源与 ODbL 许可见[地图许可](../../../../frontend/src/assets/maps/LICENSE.md)，公开分发须保留署名与许可。地点目录不包含活动或个人位置；Demo 和标准服务共用这份目录。

## 三个官网信源接入标准后端

[`official_events.py`](../ingestion/official_events.py) 是显式运行的采集命令：直接请求图书馆、百周年纪念讲堂、数学科学学院官网，按各站页面字段提取标题、活动时间和地点，再通过 `InformationAggregator` 写入同一信息表。地图和日历都读取标准 `GET /locations/activities`，不依赖 `content_demo`，不在请求或服务启动时联网采集。

先按[后端开发入口](../../../README.md#本地数据库自动准备)启动持久本地 PostgreSQL。以下命令在 backend 执行；写库前将开发入口打印的本地连接串设置为当前终端的 `DATABASE_URL`：

```bash
# 仅采集，先核对 records.json 和 failures.json
uv run --locked python -m app.services.ingestion.official_events
# 明确导入同一批经过核对的记录；可重复执行，不增加重复活动
uv run --locked python -m app.services.ingestion.official_events \
  --import-records .local/official-events/records.json --write
```

[`official_events.json`](../ingestion/official_events.json) 保存人工选定的 11 个原文链接，来自三个直接信源，活动日期为 2026-11-07 至 2026-11-18。这是可重复采集的首批 URL 清单，不是账号历史发现或持续自动更新服务。可通过 `--manifest` 传入同格式清单，每批最多 20 篇；每页最多重试三次，有超时、失败报告和请求间隔。失败时保留本地快照并停止本批入库，不用示例填补。别名无法唯一匹配时停止导入，需核对地点；不能由模型猜坐标。

原始 HTML 按 SHA-256 保存到被忽略的 `.local/official-events/`，结构化记录保留 URL、采集时间、解析器版本、时间/地点证据和 HTML 摘要。可重放相同记录；数据库保留稳定 UUID，原始快照留在开发磁盘。搜索正文为事实摘录，完整网页不直接渲染到前端。当前每篇选定文章只有一个活动，来源 ID 为 `文章标识:event:1`；通用多活动拆分、取消活动识别、历史版本数据库和增量调度尚未实现。

活动时间按北京时间解析，发布时刻不从不可靠的 CMS 元数据猜测，缺失结束时间保留 null。已结束活动仍可按历史窗口查看；地图默认只显示今天至后天尚未结束的活动。地点关联沿用统一目录，新增的“智华楼”“四元厅”别名依据[数学学院原文](https://math.pku.edu.cn/kxyj/xsbg/tlb/dynamicsystems/26997626f8f14730bae48d04c3630ac4.htm)中“智华楼四元厅-224,225室”的明确对应关系，保持建筑级精度。

## 运行本地 Demo

在 `backend` 目录执行以下命令，打开 [交互式接口](http://127.0.0.1:18763/docs)。进程监听本机，允许 `http://127.0.0.1:8775` 与 `http://localhost:8775` 的 GET/POST 联调请求，并使用退出时清理的 SQLite 数据库，默认导入[北大图书馆讲座](https://lib.pku.edu.cn/hdrl/0a32a64919294d338dd72b58de36d348.htm)和[百周年纪念讲堂公告](https://hall.pku.edu.cn/hdgp/zxyc/l/e1020fa7bc6f463facebacabd50c5340.htm)的两条活动样本，以及三条标为 `platform=demo` 的合成地点解析样本。

```bash
uv run --locked python -m app.content_demo
```

| 本地接口 | 用途 |
| --- | --- |
| `GET /places` | 地点 ID、名称、校区、地图建筑 ID 和 WGS84 经纬度 |
| `GET /places/resolve?text=理教106` | 地点原文解析结果与匹配地点的坐标 |
| `GET /places/{place_id}/aliases` | 查看地点别名，地点不存在时返回 `404` |
| `POST /information` | 导入单条信息并自动解析 `activity_location`，未知的显式地点 ID 返回 `422` |
| `POST /events/nearby` | 直接接收 #82 的设备位置对象及半径，返回筛选后的活动 |
| `GET /information` | 统一查询所有条目，支持组合筛选 |
| `GET /events` | 同样的筛选参数，结果须有开始时刻和已关联地图地点 |
| `GET /information/{id}/chunks` | 供 Agent 读取的条目、来源及分块。条目不存在时返回 `404` |

地图调用时只需传查询中心经纬度和半径。以下请求查询纪念讲堂附近 120 米内的活动。字段校验失败时返回 `422`。

```bash
curl 'http://127.0.0.1:18763/events?longitude=116.30452&latitude=39.98857&radius_m=120'
```

### 统一地点库与文本解析

`information_places` 维护独立的地点 ID、名称、校区、WGS84 经纬度，以及可选的地图 `building_id`。`information_place_aliases` 保存地点别名，同一个别名可以对应多个地点。目录包含地图中的 161 个具名建筑，其中图书馆、纪念讲堂、理教、一至四教和古籍图书馆保留人工补充的别名。地点坐标取自[校园地图](../../../../frontend/src/assets/maps/campus.json)建筑轮廓的顶点均值，授权见[地图数据说明](../../../../frontend/src/assets/maps/LICENSE.md)。

采集器先把有来源依据的地点文字写入 `activity_location`。汇总服务在同一入库事务中执行 [`LocationResolver`](locations.py)，兼容全角字符、空白及英文字母大小写，通过名称和别名定位建筑，再提取紧随其后的教室号和显式楼层。匹配优先采用完整名称，多个地点候选保留歧义。调用方显式指定已登记的 `place_id` 时以该关联为准，解析方法标为 `explicit`。

| 输入 | 结果 |
| --- | --- |
| `理教 １０６` | `pku:yanyuan:science-teaching`，教室 `106`，对应地图建筑 `444991872` |
| `理科教学楼二层B106教室` | 理科教学楼，教室 `B106`，原文楼层 `二层` |
| `图书馆培训教室208+在线` | 图书馆，教室 `208`，原文保留线上部分 |
| `教学楼106` | `ambiguous`，返回多个地点 ID 候选，坐标为空 |
| `报告厅` 或 `清华图书馆` | `unmatched`，坐标为空 |

结果保存在 `Information.location_resolution`，包含 `status`、`place_id`、`room`、`floor`、`precision`、`method`、`matched_alias`、`evidence`、`candidates` 和解析器版本。精度当前为 `building`，楼层只从原文明示信息提取。多房间列表保留在原文，单值 `room` 留空。未知或歧义地点的条目可通过通用查询读取，附近活动查询要求已有地图关联。更新原文后重新解析，地点消失时清除此前的关联，旧快照重放遵循原有时间戳规则。

地点库当前覆盖上述燕园建筑，解析规则处理已提取的地点字段。任意文章的自动地点抽取、跨校区消歧、室内坐标和别名维护界面待后续接入。

### 对齐 #82 的设备位置接口

[`DeviceLocation`](../../schemas/location.py) 对齐 [#82 的 `CurrentLocation`](https://github.com/TomoriKaho/Livelife/blob/f397902b9ccfcc1ae087c363172c04de422714c5/frontend/src/platform/location.ts)。坐标为 WGS-84，沿用 `latitude`、`longitude`、米制 `accuracy`、Unix 毫秒 `timestamp` 和可选 `heading`。设备位置仅用于本次查询，存储的是活动所关联的地点。

`POST /events/nearby` 接收 `{location, radius_m, filters}`。`filters` 支持统一查询的关键词、来源、时间窗和分页，坐标及半径只在外层提供。Demo 接受两分钟内的位置并容许最多十秒的未来时钟偏差，过期或非法参数返回 `422`。`accuracy` 用于描述设备误差，搜索范围始终由 `radius_m` 决定。#82 临时定位失败后可能保留旧位置，因此调用方应在过期时刷新。

以下片段在前端确认 #82 的 `locationTrackingState.value` 为 `located` 且已获得 `currentLocation.value` 后使用，实际接口地址按同源代理或联调配置提供。

```javascript
const response = await fetch('/events/nearby', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    location: currentLocation.value,
    radius_m: 300,
    filters: { keyword: '讲座', limit: 20 },
  }),
});
```

这一步会将查询中心发送给信息系统，地图调用方按位置变化节流，取消旧请求，并丢弃迟到响应。地图绘制继续使用自身米制投影，活动结果通过 `place.building_id` 找到建筑。地图页面的本地接入与浏览器验证见[地图说明](../../../../frontend/src/pages/map/README.md#本地信息系统联调)，物理设备定位仍须真机验收。

### 自采公众号原文

用可见浏览器打开 `https://mp.weixin.qq.com/s/<article-id>` 格式的公开原文，确认正文可见。从 `backend` 目录在已打开该文章标签页的 Playwright CLI 会话中运行以下命令。脚本读取文章文本、标题、发布账号和可解析的发布时间，并记录实际抓取时间。遇到验证页或正文缺失会停止导出。图片及图片中的文字需另行处理。

```bash
umask 077
playwright-cli run-code "$(cat app/services/ingestion/wechat_capture.js)" --raw > /tmp/wechat-article.json
uv run --locked python -m app.content_demo --wechat-json /tmp/wechat-article.json
```

实测可直读[北京大学人工智能研究院的公众号原文](https://mp.weixin.qq.com/s/l6Yiqi5KvcUJ-M1jetRloQ)。样本经[北大新闻网](https://news.pku.edu.cn/info/3001/3306131.htm)核对后，在本地 JSON 补录 `activity_date`、`activity_location`、`place_id` 和 `raw_payload.event_evidence_url`，开场时刻留空。普通 HTTP 请求两条原文均收到验证页。浏览器方式已验证已知链接的单篇获取，账号历史和增量采集待验证。开源参考 [WeRead Omni](https://github.com/teng-lin/weread-omni) 使用个人微信读书登录读取公众号列表，正文可用性需要独立实测。

[北大知道](https://pkuknow.cn/)的公开面板按公众号和北大官网列出信源、收录数，并提供按来源查看和活动日历。实测面板列出 203 个公众号，站内采集流程无法从公开页面核实。本 Demo 的入库数据均直接来自北大官网或公众号原文。

### 课程与教室信源

登录北大门户后，院系课表 `retrCourseScheduleList.do` 返回课程号、班号、周次和含教室的上课时间，数学科学学院样本同时验证了本科、研究生课表。同一请求匿名访问返回 `401`。本人课表也含节次、周次和地点。空闲教室 `retrClassRoomFree.do` 无需登录即可取得房间、容量和分节次状态。选课系统的选课计划和结果页本次显示系统提示，未取得选课快照。[北大门户](https://portal.pku.edu.cn/) · [选课系统](https://elective.pku.edu.cn/)

后续课程适配建议保留学年学期、课程号、班号、周次、星期、节次和教室原文，按校历和作息表展开到具体日期，再关联统一地点 ID。个人课表留在用户授权范围内，公共课表才作为共享信源。选课快照无法从官方渠道取得时，可单独评估拼好课。

## 三部分职责

```text
渠道适配器 InformationSource.fetch()
    → InformationInput
    → collect_information() 校验渠道归属
    → InformationAggregator.ingest() 校验、规范化、幂等保存
    → information_items
    → InformationProvider.get() / list()
    → Information → 各业务模块自己的服务 / API
```

- 获取。[`InformationSource`](../ingestion/source.py) 定义 `platform` 和 `fetch()`。公众号样本由 [`WeChatSnapshotSource`](../ingestion/wechat.py) 读取本地 JSON，经现有采集协议导入。新增平台可使用自己的适配器提供相同格式。
- 汇总：[`InformationAggregator`](aggregation.py) 保存记录并保留来源、原始正文和渠道原始字段；处理包括字段校验、UTC 时间规范化、正文首尾空白清理及地点库规则解析，活动时间仍由采集器提供。
- 提供：[`InformationProvider`](provider.py) 返回独立于 ORM Session 的只读 Pydantic 对象，供其他后端服务组合使用。调用方按自己的业务要求组织列表、日历和地图接口。

数据库操作在 [`InformationRepository`](../../repositories/sql/information.py)，表结构在 [`InformationRecord`](../../db/models/information.py)。汇总服务负责事务；repository 不提交或回滚事务，查询服务不写入数据。

## 统一格式与缺失值

字段类型、约束及 JSON Schema 见 [`schemas/information.py`](../../schemas/information.py)。`InformationInput.model_json_schema()` 和 `Information.model_json_schema()` 可用于内部契约检查。Demo 的 `/openapi.json` 描述本地查询接口。

| 字段 | 输入规则与含义 |
| --- | --- |
| `platform` | 必填，小写字母开头，由小写字母、数字及下划线组成，最多 64 字符；例如 `wechat`、`pku_hole`、`zhihu`、`xiaohongshu` |
| `source_id` | 必填，平台内稳定且唯一，最多 255 字符。来源 ID 仅在账号内唯一时，加账号命名空间，例如 `account-a:article-123` |
| `source_url` | 可选 HTTP/HTTPS 原文地址；无公开链接时保留 `None`，来源仍由平台和来源 ID 标识，不编造链接 |
| `source_name` | 可选的发布账号或单位名称，用于显示和关键词检索 |
| `title` | 可选标题，去除首尾空白后长度 1–500 |
| `content` | 必填且不能只有空白；输入正文原样另存 `raw_content`，统一输出去除首尾空白 |
| `fetched_at` | 必填，本次实际获取时间，不得用文章发布时间或入库时间代替 |
| `published_at` | 可选，来源平台提供的发布时间 |
| `activity_location` | 可选，最多 500 字符，活动地点原文，例如“理科教学楼 101” |
| `place_id` / `place` | 可选的 `information_places` 外键。查询响应展开地点 ID、名称、校区、地图 `building_id` 和 WGS84 经纬度 |
| `location_resolution` | 输出专用，提供地点匹配状态、教室、显式楼层、精度、原文依据、候选与解析版本 |
| `activity_date` | 只确认活动日期时，保存来源当地的日历日期，例如 `2026-10-18` |
| `activity_start_at` / `activity_end_at` | 可选，活动开始/结束时间；同时存在时结束必须晚于开始 |
| `registration_deadline_at` | 可选，报名截止时间 |
| `raw_payload` | 输入专用，可选 JSON 对象，保存适配器需要追溯的原始字段，默认为 `{}`；提供服务不返回它 |

所有时间戳必须带时区，例如 `2026-10-11T12:00:00+08:00`，保存和输出统一为 UTC。`activity_date` 保留原日历日期。普通文章也可入库，未知的活动时刻、地点和可选文本用 `None` 表示。

输出 `Information` 在公共字段之外增加：

- `id`：系统 UUID，供消费模块引用，后续更新保持不变。
- `first_fetched_at`：首次成功入库那份快照的获取时间，后续更新保持不变；不是历史最早发布时间。
- `processed_at`：当前保存快照的处理时间，重放被忽略时不改变。

当前一条记录表示一个平台来源信息，附带最多一组活动时间和地点。多活动文章拆分、跨平台活动合并、跨校区地点消歧、分类、摘要、全文检索和访问控制待后续明确契约。正文作为不可信的来源资料传递，消费方显示 HTML 时按自身规则渲染。

## 幂等、更新与失败

`(platform, source_id)` 有数据库唯一约束，使用数据库 `ON CONFLICT` 原子写入：

- 第一次获取创建记录；只有 `fetched_at` 更晚的输入才替换当前快照，更新时保留 UUID 和首次获取时间。
- 相同获取时间的重放、同时间不同内容和晚到的旧快照都被忽略。同时间冲突采用先成功保存的版本；适配器应稳定复用重试记录的获取时间。
- 新快照完整替换可变字段，缺失的活动字段会恢复为 `None`，不把旧活动信息错误地带到新版文章。
- 不同平台即使来源 ID 或正文相同也分别保存，不按正文相似度合并。
- 当前只保留最新原始正文与 `raw_payload`，不提供历史版本库。

`ingest(records)` 每批最多 1000 条，先完整遍历并校验，再在一个事务中保存。输入无效、采集迭代中失败、超过批量上限时不写入；SQL 写入或输出转换失败时整批回滚。空批返回 `()`。同一来源在一批出现多次时，返回一次最终快照，结果按来源首次出现的顺序排列。

每次汇总使用新的、尚未开启事务的 Session，由汇总服务提交或回滚；不要在已有读写事务的 Session 中调用 `ingest()`。调用方负责关闭 Session，不要混入其他模块的待提交修改。提供服务可在调用方的读取 Session 中使用，返回对象可在 Session 关闭后继续读取。

采集器负责网络访问、超时、重试、平台游标和权限；`collect_information()` 本身不联网、不调度、不吞掉异常，也不自动重试。渠道结果的 `platform` 必须与适配器一致。一次 `fetch()` 最多产生 1000 条，更多数据由适配器分页分批提交；只有保存成功后才推进对应游标。当前没有独立 worker、队列或游标持久化。

## 查询语义

`get(UUID)` 返回 `Information | None`。`list(InformationQuery(...))` 返回元组，默认 50 条，最大 100 条，`offset` 默认为 0。按 `fetched_at` 降序、UUID 降序排列；同一数据集合翻页顺序稳定，采集更新期间 offset 分页可能移动，当前不提供快照游标。

| 查询参数 | 规则 |
| --- | --- |
| `platform` | 精确匹配一个平台 |
| `fetched_after` / `fetched_before` | 获取时间范围 `[after, before)`，可只设一端 |
| `activity_after` / `activity_before` | 查询与该时间窗口相交的活动，窗口为 `[after, before)`，可只设一端 |
| `activity_location` | 地点原文包含匹配，`%`、`_` 等按普通字符匹配 |
| `keyword` | 标题、正文、发布账号、地点原文中任一字段包含关键词，英文字母忽略大小写，通配符按普通字符匹配 |
| `longitude` / `latitude` / `radius_m` | 一起传入 WGS84 经纬度和米制半径，半径大于 0 且最多 50,000 米。按球面距离匹配已关联地图地点的条目 |
| `events_only` | 仅返回有活动开始时刻且已关联地图地点的条目。`/events` 始终采用此条件 |
| `limit` / `offset` | 数量及偏移，非负偏移，数量 1–100 |

不同筛选条件取交集，过滤完成后分页。有开始和结束时按区间相交，只有开始时间时作为时间点匹配。仅确认日期或仅有结束时间的条目仍保留在通用列表中。查询北京时间的某一天时，传入带 `+08:00` 的当天零点和次日零点。

## Agent 读取与向量检索

[`retrieval_document()`](retrieval.py) 输出统一条目和按序号排列的正文块。`chars-v1` 每块正文最多 480 字符，相邻块重叠 60 字符，块前附标题，`text_sha256` 对实际用于检索的文本取哈希。Agent 可以先用结构化条件缩小候选范围，再取分块并引用 `source_url`。

后续可独立存储 `information_id`、`chunking_version`、`ordinal`、`model_version`、`text_sha256` 与 `embedding`。前四项组合标识向量记录，文章更新后用内容哈希复用未变更的块，清理过期块。向量存储和相似度排序待接入，可复用同一地点与时间查询契约。[pgvector](https://github.com/pgvector/pgvector)

## 本地准备与调用

后端运行时与依赖安装见 [backend README](../../../README.md)。本地开发推荐在 backend 目录运行 `uv run --locked --group local-db python -m app.dev --port 18000 --reload`，它会自动安装并启动 PostgreSQL、创建数据库和执行迁移。保持该终端运行，将控制台打印的 `DATABASE_URL` 设置到运行采集脚本或 worker 的另一个终端即可使用。数据保存在 `backend/.local/postgres/`，停止再启动仍会保留；安装平台、路径与排错见[本地数据库自动准备](../../../README.md#本地数据库自动准备)。

使用自己安装的 PostgreSQL 时，先准备独立开发数据库，再设置连接串并手动执行迁移；下列 PowerShell 示例中的凭证自行替换：

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://<用户名>:<密码>@127.0.0.1:5432/<开发数据库>'
uv run alembic upgrade head
uv run alembic current
```

迁移读取进程变量，不自动读取后端 `.env`。标准 `app.main:app` 入口不自动迁移；自动迁移仅发生在开发入口管理的本地数据库。没有数据库时 hello 和存活检查仍可用，信息持久化需要连接数据库及创建表。现有数据库连接探针只验证 `SELECT 1`，不能代替检查迁移版本。

在 backend 目录的 Python 进程中，下面例子使用人工样例演示写入与查询；无需启动 Uvicorn：

```python
from datetime import datetime

from app.db.session import Database
from app.schemas.information import InformationInput, InformationQuery
from app.services.content import InformationAggregator, InformationProvider

database = Database.from_environment()
if database.session_factory is None:
    raise RuntimeError("请先设置 DATABASE_URL 并执行迁移")

try:
    record = InformationInput(
        platform="manual",
        source_id="example:lecture-1",
        source_url="https://example.com/lecture-1",
        title="人工样例讲座",
        content="这是一条用于本地开发的信息样例。",
        fetched_at=datetime.now().astimezone(),
        activity_location="理科教学楼 101",
        activity_start_at="2026-10-12T19:00:00+08:00",
        activity_end_at="2026-10-12T21:00:00+08:00",
    )
    with database.session_factory() as session:
        saved = InformationAggregator(session).ingest([record])
    with database.session_factory() as session:
        provider = InformationProvider(session)
        detail = provider.get(saved[0].id)
        day = provider.list(
            InformationQuery(
                activity_after="2026-10-12T00:00:00+08:00",
                activity_before="2026-10-13T00:00:00+08:00",
            )
        )
    print(detail.model_dump(mode="json"))
    print([entry.model_dump(mode="json") for entry in day])
finally:
    database.close()
```

未来渠道接入实现这个协议，再交给汇总服务。示例仍是人工数据，不代表真实公众号可用：

```python
from app.services.ingestion import collect_information


class ExampleSource:
    platform = "manual"

    def fetch(self):
        # 真实适配器在这里访问已授权渠道，并转换为 InformationInput。
        return [record]


with database.session_factory() as session:
    saved = collect_information(ExampleSource(), InformationAggregator(session))
```

上面的适配器片段放在前一个示例的 `try` 内、`database.close()` 之前执行。内部服务只接收可信后端调用，不承担业务账号鉴权；当前应仅导入允许分发的公开或模拟内容，原始字段不得包含平台令牌、Cookie、账号密码或未经授权的私有数据。后续渠道接入须自行限定可采集、可分发范围。

## 迁移、验证与回滚

`0001_information` 创建信息表及来源唯一约束，`0002_information_places` 添加地图地点表、地点外键、发布方及活动日期字段。`0003_place_resolution` 增加地点别名、校区、地图建筑关联和解析结果。升级保留既有地点 ID，并把旧 Demo 地点 ID 写入 `building_id`。已有条目的解析结果为空，下一次较新快照入库时生成。回退 `0003` 会删除别名、地图关联及解析结果，保留原地点和信息记录。本联调分支将地点迁移接在 `0005_agent_account_auth` 之后，使用新的临时数据库验证完整迁移链。原内容和来源 ID 继续可用。正式环境迁移遵循[部署入口](../../../../docs/deployment.md)。

仅在可丢弃的开发数据库中，`uv run alembic downgrade base` 可回退首个迁移，**会删除信息表和全部信息数据**；需要保留数据时先导出并验证备份。再次 `upgrade head` 只重建表，不恢复已删除的数据。

在 backend 目录执行：

```bash
uv run pytest tests/test_information.py tests/test_migrations.py
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv lock --check
```

自动测试使用临时 SQLite 文件验证实际迁移、跨 Session 持久化、来源更新与幂等、失败回滚、查询过滤、时间窗口和分页；另生成 PostgreSQL 离线迁移 SQL。这些检查不等于真实 PostgreSQL 连接、并发写入或真实渠道采集已通过。PostgreSQL 验证时先在独立开发库执行迁移，再按上例写入、读取和重复导入，确认 UUID 稳定以及 `/health/ready` 可连接；正式环境操作遵循[部署入口](../../../../docs/deployment.md)。

`uv run --locked --group local-db pytest --local-postgres` 另在测试临时目录启动真实 PostgreSQL，验证自动建库、迁移、信息写入、重启后读取及停止进程；不会接触默认开发数据目录或 `DATABASE_URL` 指定的外部数据库。默认 `uv run pytest` 跳过这项集成测试，不下载数据库程序。该项不覆盖多进程并发或真实平台采集。
