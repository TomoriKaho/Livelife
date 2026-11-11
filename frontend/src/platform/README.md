# 平台能力适配

此目录放网页与 Capacitor 原生包共用的能力适配；页面只调用其公开函数，不直接处理原生插件或平台权限差异。

## 前台定位

[location.ts](location.ts) 提供按需的 `getCurrentLocation()` 和持续的 `watchCurrentLocation()`。后者只负责归一化平台回调，并返回停止函数；不保存任何位置。[location-tracker.ts](location-tracker.ts) 在 `App.vue` 挂载时建立全应用唯一的前台监听，并暴露响应式的最近位置 `currentLocation` 与状态 `locationTrackingState`。因此路由切换（包括离开地图）不会中断监听；根应用卸载时会清理监听。

- 成功结果含纬度、经度、精度、时间戳，以及平台提供时的航向；调用方负责把经纬度转为各自需要的坐标或文案。地图默认请求精确位置；Android 持续监听目标间隔及最短回调间隔均为 1 秒，但系统可为电量或信号质量合并回调。
- 错误为 `unsupported`、`permission-denied`、`unavailable` 或 `timeout`；不向页面透传底层异常信息。
- 已授权时会以时间戳更新内存中的最近位置：迟到的缓存样本不能覆盖更新的样本；已有有效位置后出现单次 `timeout` 或 `unavailable` 时保留“已定位”状态和标记，权限拒绝与不支持仍照常提示。最近位置仅保存在内存中。地图附近查询把位置、精度和时间戳发送到配置的后端，定位模块自身负责采集。该能力不是后台定位：浏览器或原生系统在应用不可见时的行为由平台决定。

网页的一次获取与持续监听分别使用浏览器原生 `navigator.geolocation.getCurrentPosition()`、`watchPosition()`，首次监听会按浏览器规则请求位置授权。Capacitor 原生容器使用 `@capacitor/geolocation` 的同名监听及清理接口；Android 会请求精确位置，用户仍可在系统弹窗中选择粗略位置，此时精度以系统结果为准。定位按钮会先用已有的有效监听位置立即居中并恢复固定视野，再请求一条新位置；若尚无有效位置，则在下一条有效监听结果到来时居中。iOS 工程尚未创建，接入时必须在 `Info.plist` 增加“使用期间位置”用途说明。

坐标契约：平台定位和离线 OSM 地图都使用 **WGS-84**，页面不会自动把位置改为 GCJ-02。以博雅塔为例，WGS-84 测试坐标是纬度 `39.992637`、经度 `116.305783`；常见 GCJ-02 坐标 `39.993923, 116.311832` 与其相距约 500 米，不能直接用于模拟器或定位测试。

自动测试：`node --test scripts/location.test.mjs`。网页手动验证可在 Chrome DevTools 的 **Sensors** 设置模拟坐标：从任一非地图页首次进入应用时确认授权请求，修改模拟坐标后再进入地图，检查蓝点与精度圈采用最新位置；停留在地图时再次修改坐标，蓝点应更新且不会抢走用户手动调整的视角，点击定位按钮才重新居中。另验证拒绝、超时或不可用提示。Android 持续监听仍须在真实设备上验收。

## 设备朝向

[device-heading.ts](device-heading.ts) 是地图朝向标的唯一平台入口。网页进入地图即优先启动 `AbsoluteOrientationSensor`（60Hz、`screen` 参考系），它会主动读取已有的当前姿态；不支持、未授权或被策略阻止时回退到 `deviceorientationabsolute` / `deviceorientation`。各网页读数以 `requestAnimationFrame` 合并同一帧中的更新，细微转向不会被阈值过滤。Android 通过本地 `DeviceHeadingPlugin`（`android/app/src/main/java/io/github/tomorikaho/livelife/dev/DeviceHeadingPlugin.java`）读取 `TYPE_ROTATION_VECTOR`，按当前显示旋转重映射后发送 0–360° 的磁北航向。传感器不可用或原生桥加载失败时，自动回退到 WebView 事件；在首个航向读数到来前，地图方向标默认指向北方，之后实时替换为传感器读数。

插件仅在地图页存在时订阅，应用暂停时注销传感器、恢复后重新订阅，离开地图或销毁 Activity 时清理。它不请求额外运行时权限，也不保存或上传传感器数据。Android 验收时，先授予位置权限，在 2D 和 3D 地图缓慢旋转设备，确认标记连续转动；再旋转屏幕、切换后台和前台、离开再进入地图，确认朝向保持可用且没有重复监听。
