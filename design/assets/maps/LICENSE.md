# 燕园本地地图数据

© OpenStreetMap contributors。地图数据以 Open Database License（ODbL）1.0 提供。

- 版权及署名说明：https://www.openstreetmap.org/copyright
- 完整许可证：https://opendatacommons.org/licenses/odbl/1-0/
- 数据来源：OpenStreetMap，通过 Overpass API 获取。
- `yanyuan-osm.json`：原始查询结果，保留完整下载快照。
- `source.json`：查询语句、下载时间、接口地址与数据时间。
- `campus.json`：基于上述快照的燕园裁切及米制坐标转换结果，同样按 ODbL 1.0 提供。

所有文件随仓库保留，并在生产构建中放入 `assets/maps/`。界面持续显示 OpenStreetMap 署名。
建筑轮廓、道路和水面来自 OSM。示意楼层、内部教室、活动及示例定位由本项目自行编写，不是 OSM 室内地图或实时校园信息。
