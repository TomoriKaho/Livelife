# 账户与认证 API

基址使用后端 API 基址，不含部署前缀。账户使用邮箱加密码；注册仅接受 `@pku.edu.cn` 与 `@stu.pku.edu.cn`，邮箱统一去除首尾空格并转小写。成功及错误响应遵循 FastAPI 的 JSON 结构，不增加统一响应包裹。

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

## 受保护接口

`GET /auth/me` 返回 `{ "id": "<uuid>", "email": "..." }`。`POST /auth/logout` 撤销当前会话并返回 `204`。两者及后续受保护接口使用 `Authorization: Bearer <access_token>`；令牌只存储 SHA-256 摘要。缺失、撤销或过期会话返回 `401` 和 `WWW-Authenticate: Bearer`。无数据库时账号接口返回 `503`。现有健康检查及 hello 接口仍公开。

令牌是 bearer 凭证，客户端必须通过 HTTPS 发送。当前前端按“记住登录”选择 localStorage，否则 sessionStorage；退出时清除本地令牌并在服务端撤销。XSS 风险和后续更安全的原生凭证存储可作为后续专项改进。
