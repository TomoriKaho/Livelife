# 客户端 API 调用

本目录维护请求和客户端失败处理。服务端契约从[共享 API 入口](../../../docs/api.md)及对应模块说明读取；页面交互由页面模块维护。

## hello 调用与失败处理

[hello.ts](hello.ts) 的 `fetchHello` 发起 `GET /test/hello`，API 基地址由平台适配提供。开发环境变量与联调步骤见[前端 README](../../README.md#api-地址与联调)，内部工具界面见[个人页说明](../pages/more/README.md#演示边界与验证)。

- 请求使用 `Accept: application/json`，客户端 10 秒未完成时中止。
- 仅 HTTP 200 且 JSON 对象中的 `message` 为字符串 `hello world` 时返回成功。
- 网络不可达、超时、非 200、无效 JSON 或字段不符返回可显示的失败原因，页面可重试。加载、按钮禁用和提示文案由调用页面维护。
- 网页预览或 Android 分发配置启用时，核对真实响应的 `X-Livelife-Backend-SHA`；own/fixed 必须与配置 SHA 一致，staging 可随 main 更新。Android 调用前另核对安装包状态；配置或状态无效时停止测试，不回退 localhost。

客户端校验失败不新增服务端错误码。自动行为测试与运行条件见[前端检查](../../README.md#构建预览与检查)，真实请求及断网重试按[测试入口](../../../docs/testing.md#网页与接口)验收。

## 新增业务请求

按已确认的模块契约实现请求和类型，复用平台地址配置；后端未完成时明确标识 Mock。接口变化同步受影响的调用方、错误处理和测试，不将部署私钥或其他服务端秘密打包进客户端。
