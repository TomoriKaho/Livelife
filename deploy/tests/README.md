# 部署工具测试

自动回归使用本机临时目录、测试进程和独立注册表。真实服务器验收须区分共享环境与初始化窗口；结果和未测项记录在 PR/Actions。业务后端检查见[后端 README](../../backend/README.md)，团队验收流程见[测试入口](../../docs/testing.md)。

## 后端部署工具检查

业务后端的检查见[后端 README](../../backend/README.md)。部署工具可独立检查，从仓库根目录执行：

```bash
python3 -m venv deploy/.venv
deploy/.venv/bin/python -m pip install supervisor==4.3.0 ruff==0.11.13
deploy/.venv/bin/python -m unittest discover -s deploy/tests -v
deploy/.venv/bin/ruff check deploy
```

Python 3.12，控制工具使用标准库和固定版本 Supervisor；验证场景见[测试说明](#回归范围)。

## 回归范围

按修改范围选取相关回归；安装依赖和完整检查命令见上节。

### 部署控制的 SSH 复用回归

从仓库根目录先运行 `deploy/.venv/bin/python -m unittest discover -s deploy/tests -p test_ssh_transport.py -v`，再运行本节的完整检查。Unix socket、Supervisor 和 Nginx 的相关集成测试需要对应操作系统与依赖，跳过须明确记录。

重点验证冷启动只建立一个主连接，多个独立调用者并发复用；主连接空闲退出或失效后恢复；凭证/known_hosts 更换后新建连接；私有目录、socket 和锁不可被其他账号访问，异常文件不被删除。临时认证握手拒绝最多重试四次，认证失败/主机公钥变化立即失败。已发送部署操作后响应丢失时不得自动重放，以免将未确认的提交误当未执行。

实际测试服验证使用只读的 `port_available` 或已存在任务的 `build_status` 查询，记录共享主连接 PID和独立进程并发结果。验证主连接恢复时只关闭确认没有在途请求的项目控制 socket，不能重启 SSH 服务或停止后端；验收步骤及维护命令见[课程机 SSH 控制连接复用](../BUILDING.md#课程机-ssh-控制连接复用)。验证 HTTPS staging hello 仍正常，再重跑原先失败的工作流，以真实检查和产物结果确认恢复。

### RPC 输入与网关

`test_rpc_input.py` 覆盖 SSH JSON 输入边界：使用真实子进程管道，故意保持写端打开，确认收到完整 JSON 后返回；另外验证嵌套、转义、Unicode 跨块、旧格式/换行格式兼容、大小限制及非法输入。实际服务器验证也仅用受限 SSH 的 snapshot 操作，保持 stdin 打开，不用部署请求代替只读检查。

公开测试入口有独立 Nginx 集成测试 `test_access_nginx.py`：使用临时目录、自签测试证书、随机回环端口和模拟上游，验证无需预览凭证的 API/静态资源访问、旧 key 入口 404、遗留凭证剥离，以及业务认证透传和业务 401 原样返回。CI 安装 Nginx 后运行；本地缺少 Linux Nginx/OpenSSL 时明确 skip，在服务器独立临时网关验证，不修改共享后端。

### 后端与网页环境回归

工具不依赖业务后端即可检查引用与环境管理。先按[部署工具检查](#后端部署工具检查)安装依赖并运行完整测试。Supervisor 集成测试需要本地 Unix socket 权限；没有安装 Supervisor 时该项明确 skip，不能当成通过。

完整测试同时覆盖网页环境：双分支及 PR 别名、固定配对、前后端完成顺序、后端-only 复用 main、分支选择迁移、到期/关闭/重开、旧任务晚到、配额、非法产物、候选持久引用及真实 SIGKILL 后恢复。前端执行 `node --test scripts/*.test.mjs`，验证配置校验、加载失败和旧 HTML/新配置不匹配；原有地图与页面行为测试一起运行。测试的 Node 条件见[前端 README](../../frontend/README.md#运行环境与安装)。

实际 HTTPS 网页还须检查无需 key 直接访问、缓存与 gzip、刷新/哈希路由、2D/3D 地图、字体/图片/许可证，以及 hello 响应的后端 SHA。部署启用情况和剩余验收以 [启用证据](../../docs/deployment.md#当前实施状态) 为准。另一名成员在 PR 记录版本、步骤和结果，AI 自查不替代正式评审。

自动测试覆盖：

- main 与两个预览独立分配端口；两个管理进程同时部署不分配重复端口。
- 后端 PR 更新后，跨 PR 前端继续连接原 SHA；释放后端 PR 后旧 SHA 仍被前端保留。
- main 永不被释放；普通前端默认连接共享 main。
- 候选后端/网关失败保留上一部署；旧构建不能覆盖新部署或关闭记录。
- 最后引用释放后延迟回收、分支租约到期、重复释放幂等。
- 课程机清理失败保留待清理端口，后续重试；实例重新创建需先完成原清理。
- 拒绝非法 owner/SHA、tar 路径穿越、符号链接及非后端文件；控制 job 不执行 artifact 脚本。
- 实际 Supervisor 子进程被终止后自动重启，重复移除不会处理其他进程。
- 启动候选之前，从另一数据库连接确认清理预约已提交；成功部署后预约与引用一起转换为有效实例。
- 对真实控制子进程注入 SIGKILL，分别在候选启动后和路由发布后、数据库最终提交前终止：旧 main 引用保留，候选端口不会被复用，恢复和清理后候选进程退出，原 main 进程继续运行。
- 验收与 main 部署交错执行时，真实部署锁覆盖检查、测试、清理和路由恢复；正常或失败的验收结束后，排队的 main 部署路由保留。

### 一次性服务器验收脚本

`deploy/smoke-servers.py` 使用独立测试注册表，但共享项目网关，因此只允许在真实注册表没有实例和待清理预约时运行。它从空表检查之前到全部清理、路由恢复之后一直持有真实部署锁；测试期间其他部署和恢复任务会等待。维护者应在无共享后端的初始化窗口运行，预留足够的工作流等待时间；共享后端已经存在时使用独立测试网关。

维护者先在公网机准备一个 JSON 文件，包含三个不同 SHA 的后端包记录。每项形如 `{"sha":"完整40位GitSHA","bundle":"/绝对路径/backend.tgz"}`，包需包含构建导出的运行依赖与 Linux wheel，然后执行：

```bash
sudo -u livelife /opt/livelife/control-venv/bin/python \
  /opt/livelife/control/smoke-servers.py /绝对路径/three-backends.json
```

网关使用现有 HTTPS，测试请求不发送预览凭证。脚本退出时只清理测试注册表登记的实例和候选，并在仍持有真实部署锁时恢复真实注册表的路由；清理失败保留测试状态用于排查。不要绕过锁或手动清空共享路由。

两项故障回归可以独立运行：

```bash
deploy/.venv/bin/python -m unittest discover -s deploy/tests -p test_interrupted_deploy.py -v
deploy/.venv/bin/python -m unittest discover -s deploy/tests -p test_smoke.py -v
```

前者需要 Supervisor 和本地 Unix socket 权限，在本机临时目录创建并清理测试子进程；后者验证文件锁和路由交错，不连接服务器。

正式后端就绪后的服务器验收：

1. 配置 HTTPS、密钥及 GitHub Variables/Secrets，部署 main 和两个不同 SHA 的后端 PR。记录完整 SHA、端口和真实 hello 响应。
2. 无预览凭证直接请求 hello 应返回 HTTP 200 和约定 JSON；检查 X-Livelife-Backend-SHA 与 PR 记录相同。业务鉴权接入后另验证业务接口的未登录与越权响应。
3. 在另一个前端 PR 建立固定绑定，更新目标后端 PR，确认两个固定 URL 分别返回正确版本；用响应头区分，不改变 hello JSON。
4. 关闭后端 PR，确认其旧版本仍被前端引用；关闭前端 PR，经过清理宽限期确认实例、路由和隧道释放。不要为了测试缩短共享配置，使用独立测试注册表。
5. 制造候选启动失败、项目隧道中断、课程机暂时不可达，分别验证回滚、自动恢复和清理重试。
6. reopened 后恢复或重新部署当前提交；检查 PR 说明、Summary 与实际服务一致。
7. main 检查通过后验证共享入口更新；失败时版本保持原样。

## 构建队列回归

维护者验证应覆盖：两个全项目槽位及第三个任务排队；push/PR 同 SHA 去重；旧排队提交替换；构建失败/worker 重启；日志分页；SHA/模块不匹配拒绝；源码路径和静态包链接拒绝；沙箱无法读取 ~/.ssh、控制数据库或部署凭证；原成功路由、固定绑定与回滚引用保持。新路径安装和完整 GitHub 链路以[实施状态](../../docs/deployment.md#当前实施状态)为准。
