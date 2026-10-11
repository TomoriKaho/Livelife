# 部署工具维护

本目录维护测试环境的构建、网关、引用和恢复工具。成员获取预览、配对后端和查看启用证据，从[部署入口](../docs/deployment.md)开始；正式发布尚无自动工作流。

## 按维护范围阅读

| 范围 | 主要说明 |
| --- | --- |
| 初始化、服务器、后端生命周期与故障 | 本文 |
| 请求字段与控制协议 | [控制接口](CONTROL_API.md) |
| 课程机构建、队列和 SSH 传输 | [构建维护](BUILDING.md) |
| 网页配置、资源发布和回滚 | [网页预览](WEB_PREVIEW.md) |
| Android 工具、签名与分发 | [Android 分发](ANDROID.md) |
| 自动回归与服务器验收 | [部署工具测试](tests/README.md) |

## 服务器、目录和端口

| 位置 | SSH | 项目目录 | 监听 |
| --- | --- | --- | --- |
| 课程机 | `group5@8.130.213.80:1021` | `/home/group5/livelife` | 后端 `127.0.0.1:18000–18063` |
| 公网机维护者 | `ubuntu@192.144.253.40:22` | `/opt/livelife` | HTTPS `443`；隧道 `127.0.0.1:28000–28063` |
| Actions 专用用户 | `livelife@192.144.253.40:22` | 仅允许 JSON 管理命令 | 无通用远程 shell |

对应端口相差 10000。分配前检查数据库、待清理记录和两侧实际监听；占用则选择其他槽位，池满明确报错。不能直接把分支名称拼接成目录、端口或 shell 命令。

课程机使用项目专属 Supervisor 和 Unix socket，普通用户即可安装；每个后端自动重启，并处理整组子进程。公网机的项目 Supervisor 管理 SSH 隧道，SSH keepalive 与自动重启负责恢复连接。`livelife-recover.timer` 每五分钟检查登记实例，恢复课程环境重启后的进程；源目录丢失时报错，需重新部署原 SHA。

公网机使用独立 `livelife-gateway.service` 运行 Nginx。SQLite 登记表在 `/opt/livelife/state/registry.sqlite3`，控制程序在 root 拥有的 `/opt/livelife/control/`。分支产物仅在课程机运行，不在公网机执行。

## 维护者初始化教程

以下使用已审查代码。先确认项目目录、账户、端口和前置条件，课程机不需要 Docker/sudo。

### 1. 安装课程机控制程序

```bash
scp -P 1021 -r deploy group5@8.130.213.80:~/livelife-bootstrap
ssh -p 1021 group5@8.130.213.80
bash ~/livelife-bootstrap/bootstrap-course.sh
```

创建专用 control-venv、安装 `supervisor==4.3.0`、复制工具，不启动业务后端。需要 Python 3.12、venv/ensurepip 与依赖下载源；失败按实际错误修复。

### 2. 公网机控制程序与密钥

```bash
scp -r deploy ubuntu@192.144.253.40:~/livelife-bootstrap
ssh ubuntu@192.144.253.40
sudo bash ~/livelife-bootstrap/bootstrap-public.sh
```

脚本创建 livelife 用户、控制虚拟环境、项目 Nginx 和 systemd 配置，尚不启用服务。核对 `/opt/livelife/config.json` 的 IP、SSH 端口、用户名、密钥与 known_hosts 路径。root 拥有控制程序和 root 执行的证书脚本，部署账户仅写环境状态、隧道日志和路由数据。

公网机需已有 Python 3.12、venv 模块、Nginx、curl、tar 与 openssl；Ubuntu 缺少 venv 时由维护者安装 `python3.12-venv`。初始化脚本不自行安装宿主机软件。

使用 `ssh-keygen -t ed25519 -N '' -f <私有路径>` 生成两把独立密钥：Actions → 公网机、公网机 → 课程机。私钥不进入 Git。

公网机 livelife 的 authorized_keys 写入第一把公钥：

```text
restrict,command="/opt/livelife/control-venv/bin/python /opt/livelife/control/public-entry.py" ssh-ed25519 <第一把公钥内容>
```

第二把私钥放 `/opt/livelife/credentials/course_ed25519`，livelife 拥有、权限 600。课程机 group5 的 authorized_keys 追加第二把公钥，限制 forced command 以及 64 个许可端口，实际写入时不能使用省略号：

```text
restrict,port-forwarding,command="/home/group5/livelife/control-venv/bin/python /home/group5/livelife/control/course-entry.py",permitopen="127.0.0.1:18000",...,permitopen="127.0.0.1:18063" ssh-ed25519 <第二把公钥内容>
```

RPC 和 `ssh -N -L` 共用这把受限密钥，不提供通用 shell。authorized_keys 权限 600，.ssh 目录 700。保留账号原有公钥，仅追加项目的独立条目。

ssh-keyscan 仅用于收集公钥，需在已可信 SSH 连接上核对指纹后保存 known_hosts。已核对的 ED25519 指纹为：课程机 `SHA256:2jokCDS9x7MV29JGEn3iEi3oiZzQJpqOLL9VHfAUNGA`；公网机 `SHA256:D901HLly2xmG468zDPIzrDIdpO1XGL8H6kNu7kTtNbI`。变化需确认来源。所有自动 SSH 使用 StrictHostKeyChecking=yes。

### 3. 无域名 IP HTTPS

安全组放通公网 TCP 443。使用 Lego TLS-ALPN-01 验证，无需配置 HTTP 80 的挑战路由：

```bash
sudo bash ~/livelife-bootstrap/install-lego.sh
sudoedit /opt/livelife/acme.env
```

acme.env 由 root 拥有，权限 600，填写：

```bash
LIVELIFE_IP=192.144.253.40
ACME_EMAIL=维护者指定的联系邮箱
```

先 `sudo /opt/livelife/control/renew-ip.sh staging` 验证挑战可达，测试证书放独立 acme-staging 目录；通过后 `sudo /opt/livelife/control/renew-ip.sh initial` 申请可信 IP 证书。工具固定 Lego 5.5.2，并核对官方 release checksum。

证书使用 shortlived profile，约六天有效。daily timer 每天检查，剩余三天以内续期。签发/续期短暂停止项目 gateway 让出 443，结束恢复；后端与隧道继续运行。失败保留原证书并恢复网关，维护者查看日志及时修复。

参考：[IP 证书说明](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability)、[Lego 官方文档](https://go-acme.github.io/lego/)。

### 4. 启动公开测试入口

网页预览、运行时配置、静态资源和当前 hello API 可直接通过 HTTPS 访问，无需用户名、密码或预览 key。后续业务接口由后端实现登录及逐请求权限检查；取消网关门禁不表示业务鉴权已经实现。

维护者初始化时直接使用本仓库 `deploy/nginx.conf`。旧部署迁移时，先备份 `/opt/livelife/gateway/nginx.conf` 及本次更新的控制工具，在 `/opt/livelife/state/manager.lock` 部署锁内更新项目配置，执行检查并仅重载项目网关：

```bash
sudo /usr/sbin/nginx -p /opt/livelife/gateway/ -c /opt/livelife/gateway/nginx.conf -t
sudo systemctl reload livelife-gateway.service
```

配置检查或重载失败时恢复备份并重新检查、重载，不把配置写入等同于访问方式已生效。更新控制工具时同时同步 `livelife/runtime.py`，其网页健康检查不再读取 key 文件。

旧 `credentials/preview-key.txt`、`preview-key.conf` 和 `gateway/access.html` 不再被当前配置加载，无需读取或分发；迁移不依赖删除这些遗留文件。旧浏览器 Cookie 不授予任何权限，网关会剥离 `livelife_preview` Cookie 及 `X-Livelife-Preview-Key` 头；重复旧 Cookie 时不向业务后端转发该 Cookie 头。正常业务 `Authorization` 和业务 Cookie 仍保留，业务 401 不会被网关替换成 key 输入页。旧 `/__livelife/access` 和输入页入口返回 404。

可直接验证：

```bash
curl --fail https://192.144.253.40/staging/runtime-config.json
curl --fail -i https://192.144.253.40/api/staging/test/hello
```

hello 应为 HTTP 200、`{"message":"hello world"}`，并返回真实后端 SHA。尚未发布或已释放的预览地址应为 404。部署管理仍只经受限 SSH JSON 接口进行，取消网页访问门禁不开放公网部署、绑定或删除操作。

```bash
sudo systemctl enable --now livelife-gateway.service
sudo systemctl enable --now livelife-recover.timer livelife-renew-ip.timer
sudo systemctl status livelife-gateway.service --no-pager
```

没有后端路由时 API 返回 404 是正常状态。先通过专用 SSH key 发送 `{"op":"snapshot"}` 验证控制平面，再部署真实后端验证 API。网页静态路由使用同一 HTTPS 入口。

### 5. 配置 GitHub 并启用

**Settings → Secrets and variables → Actions**：

| 名称 | 类型 | 内容 |
| --- | --- | --- |
| LIVELIFE_DEPLOY_SSH_KEY | Secret | 第一把专用部署私钥 |
| LIVELIFE_PUBLIC_KNOWN_HOSTS | Secret | 核对指纹后的公网机 known_hosts 行 |
| LIVELIFE_SSH_TARGET | Variable | `livelife@192.144.253.40` |
| LIVELIFE_PUBLIC_BASE_URL | Variable | `https://192.144.253.40`，与服务器一致 |
| LIVELIFE_BACKEND_ENABLED | Variable | 后端自动部署开关，设 `true` 启用 |
| LIVELIFE_FRONTEND_ENABLED | Variable | 网页自动部署开关，启用见[网页维护](WEB_PREVIEW.md#维护者启用顺序) |
| LIVELIFE_ANDROID_ENABLED | Variable | Android 自动分发开关，启用见[分发维护](ANDROID.md#android-启用和排查) |

第二把私钥不进入 GitHub。请求 job 无部署秘密、无 checkout、无构建；特权控制程序只从 main 的 deploy/ 检出。课程机在命名空间沙箱中执行检查与构建，产物作为数据由公网机校验发布。fork 不提交到课程机；课程机仅持测试权限，不接正式数据库/凭证。venv 是依赖隔离，构建的文件/进程隔离由 bubblewrap 提供。

控制工作流的 GitHub token 权限由 `.github/workflows/backend-control.yml` 明确声明：

```yaml
permissions:
  contents: read
  actions: read
  pull-requests: write
  statuses: write
```

前两项用于读取 main 控制代码和可信工作流元数据；`statuses: write` 将课程机真实结果写为当前 SHA 的 Frontend checks / Backend checks，不能用请求 job 的绿色状态代替；`pull-requests: write` 用于创建或更新 PR 的预览、绑定与关闭说明。评论虽然调用 `/issues/{PR编号}/comments`，目标仍是 PR，不能只授予 `issues: write` 并保留 PR 只读。此流程不需要普通 Issue 写权限、代码写权限或个人访问令牌。仓库的全局 Workflow permissions 可保持只读，工作流按需声明上述权限；自动创建或批准 PR 的开关不需要开启。

开关的当前启用证据统一见[部署入口](../docs/deployment.md#当前实施状态)。三个 enabled 均未开启时控制 job 跳过，仅记录构建请求，不执行课程机检查；请求成功不能表示测试通过。新安装时先使工作流进入 main，再验证 Runner → 公网机 → 课程机的真实连接。

## 后端启动与兼容产物

#24 提供 Python 3.12 工程、`backend/app/main.py` 中的 `app`、`backend/pyproject.toml` 与 `backend/uv.lock`，以及约定的 `GET /test/hello`。部署启动为 `python -m uvicorn app.main:app`，工作目录为 release/backend。不为基础设施改动业务 JSON。

以下为旧 GitHub Runner 打包模式，保留兼容旧产物，不是新请求工作流的执行路径。新路径见[课程机统一构建与队列](BUILDING.md#课程机统一构建与队列)。旧模式使用 Python 3.12 与固定 `uv==0.12.23`：

1. `uv sync --locked` 检查锁文件并安装检查环境；运行实际后端的 pytest、ruff 和格式检查。
2. 启动候选后端，真实请求 hello；失败则不部署。
3. `uv export --locked --no-dev --no-emit-project` 导出运行依赖，在 Runner 上下载 Linux x86_64/Python 3.12 wheel。
4. 打包 Git 中该 SHA 的 backend 源码、生成的 `.deploy-requirements.txt` 和 `.wheels/`，不包含本地虚拟环境或未提交文件。部署产物只上传 manifest.json 与 backend.tgz。
5. 课程机创建版本独立 venv，用 pip 的 `--no-index --find-links` 离线安装；无需在每次预览时访问 PyPI。安装记录在该版本的 `install.log`。

构建和课程机须保持上述系统/架构/运行时兼容。运行依赖必须有 wheel，压缩包上限 20 MiB，文件内容上限 100 MiB、10000 个条目；超限或依赖需要源码编译时明确失败，需要专项调整，不静默在线安装。简化的 requirements.txt 工程仍可用于独立基础设施验证；正式后端以 uv.lock 为准。

uv 参数参考：[锁文件与导出教程](https://docs.astral.sh/uv/concepts/projects/sync/)。

## 保留、关闭、重开和回收

每个 owner 只有一条保留记录，重复调用不累加计数：

- `main`：永不允许释放，版本随成功部署更新。
- `pr:40`：后端 PR 打开时保留其最新成功部署。
- `frontend:41`：绑定保留固定版本，直到释放或前端 PR 关闭。
- `branch:<分支摘要>`：未关联 PR 的部署租约，72 小时到期，重新部署可续期。

浏览器打开与否、人数和请求次数不影响保留。PR 关闭释放它的后端记录和前端绑定，其他前端仍引用的版本继续运行。分支删除也撤销其网页入口。每十五分钟核对 PR 状态、回收到期租约，弥补任务队列遗漏或 webhook 清理失败。

最后一个引用释放后等待一小时再清理。PR reopened 会检查并部署当前 SHA；实例还在则复用/恢复，已清理则重新安装。固定引用不能静默回退到 staging。

管理命令在服务器持有文件锁，端口与记录变更串行；不使用会丢弃较早 pending 任务的全局 Actions concurrency 队列。SQLite 保存工作流 generation。关闭留下墓碑，较早构建延迟完成不能复活已关闭 PR。清理先撤路由并保存待清理记录，再停止进程；课程机不可达时保留端口占用并重试，不给新版本分配未释放端口。

新候选后端启动前，先把 `be-SHA` 与端口写入 retirements 待清理表并提交，随后才启动进程。健康检查和路由发布成功后，在同一最终事务中登记实例、更新引用并删除这条预约；启动中的候选不会被查询为 ready。控制进程被强制终止时，未完成候选仍有持久记录，`recover` 从已提交实例恢复路由，`collect` 停止候选并释放预约；清理失败继续保留端口。已有共享实例的恢复不会建立候选清理预约。

## 故障、回滚与验证记录

- 后端失败：查看课程机 `livelife/supervisor/be-<SHA>.log`；候选不发布，保留旧成功版本。
- 依赖失败：查看 Actions 返回的安装日志末尾，或课程机 `livelife/releases/be-<SHA>/install.log`，核对导出清单、wheel 和 Python/CPU 架构；候选失败后会清理该目录。
- 隧道失败：查看公网机 `livelife/tunnels/be-<SHA>.log`，核对指纹、密钥限制、端口和课程机状态；手动 recover，不静默换后端。
- 网关失败：`journalctl -u livelife-gateway.service` 与 gateway/logs；更新先 nginx -t，失败恢复原路由。
- 清理失败：数据库保留待清理占用，网络恢复后 collect；不直接删数据库或按端口杀未知进程。
- 证书失败：`journalctl -u livelife-renew-ip.service`，修复 443/ACME 条件后手动 renew。
- 业务回滚：重新部署确认的旧 SHA。后续数据库引入时另行确认隔离、迁移和恢复策略。

### PR 评论返回 403 时如何处理

1. 打开失败的 **Preview environments** 运行，查看失败步骤。如果 traceback 位于 `GitHub.comment` 的 POST/PATCH 并显示 `HTTP Error 403`，被拒绝的是 GitHub 评论接口；这不能说明腾讯云拦截了 SSH。若失败的是 SSH 超时或公钥认证，则按隧道、网络或密钥问题排查。
2. 展开 **Set up job → GITHUB_TOKEN Permissions**，确认实际权限包含 `PullRequests: write`。在上述控制工作流中声明权限，通过 PR 合入 main；不要仅为评论把仓库所有工作流改成写权限或公开部署私钥。
3. 权限修复合并后，使用新事件验证。合并修复 PR 产生的 closed 事件应成功释放它的引用并创建或更新关闭说明；也可在后续打开的同仓库 PR 上验证预览/绑定说明。直接 Re-run 原来的失败任务仍使用原事件提交的工作流权限，不能用它验证新的 YAML 权限。
4. 检查新运行的真实权限、评论及 Actions 结果。若仍为 403，核对目标 PR 是否锁定、实际 token 权限与仓库/组织策略，保留运行链接；不把用户个人 token 的成功当成 `GITHUB_TOKEN` 已修复。

参考：[GitHub 工作流权限](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)、[PR/Issue 评论接口](https://docs.github.com/en/rest/issues/comments#create-an-issue-comment)、[重跑工作流](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs)。
