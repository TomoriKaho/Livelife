# 平台能力适配

此目录放网页与 Capacitor 原生包共用的能力适配；页面只调用其公开函数，不直接处理原生插件或平台权限差异。

## 前台定位

[location.ts](location.ts) 提供 `getCurrentLocation()`。地图、日历、推荐或 Agent 在用户明确触发的动作中直接调用它，并按返回的 `status` 显示自身的提示：

- 成功结果只含纬度、经度、精度和时间戳；调用方负责把经纬度转为各自需要的坐标或文案。
- 错误为 `unsupported`、`permission-denied`、`unavailable` 或 `timeout`；不向页面透传底层异常信息。
- 每次调用最多请求一次当前位置和必要权限；不建立位置监听，不缓存、不持久化，也不上传坐标。

网页使用插件的 Web 实现。Android 使用 `@capacitor/geolocation`，并在 `AndroidManifest.xml` 声明前台粗略和精确位置权限；Android 12 及更高版本允许用户只授权粗略位置，函数仍会返回该位置。iOS 工程尚未创建，接入时必须在 `Info.plist` 增加“使用期间位置”用途说明。

自动测试：`node --test scripts/location.test.mjs`。Android 手动验证需在模拟器扩展控制的 **Location** 中设定位置，然后由明确的用户操作调用定位函数，分别记录允许、拒绝、超时/关闭定位服务及粗略位置结果。
