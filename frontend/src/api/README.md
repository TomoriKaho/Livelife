# 客户端 API 调用

本目录维护请求和客户端失败处理。服务端契约从[共享 API 入口](../../../docs/api.md)及对应模块说明读取；页面交互由页面模块维护。当前真实业务请求包括 hello、账户、个人资料、Agent 对话与地图活动查询。

## 地图活动查询

[`map-activities.ts`](map-activities.ts) 每次进入地图页从 [`GET /locations/activities`](../../../backend/app/api/locations/API.md) 分页读取北京时间今天至后天尚未结束的活动，翻页沿用首个响应的 `as_of`。查询超过 10 秒、数据库不可用、响应格式不符或网络失败时向地图页返回可显示错误，不用演示活动补位。请求前核对 Android 安装包状态；测试预览配置启用时核对响应后端 SHA。离开地图时中止请求。设备坐标只用于客户端计算附近建筑，不发送到此接口；地点原文和建筑名称的匹配规则在[地图说明](../pages/map/README.md)维护。

## hello 调用与失败处理

[hello.ts](hello.ts) 的 `fetchHello` 发起 `GET /test/hello`，API 基地址由平台适配提供。开发环境变量与联调步骤见[前端 README](../../README.md#api-地址与联调)，内部工具界面见[个人页说明](../pages/more/README.md#演示边界与验证)。

- 请求使用 `Accept: application/json`，客户端 10 秒未完成时中止。
- 仅 HTTP 200 且 JSON 对象中的 `message` 为字符串 `hello world` 时返回成功。
- 网络不可达、超时、非 200、无效 JSON 或字段不符返回可显示的失败原因，页面可重试。加载、按钮禁用和提示文案由调用页面维护。
- 网页预览或 Android 分发配置启用时，核对真实响应的 `X-Livelife-Backend-SHA`；own/fixed 必须与配置 SHA 一致，staging 可随 main 更新。Android 调用前另核对安装包状态；配置或状态无效时停止测试，不回退 localhost。

客户端校验失败不新增服务端错误码。自动行为测试与运行条件见[前端检查](../../README.md#构建预览与检查)，真实请求及断网重试按[测试入口](../../../docs/testing.md#网页与接口)验收。

## 个人资料请求

[profile.ts](profile.ts) 维护 `/profile/interests`、`/profile/me` 的读取与更新，服务端契约见[个人资料 API](../../../backend/app/api/profile/API.md)。

- 令牌与账户模块共用 `livelife.auth.token`（`[auth.ts](auth.ts)`）：勾选“记住登录”写 `localStorage`，否则写 `sessionStorage`；没有令牌时不发请求，页面按界面预览处理。
- 请求沿用 10 秒超时。`401` 由页面提示重新登录并调用账户模块的 `clearSession()`，同时清除本地令牌与当前用户；`503` 提示数据库未配置，`400`/`422` 提示内容不符合要求，其它状态与网络异常返回可显示原因。
- `PATCH` 只提交出现的字段，兴趣整体替换；保存成功后用响应回填昵称、简介和兴趣顺序。
- 请求前核对 Android 安装包状态；测试配置启用时校验响应的 `X-Livelife-Backend-SHA`，固定版本必须一致，staging 接受有效的更新 SHA。状态或版本失败不回填资料，也不把配置错误当成登录失效。独立 Vite 日历页可执行 `await (await import('/scripts/profile.browser.mjs')).verifyProfileConfiguration()` 验证版本与安装包门禁；网页替身检查不代表 Android 真机验收。

## Agent 对话

[agent.ts](agent.ts) 使用账户 Bearer 令牌认证，并用 `X-Agent-Session` 定位当前用户的短期对话。`sessionStorage` 的 v2 缓存绑定账户 ID 与 API 地址，旧 v1 匿名缓存不再恢复。登出、过期、注销、切换账号及跨标签账户变更时清除缓存并中止活动流；请求返回及 SSE 事件回填前检查身份代次，拒绝上一账号的迟到响应。账户 401 要求重新登录，不自动创建匿名会话。`agent-stream.mjs` 解析 SSE 的开始、来源、文本增量、用量、完成和错误事件；失败时保留用户问题供重试。附件不会加入请求。服务端字段和错误语义见[Agent API](../../../backend/app/api/agent/API.md)。

## 新增业务请求

按已确认的模块契约实现请求和类型，复用平台地址配置；后端未完成时明确标识 Mock。接口变化同步受影响的调用方、错误处理和测试，不将部署私钥或其他服务端秘密打包进客户端。

## 账户认证

[`auth.ts`](auth.ts) 调用[账户与认证 API](../../../backend/app/api/accounts/API.md)，实现校园邮箱验证码、注册、登录、会话恢复和退出。记住登录时令牌写入 `localStorage`；普通登录使用 `sessionStorage`，退出时请求服务端撤销并清理两种存储。前端仅持有 Bearer 令牌，不保存密码或邮箱验证码。通过 HTTPS 连接非本机服务；不要将令牌或其他秘密写入日志。

注销账号只有在服务端确认成功后才清理本地会话；密码错误、服务故障或网络失败均保留令牌和当前用户，供修改密码或重试。独立 Vite 日历测试页的 Console 可执行 `await (await import('/scripts/profile.browser.mjs')).verifyDeletionSession()`，使用虚构响应验证失败保留和成功清理；它与主动退出登录的本地清理策略不同。

登录和注册表单均要求校园邮箱、密码；本地可选测试入口只供接口调试，且没有 Agent 权限，见[账户契约](../../../backend/app/api/accounts/API.md#post-authlogin)。

在独立本地 Vite 测试标签页执行 `await (await import('/scripts/agent-auth.browser.mjs')).verifyAgentAuth()`，验证账户/对话凭证分离、切换账号时拒绝迟到历史、清除缓存、中止 SSE、401 不匿名重试及跨标签变更。使用虚构令牌和响应，不访问真实模型。


## 地图附近活动

[`map-activities.ts`](map-activities.ts) 复用平台地址、Android 状态与后端 SHA 校验，调用标准 `GET /locations/activities`。传递设备经纬度、时间戳、半径、关键词与时间窗口；翻页固定服务端返回的时间边界，校验结构化地点、距离、活动及分页字段，按 ID 去重。十秒超时、旧请求取消、迟到响应与定位失效处理在 [`useNearbyActivities.ts`](../pages/map/useNearbyActivities.ts) 中维护。正式字段见[地图接口](../../../backend/app/api/locations/API.md)，启动步骤见[地图联调](../pages/map/README.md#本地信息系统联调)。
