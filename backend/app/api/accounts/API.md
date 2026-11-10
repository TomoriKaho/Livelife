# 账户与认证 API

基址使用后端 API 基址，不含部署前缀。账户使用邮箱加密码；注册仅接受 `@pku.edu.cn` 与 `@stu.pku.edu.cn`，邮箱统一去除首尾空格并转小写。当前账号体系仅支持上述校园邮箱注册与登录，用户名登录纳入后续版本，届时另行更新本契约与前端文案。成功及错误响应遵循 FastAPI 的 JSON 结构，不增加统一响应包裹。

## `POST /auth/email-codes`

请求：`{"email":"student@stu.pku.edu.cn"}`。返回 `202` 和通用消息，不区分已注册地址、限流或实际是否发送，降低账户枚举风险。验证码为 6 位数字，10 分钟有效；每地址 60 秒最多申请一次、15 分钟最多 5 次，最多校验 5 次。验证码只保存加盐 PBKDF2 摘要；邮件通过 STARTTLS SMTP 发送（465 端口使用 SMTP SSL）。邮件服务未配置或投递失败返回 `503`，响应不包含验证码。

## `POST /auth/register`

请求：`{"email":"student@stu.pku.edu.cn","code":"123456","password":"at-least-10-chars"}`。密码长度 10–128 字符。验证码成功使用后创建账号并自动签发普通会话，返回 `201`：

```json
{"access_token":"<opaque-token>","token_type":"bearer","expires_in":86400,"user":{"id":"<uuid>","email":"student@stu.pku.edu.cn"}}
```

已注册邮箱返回 `409`；验证码缺失、错误、过期或超出尝试次数返回 `400`。密码使用 scrypt 哈希，不返回或记录明文密码。

## `POST /auth/login`

请求：`{"email":"student@stu.pku.edu.cn","password":"...","remember":true}`。成功返回与注册相同的会话结构。普通会话有效 1 天，`remember: true` 有效 30 天。邮箱或密码错误统一返回 `401`。

临时测试入口：`{"email":"","password":"","remember":false}` 会首次创建并复用内置普通用户 `builtin-test@livelife.invalid`，签发同样的真实会话，不要求邮箱验证码或 SMTP。所有空白登录共享该用户 ID，每次签发独立令牌；测试用户没有可用的密码，也不是校园邮箱已验证用户。仅当邮箱去空格后为空且密码为空字符串时生效；只填一项、普通登录失败或注册均不回退到测试账号。

后端 `AUTH_TEST_LOGIN_ENABLED` 默认 `true`；设为 `false` 后空白登录返回 `403`，普通登录继续可用。关闭入口不会撤销已签发的测试会话，已有令牌仍按有效期和退出规则处理。无数据库仍返回 `503`。此入口用于当前临时联调，正式环境应关闭；测试用户是共享身份，不用于私人数据。

## 受保护接口

`GET /auth/me` 返回 `{ "id": "<uuid>", "email": "..." }`。`POST /auth/logout` 撤销当前会话并返回 `204`。两者及后续受保护接口使用 `Authorization: Bearer <access_token>`；令牌只存储 SHA-256 摘要。缺失、撤销或过期会话返回 `401` 和 `WWW-Authenticate: Bearer`。无数据库时账号接口返回 `503`。现有健康检查及 hello 接口仍公开。

令牌是 bearer 凭证，客户端必须通过 HTTPS 发送。当前前端按“记住登录”选择 localStorage，否则 sessionStorage；退出时清除本地令牌并在服务端撤销。XSS 风险和后续更安全的原生凭证存储可作为后续专项改进。

## `DELETE /auth/me`（注销账号）

请求头携带 `Authorization: Bearer <access_token>`，请求体 `{"password":"..."}` 作二次确认。校验通过后在同一事务内删除该账户的会话、个人资料与兴趣标签、该邮箱未使用的验证码以及用户记录，返回 `204`，已签发令牌立即失效。密码错误返回 `400`；缺失、撤销或过期会话返回 `401` 和 `WWW-Authenticate: Bearer`。内置测试账号没有可用密码，不通过此接口注销。`POST /auth/logout` 只撤销当前会话，不删除账户。
