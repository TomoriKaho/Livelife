# 客户端 API 调用

本目录维护请求和客户端失败处理。服务端契约从[共享 API 入口](../../../docs/api.md)及对应模块说明读取；页面交互由页面模块维护。当前真实业务请求包括 hello 与 Agent 对话。

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
- 请求沿用 10 秒超时。`401` 提示重新登录并清除本地令牌，`503` 提示数据库未配置，`400`/`422` 提示内容不符合要求，其它状态与网络异常返回可显示原因。
- `PATCH` 只提交出现的字段，兴趣整体替换；保存成功后用响应回填昵称、简介和兴趣顺序。

## Agent 对话

[agent.ts](agent.ts) 使用 `sessionStorage` 保存 24 小时匿名会话令牌，通过 Bearer 认证读取历史并 POST 发送问题。`agent-stream.mjs` 解析 SSE 的开始、来源、文本增量、用量、完成和错误事件；失败时保留用户问题供重试。附件不会加入请求。服务端字段和错误语义见[Agent API](../../../backend/app/api/agent/API.md)。

## 新增业务请求

按已确认的模块契约实现请求和类型，复用平台地址配置；后端未完成时明确标识 Mock。接口变化同步受影响的调用方、错误处理和测试，不将部署私钥或其他服务端秘密打包进客户端。

## 账户认证

[`auth.ts`](auth.ts) 调用[账户与认证 API](../../../backend/app/api/accounts/API.md)，实现校园邮箱验证码、注册、登录、会话恢复和退出。记住登录时令牌写入 `localStorage`；普通登录使用 `sessionStorage`，退出时请求服务端撤销并清理两种存储。前端仅持有 Bearer 令牌，不保存密码或邮箱验证码。通过 HTTPS 连接非本机服务；不要将令牌或其他秘密写入日志。

临时联调时，在登录页将邮箱和密码均留空可进入后端内置测试账号；这仍是一次真实登录请求，页面不会伪造身份。只填一项时表单要求补齐；注册保持必填和验证码校验。测试入口的关闭配置、共享用户及会话限制见[账户契约](../../../backend/app/api/accounts/API.md#post-authlogin)。
