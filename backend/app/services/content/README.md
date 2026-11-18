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

### 补充场地与校外地点

以下 WGS84 坐标为轮廓去掉闭合重复末点后的顶点均值，不是入口或室内测绘。`building_id=null`，不伪造校园建筑关联；解析精度为 `site`。地图客户端是否显示校外范围是另一项能力，目录入库不代表校园底图已扩展。

| 地点 / 稳定 ID | 经度 / 纬度 | 核实与别名 |
| --- | --- | --- |
| 二体网球场 / `pku:yanyuan:tennis-2` | 116.301119875 / 39.98943555 | [OSM way 226702940](https://www.openstreetmap.org/way/226702940)，仓库 `yanyuan-osm.json` 保存同一网球场轮廓；[北大体育教研部场馆介绍](https://pe.pku.edu.cn/zhcg/cgjs.htm)说明二体有室外网球场。别名仅“第二体育馆网球场”“北京大学二体网球场”，不是第二体育馆或二体篮球场。 |
| 北京大学红楼 / `pku:offcampus:red-building` | 116.39914353846153 / 39.92331917692308 | [OSM way 187204004 v8](https://www.openstreetmap.org/way/187204004/history)，[北京市官方介绍](https://www.beijing.gov.cn/renwen/rwzyd/qgzdwwbhdw/bjdxhl/202210/t20221024_2842307.html)核实东城区五四大街29号；别名仅“北大红楼”，校区标记为“北京东城（校外）”。 |

OSM 红楼对象附带的门牌标签与官方地址不一致，门牌以官方29号为准，坐标取其明确命名的建筑轮廓；不把该标签作为地址别名。原始 OSM 数据沿用 ODbL 署名要求。地点目录不增加“红楼”“网球场”“二体”等泛称。新增两地点拒绝以其名称开头的更长场所名称；红楼文本显式出现矛盾区名或五四大街其他门牌号时不匹配。更多自然语言地址歧义仍需人工核对，不是通用地址解析器。

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

`information_places` 维护独立的地点 ID、名称、校区、WGS84 经纬度，以及可选的地图 `building_id`。`information_place_aliases` 保存地点别名，同一个别名可以对应多个地点。目录包含地图中的 161 个具名建筑及经核实补充的场地/校外地点，其中图书馆、纪念讲堂、理教、一至四教和古籍图书馆保留人工补充的别名。地点坐标取自[校园地图](../../../../frontend/src/assets/maps/campus.json)建筑轮廓的顶点均值，授权见[地图数据说明](../../../../frontend/src/assets/maps/LICENSE.md)。

采集器先把有来源依据的地点文字写入 `activity_location`。汇总服务在同一入库事务中执行 [`LocationResolver`](locations.py)，兼容全角字符、空白及英文字母大小写，通过名称和别名定位建筑，再提取紧随其后的教室号和显式楼层。匹配优先采用完整名称，多个地点候选保留歧义。调用方显式指定已登记的 `place_id` 时以该关联为准，解析方法标为 `explicit`。

| 输入 | 结果 |
| --- | --- |
| `理教 １０６` | `pku:yanyuan:science-teaching`，教室 `106`，对应地图建筑 `444991872` |
| `理科教学楼二层B106教室` | 理科教学楼，教室 `B106`，原文楼层 `二层` |
| `图书馆培训教室208+在线` | 图书馆，教室 `208`，原文保留线上部分 |
| `教学楼106` | `ambiguous`，返回多个地点 ID 候选，坐标为空 |
| `报告厅` 或 `清华图书馆` | `unmatched`，坐标为空 |

结果保存在 `Information.location_resolution`，包含 `status`、`place_id`、`room`、`floor`、`precision`、`method`、`matched_alias`、`evidence`、`candidates` 和解析器版本。有校园建筑轮廓关联时精度为 `building`，无建筑关联的参考地点为 `site`，楼层只从原文明示信息提取。多房间列表保留在原文，单值 `room` 留空。未知或歧义地点的条目可通过通用查询读取，附近活动查询要求已有地图关联。更新原文后重新解析，地点消失时清除此前的关联，旧快照重放遵循原有时间戳规则。

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

## 内部 Agent 信息处理（#101）

`app.services.content.processing` 接收已获取的 `InformationInput` 原文，不负责联网采集或定时调度。它复用服务端模型配置与 HTTP 传输工具，但使用独立提取提示词、任务表及额度记录，不创建用户聊天、读取私人历史或扣用户聊天额度。`processing/schemas.py` 是内部候选契约的主要来源；不新增 HTTP API。

```text
本地原文 JSON → submit（持久化原文与内容哈希）
             → run（模型提取 → 类型/原文证据校验 → 地点目录解析）
             → needs_review（保留候选，不进入公开查询）
             → 人工核对 → publish（仅新增）→ information_items → 现有查询服务
```

首版只提取单活动的日期、起止时刻、报名截止、地点文字以及候选摘要。每个非空活动字段必须附连续原文摘录；日期必须有显式年月日（支持空格和全角排版），时刻需原文明示 H:MM 或 HH:MM，按北京时间处理，不从发布日期猜年份。原文缺年份、只有相对日期或其他未支持表达时留空。地点 ID 和坐标不由模型生成，沿用地点目录解析。证据存在不代表语义正确，摘要和字段仍必须人工核对；多活动、取消/改期、冲突或不确定内容仅保留候选，后续分别由 #108/#109/#110 处理。

处理版本 `campus-extraction-v5` 将模型选择与程序格式化分开：模型的地点字段只返回连续原文 `quote`，不生成地点值、ID或坐标；时间的 `value` 仅复制原文单个 H:MM 或 HH:MM，`quote` 包含该时刻及唯一完整年月日；程序转换为带时区的 ISO 时间。日期缺年份、多个日期或未支持的时刻表达不能自动转换。原始选择与转换后的候选均保留，改写、拼接和编造的证据会因原文不包含该连续片段而失败。

地点值由原文选择生成，折叠连续空白为单个空格，去除括号内侧/前面的排版空白和门牌号周围的特定横向空白；原始 quote 不变。不是删除所有空白或重写地点。摘要引用可为正文精确片段或完整原文标题，活动证据仍只接受正文。原文来源校验不能证明所选地点在语义上属于本次活动，仍需审核。

清理后的地点沿用本模块地点目录解析：唯一名称/别名命中得到 `place_id`，地图建筑 ID 和坐标来自目录，精度按目录返回 building 或 site（场地/校外地点）；多地点返回 ambiguous，目录未覆盖返回 unmatched。测试库需显式导入目录才能验证匹配。大厅、房间和球场不因名称相近而自动新增坐标，也不把外校/校外地址映射为北大建筑。

### 配置和运行

在独立开发库设置 `DATABASE_URL` 并执行 `uv run --locked alembic upgrade head`。需要地图地点匹配时按本文件前文导入地点目录。模型沿用 `AGENT_LLM_BASE_URL`、`AGENT_LLM_API_KEY`、`AGENT_LLM_MODEL`、`AGENT_LLM_REASONING_EFFORT` 和 `AGENT_LLM_TIMEOUT_SECONDS`；密钥只在服务端环境或被忽略的 backend/.env。端点须支持非流式 `/chat/completions` 和 `response_format=json_object`，不支持时明确失败，不静默换模型。

以下命令在 backend 执行。`articles.json` 是一个 `InformationInput` 对象或最多 100 条的数组，包含标题、正文、平台、稳定来源 ID、原文链接、发布方、获取时间及可用的发布时间。仅提交允许处理的公开原文或合成样本。文件不能包含凭据或私人数据；真实冷启动文章保存在仓库外，不作为测试 fixture 提交。图片里的文字尚未识别时需人工检查，纯图片文章不能用空正文冒充已完整提取。

```bash
uv run --locked python -m app.services.content.processing submit /absolute/path/articles.json
uv run --locked python -m app.services.content.processing run <job-uuid>
uv run --locked python -m app.services.content.processing show <job-uuid>
# 筛选失败任务，show 同时显示原文选择、失败阶段及每次尝试的诊断
uv run --locked python -m app.services.content.processing list --status failed --limit 50 --offset 0
# 仅失败后显式重试，不会自动循环调用模型；原 run --retry 仍兼容
uv run --locked python -m app.services.content.processing retry <job-uuid>
# 有界批处理：先提交并保存清单，再逐篇运行并持久保存检查点
uv run --locked python -m app.services.content.processing submit /absolute/path/articles.json > /absolute/path/jobs.json
uv run --locked python -m app.services.content.processing batch /absolute/path/jobs.json \
  --output /absolute/path/results.json
# 检查失败原因后明确执行；只重试清单内失败项，成功项复用
uv run --locked python -m app.services.content.processing batch /absolute/path/jobs.json \
  --retry-failed --output /absolute/path/retry-results.json
# 逐项核对原文、证据和候选后，由可信维护者明确执行
uv run --locked python -m app.services.content.processing publish <job-uuid> \
  --reviewed-by '<维护者标识>' --reason '<核对依据>'
```

`list` 支持状态、版本过滤及分页（单页最多 100 条）。`show` 的 `diagnosis` 提供错误分类、建议动作、剩余尝试数与当前模型/版本是否一致；切换模型或规则后，应重新 submit 原文，不能直接重试旧版本任务。`batch` 接受 submit 的 JSON 清单，去重后限 1–100 个任务，先验证所有 ID，再按请求速率串行执行。默认仅执行 pending，`--retry-failed` 仅执行 failed；不会在本轮自动重试新失败。单篇失败继续下一篇，成功项复用，预算/尝试上限仍生效；未全部达到 needs_review/published 或存在执行阻塞时返回非零退出码。每篇结束原子替换输出文件（含原文，请放在仓库外）。进程崩溃时以数据库为准，show 可查最后状态；遗留 running 需等待租约过期后显式 run 恢复，batch 不隐式接管。

命令仅供具有数据库访问权限的维护者使用，`reviewed-by` 是操作记录，不是认证机制。发布是显式新增，业务唯一约束阻止覆盖已存在来源；同一任务重复发布返回相同信息 ID。既有业务记录的修正、替换及完整审核界面交由 #110；本节人工回退只生成未发布原文的新候选；没有确认的候选不会进入地图、日历或 Agent 公开检索。原始正文保留，生成摘要不替换原文。

### 普通缺失、阻断与最小人工回退

v5 将两类问题分开：`missing_fields` 由程序按空字段计算，模型的 `notices` 解释普通缺失（未给报名截止、未写年份、时间表达暂不支持等）；`ambiguities` 仅保留事实冲突、多种解释无法选定、取消改期等阻断问题。普通缺失允许空值，不阻断维护者明确确认。多活动、不确定类型、非空 ambiguities 或地点解析 ambiguous 仍阻断发布。地点解析版本 `campus-alias-v3` 将“或/或者/与”等连接词视为分隔，多个已知地点不能只取第一个。地点 unmatched 保留文字和空 place_id，不自动猜坐标；未匹配本身不等于事实冲突。

`show.review_gate` 使用当前校验与地点目录计算 `eligible_for_confirmation`、`blocking_reasons`、`missing_fields`、`notices` 和地点解析。eligible 只表示可交给维护者确认，绝不自动发布，也不保证摘要语义正确。旧版本的 ambiguities 不按关键词猜测并迁移为 notices；要么重新 submit 生成 v5 任务，要么明确人工回退。

模型超时/不可用时可直接人工选原文；缺证据、格式错误或冲突时先核对原文与历史尝试。以下操作只供可信数据库维护者使用，操作人标识是审计字段，不是新的身份认证机制：

```bash
# 1. 查看完整原文、模型选择、逐次失败诊断、当前阻断项
uv run --locked python -m app.services.content.processing show <原任务UUID>
# 2. 导出审核草稿到仓库外；不会改变任务或调用模型
uv run --locked python -m app.services.content.processing export-fallback <原任务UUID> > /absolute/path/review.json
# 3. 人工编辑 review.json，核对后生成一个新的待审核候选
uv run --locked python -m app.services.content.processing fallback /absolute/path/review.json \
  --reviewed-by '<维护者标识>' --reason '<总体核对依据>'
# 4. 查看返回的新任务，再明确确认发布；原任务仍保留
uv run --locked python -m app.services.content.processing show <新任务UUID>
uv run --locked python -m app.services.content.processing publish <新任务UUID> \
  --reviewed-by '<维护者标识>' --reason '<最终确认依据>'
```

草稿包含 `source_job_id`、`source_fingerprint`、`selection`、`resolutions`。不要修改来源 ID 或指纹；`selection` 使用与模型相同的原文选择契约（地点只有 quote，时刻 value 为原文 H:MM 或 HH:MM）。若模型没有产生合法选择，selection 为 null，需依 `processing/selection.py` 的契约手工填写。每个 resolutions 键对应 show 中的一个阻断 code，必须逐项填非空理由；真实缺失应保留 null，不能编造年份、时刻、坐标或改写证据。旧版误将缺失记为冲突时，可将该说明转移到 notices，并在对应 resolution 中记录原因。

回退入口再次运行原文、格式、地点校验；冲突仍未解决或地点仍歧义时拒绝生成可发布候选。若原文无法判定事实，应保留原任务待审核，不能为通过校验而删掉冲突说明。多活动拆分、取消/改期关联其他记录，以及用外部资料补充原文没有的事实不在此入口范围，转交后续处理。已发布任务不能走该入口覆盖业务数据。

人工回退不修改原文、原模型候选或尝试日志。它创建 `model=human`、`version=manual-fallback-v1` 的新任务，在 `result.manual_review` 保存来源任务、原快照指纹、处理人、理由、逐项处理说明和时间；不产生模型用量。相同审核包与处理人/理由重复提交复用新任务，发布仍受来源唯一约束。原任务被重试或状态/结果改变后旧草稿失效，须重新导出，避免按过期依据确认。人工回退不能替代 #110 的权限界面、审核队列及已发布内容修订。

### 幂等、失败和用量

`information_processing_jobs` 保存原文快照、内容哈希、版本、模型、状态及候选。哈希包含来源身份、正文、标题、发布时间和发布方，不含获取时间及适配器 `raw_payload`；重复获取相同内容复用原任务及首次提交快照，不重复调用模型。修改原文、模型端点/名称/推理参数或提升处理版本生成新任务；已有成功候选不被失败重处理覆盖。模型结果 `needs_review`、执行 `running`、失败 `failed` 和发布 `published` 明确区分。

`information_processing_attempts` 保存每次模型尝试的预留额度、返回用量、脱敏错误码及独立 diagnostics 快照。诊断包含失败阶段、固定校验码、结构错误的字段路径/类型，以及已合法解析的原文选择和候选；重试不会覆盖历史尝试。未解析的模型响应及异常消息不保存；旧迁移之前的尝试 diagnostics 为 null，不能追溯补造。预算按最近 24 小时累计预留量保守计算，不因超时、断流、重启或重试退款；预留量是提示词 UTF-8 字节数加输出上限，并非精确计费。实际 token 用量另存，包括上游已返回用量但因输出截断而失败的响应；上游未返回用量时记为未知，不当作零消耗。尚未实现货币价格换算。模型限流、超时、非完整终态、格式/证据错误均保留失败，不写业务信息。结构合法但证据不通过的候选保留固定错误码供排查，失败状态不能发布；不会保存任意上游错误文本或未解析响应。未配置模型不发请求，`run` 返回失败退出码。

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `CONTENT_PROCESSING_DAILY_TOKENS` | 100000 | 系统处理独立的滚动 24 小时预留额度 |
| `CONTENT_PROCESSING_RATE_PER_MINUTE` | 3 | 最近一分钟模型请求上限 |
| `CONTENT_PROCESSING_MAX_ATTEMPTS` | 3 | 每个任务最多模型尝试次数 |
| `CONTENT_PROCESSING_MAX_OUTPUT_TOKENS` | 4096 | 单次输出上限（推理模型含推理预算） |
| `CONTENT_PROCESSING_MAX_CHARS` | 40000 | 原文字符上限，超限失败，不静默截断 |

数据库执行租约令显式处理串行运行；忙时返回 `processor_busy`。进程中断后租约在模型超时加 30 秒后过期，可重跑同一任务；过期执行的迟到结果不能提交。此处是小规模手动处理入口，不是 #111 的多信源队列/持续 worker。无法保证上游模型在本地超时后立即停止计费，失败请求仍保留预留量。

### 验证与迁移

`uv run --locked pytest tests/test_content_processing.py tests/test_migrations.py tests/test_merge_migrations.py` 验证候选校验、幂等、重试、预算、租约、人工发布及迁移。模型替身测试不代表真实模型效果；真实联调需要上述配置及原文核对。

迁移 `0009_information_processing` 只新增任务、尝试和执行租约三张表，不改现有聊天/信息表。在可丢弃开发库回退到 `0008_merge_history_favorites` 会删除处理记录及审核依据，但已发布信息仍保留；有已发布记录时应先备份任务表，不在共享库直接回退。迁移 `0010_processing_diagnostics` 为尝试表增加可空 JSON 诊断列，回退到 0009 仅丢失诊断快照。正式迁移和部署需要单独授权，API 启动不会运行这些命令。

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
