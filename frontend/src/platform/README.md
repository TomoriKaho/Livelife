# 平台能力适配

此目录放网页与 Capacitor 原生包共用的能力适配；页面只调用其公开函数，不直接处理原生插件或平台权限差异。

## 前台定位

[location.ts](location.ts) 提供按需的 `getCurrentLocation()` 和持续的 `watchCurrentLocation()`。后者只负责归一化平台回调，并返回停止函数；不保存任何位置。[location-tracker.ts](location-tracker.ts) 在 `App.vue` 挂载时建立全应用唯一的前台监听，并暴露响应式的最近位置 `currentLocation` 与状态 `locationTrackingState`。因此路由切换（包括离开地图）不会中断监听；根应用卸载时会清理监听。

- 成功结果含纬度、经度、精度、时间戳，以及平台提供时的航向；调用方负责把经纬度转为各自需要的坐标或文案。
- 错误为 `unsupported`、`permission-denied`、`unavailable` 或 `timeout`；不向页面透传底层异常信息。
- 已授权时每次平台位置回调都会替换内存中的最近位置；不缓存、不持久化，也不上传坐标。该能力不是后台定位：浏览器或原生系统在应用不可见时的行为由平台决定。

网页的一次获取与持续监听分别使用浏览器原生 `navigator.geolocation.getCurrentPosition()`、`watchPosition()`，首次监听会按浏览器规则请求位置授权。Capacitor 原生容器使用 `@capacitor/geolocation` 的同名监听及清理接口；Android 12 及更高版本允许用户只授权粗略位置，函数仍会返回该位置。iOS 工程尚未创建，接入时必须在 `Info.plist` 增加“使用期间位置”用途说明。

自动测试：`node --test scripts/location.test.mjs`。网页手动验证可在 Chrome DevTools 的 **Sensors** 设置模拟坐标：从任一非地图页首次进入应用时确认授权请求，修改模拟坐标后再进入地图，检查蓝点与精度圈采用最新位置；停留在地图时再次修改坐标，蓝点应更新且不会抢走用户手动调整的视角，点击定位按钮才重新居中。另验证拒绝、超时或不可用提示。Android 持续监听的实机验收另行安排。
