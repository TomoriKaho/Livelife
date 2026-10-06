# 环境、Actions 与发布教程

## 当前实施状态

frontend/ 和 backend/ 已提供可构建网页及 FastAPI hello 服务。#29 的 main/分支后端构建、课程机部署和公网 HTTPS API 已接入；课程机直接运行 Python，不使用 Docker。网页静态预览在 #27 分支实现，独立开关 `LIVELIFE_FRONTEND_ENABLED` 在合并及初始化前保持关闭。Android/iOS 工程、APK 分发由 #28 及后续任务处理。

网页启用步骤、接口契约与本次验证记录见[网页预览实现与维护](#网页预览实现与维护)。服务器配置完成、手动预览通过和完整 GitHub 事件链路通过是不同状态，不能相互替代。

## 分支与环境

| 来源 | 环境 | 更新规则 |
| --- | --- | --- |
| main 的已检查提交 | staging 共享测试后端 | 成功后切换，入口永久保留 |
| 打开的后端 PR | PR 最新入口与固定 SHA 实例 | 成功部署更新 PR 入口 |
| 尚未创建 PR 的分支 | 有期限的预览实例 | 推送或手动运行检查，保留 72 小时 |
| 前端连接另一后端 PR | 固定 SHA 的后端绑定 | 明确重新绑定才切换 |
| 已验收 Tag | production | 单独授权和部署，不属于 #29 |

main 是代码分支，staging 是测试环境。生产不会随 main 自动发布。本阶段没有数据库、模型凭证或真实账号数据。

同一 SHA 共用一个不可变后端实例，使用独立目录、虚拟环境与端口。新 SHA 启动并检查通过后，才切换 main/PR 的最新入口；其他前端仍绑定旧 SHA 时继续保留旧实例。#24 的 uv.lock 锁定依赖，构建时导出运行依赖和 wheel，一同传输到课程机，在各自虚拟环境中离线安装。

默认仅改前端时连接 staging，随 main 更新；**主动指定另一个 PR 时固定其部署 SHA**。同一 PR 同时改前后端时，其自身预览跟随自己的最新成功部署，其他 PR 的固定绑定保持不变。

## 服务器、目录和端口

| 位置 | SSH | 项目目录 | 监听 |
| --- | --- | --- | --- |
| 课程机 | `group5@8.130.213.80:1021` | `/home/group5/livelife` | 后端 `127.0.0.1:18000–18063` |
| 公网机维护者 | `ubuntu@192.144.253.40:22` | `/opt/livelife` | HTTPS `443`；隧道 `127.0.0.1:28000–28063` |
| Actions 专用用户 | `livelife@192.144.253.40:22` | 仅允许 JSON 管理命令 | 无通用远程 shell |

对应端口相差 10000。分配前检查数据库、待清理记录和两侧实际监听；占用则选择其他槽位，池满明确报错。不能直接把分支名称拼接成目录、端口或 shell 命令。

课程机使用项目专属 Supervisor 和 Unix socket，普通用户即可安装；每个后端自动重启，并处理整组子进程。公网机的项目 Supervisor 管理 SSH 隧道，SSH keepalive 与自动重启负责恢复连接。`livelife-recover.timer` 每五分钟检查登记实例，恢复课程环境重启后的进程；源目录丢失时报错，需重新部署原 SHA。

公网机使用独立 `livelife-gateway.service` 运行 Nginx。SQLite 登记表在 `/opt/livelife/state/registry.sqlite3`，控制程序在 root 拥有的 `/opt/livelife/control/`。分支产物仅在课程机运行，不在公网机执行。

## API 地址与前端关联

以下为目标入口，末尾 `/` 属于 API 基地址：

```text
https://192.144.253.40/api/staging/                    main 共享测试后端
https://192.144.253.40/api/pr-40/                      PR #40 最新成功部署
https://192.144.253.40/api/versions/be-<完整40位SHA>/   不可变版本
```

请求 hello 时加 `test/hello`。网关去掉部署前缀，后端收到 `/test/hello`，响应仍为 `{"message":"hello world"}`。响应头 `X-Livelife-Backend-SHA` 提供版本，不修改业务 JSON。Uvicorn root-path 指向不可变入口，Swagger/OpenAPI 使用该前缀。

`/__livelife/versions.json` 提供已发布路由和 SHA。网页/API 使用 HTTPS Basic 认证；密码不写入链接、PR、静态前端或构建产物，网关不把基础设施认证头转给后端。控制平面只有专用 SSH JSON 命令，不提供公网 bind/delete 接口。业务登录和 APP 认证另行设计。

### 成员如何获得测试链接

1. 从 main 创建功能分支，修改并提交后端；确保分支已包含 main 上的检查工作流，必要时先同步。
2. 推送分支，或在 **Actions → Backend checks → Run workflow** 选择分支。检查 checkout 固定 head SHA，不使用 PR 合并模拟提交。
3. 检查成功后，**Preview environments** 从 main 执行控制程序。同仓库分支自动部署，fork 仅检查，不取得部署秘密。
4. 已有 PR 时自动更新同一条说明，提供固定版本 hello 链接、SHA 和 PR 最新入口；没有 PR 时从控制工作流 Summary 获取地址与到期时间。
5. 使用维护者私下提供的访问凭证打开链接。网页预览需要 #27，API 链接不表示网页已部署；开关启用后同一条评论同时提供网页和 API。
6. 新提交更新 PR 入口；失败显示候选 SHA 并保留原成功部署，不能把旧版当成本次提交通过。

`workflow_dispatch` 和 `workflow_run` 控制工作流需要先进入 main。缺少真实后端入口或依赖的分支会明确跳过打包/部署，不生成虚假的成功地址。

### 跨 PR 联调怎么指定

通常不需要指定。#27 默认连接 staging；同一分支改后端时连接自己的部署。跨 PR 时：

1. 确认目标后端 PR 已部署最新提交，例如 #40。
2. **Actions → Backend environments → Run workflow**，operation 选 `bind`，frontend_pr 填 `41`，backend_target 填 `pr-40`。
3. 工具检查两个 PR 属于本仓库且打开，解析 #40 的成功部署，保存 `frontend:41 → be-完整SHA`。最新提交尚未部署时，报错并保留原绑定。
4. 返回 `api_base_url`、`api_path`、`backend_sha`、`frontend_sha`。网页开关启用后控制器立即更新运行时配置；未启用时只记录后端绑定。

#40 更新后，#41 仍连接原 SHA。需要切换时重新 bind；target 改成 `staging` 恢复默认，填 `be-完整SHA` 可选择仍存在的特定版本。#27 更新前端时先 lookup 原绑定，保留后端 SHA 并同步前端 SHA，不能每次推送都覆盖成 staging。

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

公网机需已有 Python 3.12、venv 模块、Nginx、curl、tar 与 openssl；Ubuntu 缺少 venv 时由维护者安装 `python3.12-venv`。本次服务器已满足这些前置条件。初始化脚本不自行安装宿主机软件。

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

### 4. 设置测试访问认证并启动

```bash
openssl passwd -apr1
sudoedit /opt/livelife/credentials/htpasswd
```

通过提示输入密码，避免放进命令行。htpasswd 每行 `用户名:摘要`，livelife 拥有、权限 600；可分别创建成员账号。初始化的空文件拒绝所有请求，填入账号前不认为入口可用。

```bash
sudo systemctl enable --now livelife-gateway.service
sudo systemctl enable --now livelife-recover.timer livelife-renew-ip.timer
sudo systemctl status livelife-gateway.service --no-pager
```

没有后端路由时 API 返回 404 是正常状态。先通过专用 SSH key 发送 `{"op":"snapshot"}` 验证控制平面，再部署真实后端验证 API。#27 后续在同一 HTTPS 入口加入前端静态路由。

### 5. 配置 GitHub 并启用

**Settings → Secrets and variables → Actions**：

| 名称 | 类型 | 内容 |
| --- | --- | --- |
| LIVELIFE_DEPLOY_SSH_KEY | Secret | 第一把专用部署私钥 |
| LIVELIFE_PUBLIC_KNOWN_HOSTS | Secret | 核对指纹后的公网机 known_hosts 行 |
| LIVELIFE_SSH_TARGET | Variable | `livelife@192.144.253.40` |
| LIVELIFE_PUBLIC_BASE_URL | Variable | `https://192.144.253.40`，与服务器一致 |
| LIVELIFE_BACKEND_ENABLED | Variable | 后端自动部署开关，现已设 `true` |
| LIVELIFE_FRONTEND_ENABLED | Variable | 网页独立开关；按下文合并后启用步骤设置 |

第二把私钥和 Basic 密码不进入 GitHub。检查/打包 job 无部署秘密；控制程序从 main checkout，只解析限定的 artifact 文件，不执行其中的脚本。fork 不部署；课程机仅持测试权限，不接正式数据库/凭证。venv 是依赖隔离，不能当成安全沙箱。

控制工作流的 GitHub token 权限由 `.github/workflows/backend-control.yml` 明确声明：

```yaml
permissions:
  contents: read
  actions: read
  pull-requests: write
```

前两项用于读取 main 控制代码和构建产物；`pull-requests: write` 用于创建或更新 PR 的预览、绑定与关闭说明。评论虽然调用 `/issues/{PR编号}/comments`，目标仍是 PR，不能只授予 `issues: write` 并保留 PR 只读。此流程不需要普通 Issue 写权限、代码写权限或个人访问令牌。仓库的全局 Workflow permissions 可保持只读，工作流按需声明上述权限；自动创建或批准 PR 的开关不需要开启。

两个 enabled 均未开启时控制 job 跳过，CI 仍检查基础设施。工作流进入 main 前无法验证完整 workflow_run 链路；进入 main 后验证 Runner → 公网机 → 课程机的真实连接。

## 后端接入要求与 #27 控制接口

#24 提供 Python 3.12 工程、`backend/app/main.py` 中的 `app`、`backend/pyproject.toml` 与 `backend/uv.lock`，以及约定的 `GET /test/hello`。部署启动为 `python -m uvicorn app.main:app`，工作目录为 release/backend。不为基础设施改动业务 JSON。

构建在 GitHub 的 Ubuntu 24.04 Runner 上进行，使用 Python 3.12 与固定 `uv==0.12.23`：

1. `uv sync --locked` 检查锁文件并安装检查环境；运行实际后端的 pytest、ruff 和格式检查。
2. 启动候选后端，真实请求 hello；失败则不部署。
3. `uv export --locked --no-dev --no-emit-project` 导出运行依赖，在 Runner 上下载 Linux x86_64/Python 3.12 wheel。
4. 打包 Git 中该 SHA 的 backend 源码、生成的 `.deploy-requirements.txt` 和 `.wheels/`，不包含本地虚拟环境或未提交文件。部署产物只上传 manifest.json 与 backend.tgz。
5. 课程机创建版本独立 venv，用 pip 的 `--no-index --find-links` 离线安装；无需在每次预览时访问 PyPI。安装记录在该版本的 `install.log`。

构建和课程机须保持上述系统/架构/运行时兼容。运行依赖必须有 wheel，压缩包上限 20 MiB，文件内容上限 100 MiB、10000 个条目；超限或依赖需要源码编译时明确失败，需要专项调整，不静默在线安装。简化的 requirements.txt 工程仍可用于独立基础设施验证；正式后端以 uv.lock 为准。

uv 参数参考：[锁文件与导出教程](https://docs.astral.sh/uv/concepts/projects/sync/)。

#27 使用同一专用 SSH JSON RPC，响应 JSON，失败时非零退出且包含 error。generation 为 `GitHub run_id * 1000 + run_attempt`，自动部署使用原始构建 run 的 generation：

| op | 输入 | 行为 |
| --- | --- | --- |
| lookup | owner，如 frontend:41/main | 返回版本和 API 地址 |
| bind | frontend owner、target、generation、frontend_sha | 解析并保留固定引用；staging 显式跟随 main |
| release | owner、generation | 幂等释放，禁止 main |
| snapshot | 无 | 返回实例与引用 |
| collect / recover | 无 | 延迟清理 / 恢复进程、检查健康 |
| deploy | owner、sha、generation、bundle、digest | CI 内的部署操作，不公开 HTTP 管理入口 |

维护者可用专用密钥测试控制接口，先在本地准备权限 600 的密钥与已核对的 known_hosts，再执行：

```bash
ssh -T -i /私有路径/actions_ed25519 \
  -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/私有路径/public_known_hosts \
  livelife@192.144.253.40 <<'JSON'
{"op":"snapshot"}
JSON
```

此密钥只能调用工具，不支持远程 shell、SCP 或隧道。lookup 示例为 `{"op":"lookup","owner":"main"}`；尚无部署时返回明确错误。普通成员使用 Actions 页面操作，避免分发部署私钥。

前端切换失败时保留旧绑定，关闭 PR 才释放它的引用。#29 提供绑定接口及后端说明，不构建网页或 APK。

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

2026-10-07，PR #34 合并后的 [main 部署运行](https://github.com/TomoriKaho/Livelife/actions/runs/37503098101) 成功；[PR 关闭处理运行](https://github.com/TomoriKaho/Livelife/actions/runs/37503032614) 连续三次在写 GitHub 评论时返回 403。该运行已完成两条 release RPC，再在评论 POST 失败，后续 collect 未执行；定期核对与回收仍按现有规则补偿。本次权限修复的线上评论结果以合入后的新运行为准，不能把本地检查记为线上通过。

参考：[GitHub 工作流权限](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)、[PR/Issue 评论接口](https://docs.github.com/en/rest/issues/comments#create-an-issue-comment)、[重跑工作流](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs)。

2026-10-07 实测记录：

- 公网 IP 的可信 HTTPS 证书已签发；无凭证访问管理数据入口返回 401。
- 两级专用 SSH 密钥、known_hosts 和课程机受限端口转发已验证；公网机可以直接调用课程机控制接口。
- 三份不同 SHA 的临时 FastAPI 服务直接运行在课程机，各用独立端口，经公网 HTTPS 返回约定 hello JSON、正确 SHA 响应头与可用 Swagger 文档。
- 正式后端 PR #32 的提交 `2e10044c70cbd9bc80bcaab173f6104c4d9ecb56` 在独立本地副本通过 8 项 pytest、ruff、格式检查和 hello 打包；其 uv.lock 导出的运行依赖与 Linux wheel 已在课程机离线安装，并重复通过 HTTPS、固定绑定及回收验证。
- 前端固定绑定在后端 owner 释放后继续保留该版本；全部引用释放后，临时实例、路由和隧道已清理。未将验证服务登记为 main。
- 项目网关、恢复 timer 与证书续期 timer 已启用；GitHub 部署密钥、主机公钥和连接变量已配置，LIVELIFE_BACKEND_ENABLED 已设 true。工作流进入 main 前不会因此获得完整自动部署链路。

测试访问凭证由维护者私下提供，初始凭证保存在公网机 `/opt/livelife/credentials/access.txt`，权限 600；不在文档或 PR 中公开密码。尚无正式后端路由时，不把 API 示例当成可用应用入口。

上述为 #29 合入前的独立服务器验证记录。#29 与真实 hello 后端现已合入 main，后端自动部署已接入；#27 的网页自动事件链路在本分支完成代码后仍需合入、启用并验证。后续记录见文末。

## 合并前的分支预览

推送不等于合并。按上面的“成员如何获得测试链接”在线自测，记录 SHA；前端预览需要 #27，APP 仍需实际安装包和真机验证。

## 发布与正式部署

staging 整体验收后记录 SHA，再建立 Tag、Release 与发布说明。Release 可附 APK、指南和版本信息。生产使用独立配置与明确授权，不复用临时预览清理；创建 Release 本身不会部署。

## Capacitor 构建与首阶段验证包

网页构建 → Capacitor 同步 → Android/iOS 原生构建及签名 → 分发与真机验证。后端不随 APK 打包。Android 使用手机可访问的 HTTPS API，不能使用电脑 localhost；包记录前后端 SHA、安装步骤及未测能力。iOS 与商店发布另行安排。

参考：[Capacitor 构建流程](https://capacitorjs.com/docs/basics/workflow)。

## 网页预览实现与维护

#27 使用已有 HTTPS 443、Basic 认证和 Nginx，静态网页目录为 `/opt/livelife/web`；没有新增预览监听端口。网页通过同源 API 路径访问课程机后端，Basic 密码不进入网页、产物、配置或评论。

### 地址和配对契约

以下地址均以 `https://192.144.253.40` 为前缀：

| 环境 | 网页路径 | 自动后端 |
| --- | --- | --- |
| main | `/staging/` | main 共享测试后端 |
| 无 PR 分支 | `/preview/branch-<摘要>/` | staging；自身后端改动时使用配套版本 |
| 打开的 PR | 原分支路径及 `/preview/pr-<编号>/` | 同上；两者指向同一部署 |
| 后端-only PR | `/preview/pr-<编号>/` | 自身后端，复用 main 最近成功前端 |
| 显式联调 | 网页地址不变 | bind 解析时的固定 SHA |

摘要是原分支名 UTF-8 的 SHA-256 前 32 位，不把分支名拼入路径。控制器根据 GitHub 当前 head、PR 状态和合并基线的 Git 树判断改动；自身后端未成功部署时显示等待/失败，保留上一成功页面。仅前端更新而 backend 目录树相同时可复用自身上一后端。前后端构建谁先完成都可以，配套成功后才发布。

无 PR 分支租约为 72 小时，成功部署续期；定期核对不续期。main 永久保留，打开的 PR 保留至关闭。PR 关闭/合并、分支删除、手动释放或过期撤销入口；其他环境的固定引用不受影响。重开优先复用尚在的产物，否则等待新构建。Actions Artifact 保留 7 天，这与已部署文件生命周期不同。

### 前端构建和运行时配置

`Frontend checks` 在 Ubuntu 24.04 使用 Node 24.13.0 / npm 11.6.2，依次 `npm ci`、全部行为测试、类型检查和 Vite build，再由 `deploy/prepare-frontend.py` 生成 frontend.tgz 与版本/构建编号/压缩包 SHA-256 manifest。push、PR opened/synchronize/reopened 按前端及网页工具路径触发；手动 Run workflow 可选择分支。build job 不持有部署密钥。

`Preview environments` 从 main 读取控制代码，验证 GitHub 来源、当前提交、PR 状态与产物身份；fork 仅检查。只解析静态包，不执行产物中的脚本。安全边界参考 [workflow_run 官方说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run)。

每个入口的 `runtime-config.json` 最少包含：

```json
{
  "schema_version": 1,
  "environment": "main",
  "frontend_sha": "完整40位前端提交SHA",
  "build_id": "fe-完整SHA-构建运行编号-重试次数",
  "api_base_url": "https://192.144.253.40/api/staging/",
  "backend_mode": "staging",
  "backend_sha": "加载配置时的完整40位后端SHA"
}
```

示例中的中文为占位说明，不能直接用于发布。环境标识仅 main 或 branch-32位摘要；后端模式 staging / own / fixed。网页按当前入口读取配置后初始化 API；配置失败禁用接口测试并显示错误，不回退 localhost，样例页面仍可查看。配置 build_id 与当前 HTML 不一致时提示刷新，避免更新期间把旧页面标成新版本。

“我的 → 帮助与反馈 → 接口连通性测试”显示前端 SHA、构建号、后端模式和加载时 SHA；真实 hello 响应头记录实际后端 SHA。staging 可随 main 变化；own/fixed 的响应 SHA 不匹配时报告错误。切换配对仅更新配置，不重建前端；APK 接入由 #28 单独设计。

### 静态文件、配额与恢复

JS/CSS、地图及许可证使用 `/__livelife/web-builds/<build_id>/`；字体和图片通过共享 `/__livelife/web-assets/assets/<哈希文件名>` 分发，硬链接按物理文件去重。HTML/config 无缓存，不可变资源长期缓存，已生成 gzip 文件由 [gzip_static](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html) 分发。API 独立限流，静态资源不参与 API 限流；目录列表关闭。项目日志由 `/etc/logrotate.d/livelife` 轮转。

每个环境保留当前和上一成功部署，分别登记 `web:<部署ID>` 后端引用，与 `frontend:<PR或分支标识>` 的选择记录和未来 APK 引用分开。回滚恢复原部署的前端和后端配对；回滚后自动核对保持该页面，下一次成功前端构建才推进。候选发布之前提交持久化后端引用，网关验证成功才提交站点；失败保留旧页面。进程中断后 recover 先恢复数据库已提交的路由，再清理候选引用/文件。

默认物理网页上限 2 GiB，按去重后的文件 inode 计量；发布先回收经过宽限期的闲置文件，仍不足拒绝候选。无引用文件至少保留一小时。压缩包 64 MiB、展开 256 MiB、10000 条目；拒绝重复路径、穿越、链接和特殊文件。SSH JSON 请求上限 96 MiB，后端压缩包仍为 20 MiB。

当前字体原始约 22.2 MB、gzip 约 14.7 MB。5 Mbps 下首次完整字体传输理论约 24 秒，实际受协议和网络影响；共享缓存与 gzip 已实现，字体转换/拆分另行安排。

### 新增受限 SSH JSON 操作

原有后端操作兼容。以下操作同样通过既有 SSH 接口调用，不公开 HTTP 管理端点：

| op | 主要输入 | 作用 |
| --- | --- | --- |
| web_publish | environment、branch、pr、source_sha、generation、manifest+base64 bundle 或 build_id、target、mode | 校验静态包、保存等待记录、配对成功后原子发布 |
| web_lookup | environment | 返回状态、网页 URL、版本、API、到期时间及当前检查结果 |
| web_release | environment、generation | 撤销分支和 PR 别名；main 禁止释放 |
| web_rollback | environment、generation | 恢复上一成功页面及其后端引用 |
| web_note | environment、component、source_sha、generation、status | 记录经 GitHub 验证的构建状态 |

generation 使用原构建 run_id * 1000 + attempt；关闭和手动操作使用对应控制运行编号。内容与显式选择分别排序，旧上传、关闭后的晚到任务及前端更新不能覆盖较新的显式绑定。返回状态 ready / waiting / failed / released / superseded；waiting/failed 可能带上一成功版本，不能作为最新提交验收结果。

main 合并后可在 Actions → Preview environments → Run workflow 使用 web-lookup / web-release / web-rollback，填写 frontend_pr 或 frontend_branch（二选一）。未发 PR 的显式绑定也可填写 frontend_branch；创建 PR 时迁移为永久 PR 选择记录。bind 的 backend_target 支持 staging、pr-编号及仍存在的 be-SHA；跨 PR 解析并固定最新成功 SHA，未部署最新提交时拒绝替换旧绑定。

### 维护者启用顺序

1. 合并前运行前端行为测试/build、部署 unittest、ruff、actionlint 和服务器手动验证；由另一名成员正式评审。人工验证不需要启用自动网页开关。
2. 更新公网机 `/opt/livelife/control` 中的受信工具、项目 nginx.conf 和 logrotate 配置，创建 livelife 可写 `/opt/livelife/web`。先备份项目代码、网关配置和 SQLite，更新时持有项目锁；依赖保持现有 Python 控制环境。检查配置后只重载 livelife-gateway。既有后端操作须验证兼容。
3. 工作流合入 main 后设置 Repository Variable `LIVELIFE_FRONTEND_ENABLED=true`。后端开关保持现状；网页开关关闭不删除已部署页面，只停止自动网页管理。
4. 手动运行 Frontend checks，选择 main；等待 Preview environments 成功，检查 `/staging/` 配置/版本、认证、真实 hello。
5. 用两个开发分支和各类 PR 验证自动链接、单条评论、同分支配对、跨 PR 固定绑定、失败保留、关闭/重开与资源清理。尚未发 PR 的信息由控制 Actions Summary 给出。
6. 记录实际 SHA、构建 run、访问及测试结果。完整成员使用教程按既定安排在 #28 安装包流程完成后统一整理。

单条 PR 自动评论使用 `<!-- livelife-preview -->`，兼容升级旧后端评论，提供页面/版本/模式/API/状态；不包含认证信息。安装包及正式发布不属于本次开关。

### #27 实施验证记录（2026-10-07）

- 任务分支 `27-frontend-preview` 通过 Issue Create a branch 关联 #27。前端 39 项行为测试、类型检查、普通及预览构建通过；预览资源 URL 回归检查通过。部署工具 70 项测试通过（含真实 Supervisor 与 SIGKILL），ruff、actionlint、shell 语法及改动空白检查通过。
- GitHub Runner 实际构建提交 `2f92f54491287ce04d17841a0ab9ba3f7fcdfa7e`，Frontend checks run `37513180117` / attempt 1 成功，Artifact 约 17.2 MB。使用其原始产物手动发布分支网页，未把分支产物登记为 main 网页。
- 公网项目工具及静态网关已更新，更新前备份位于 `/opt/livelife/backups/frontend27-1791312102`。真实 HTTPS 校验发现目录入口 alias 被 Nginx 追加 index.html 的问题，已修复；失败候选未留下站点或后端引用。
- 无认证返回 401；HTML/config 无缓存；JS/CSS/地图/字体/图片及三份许可证返回 200，不可变缓存和 gzip 生效。原始字体约 22.2 MB，服务器 gzip 14,739,544 bytes；网页物理存储约 43.4 MB（共享字体按 inode 去重）。
- 临时第二环境验证独立配对、共享资源和释放；验证结束仅保留本任务分支网页。固定后端实际 hello 响应 SHA 与选择一致，随后恢复 staging，上一成功配对继续持有独立回滚引用。
- Playwright Chrome 390×844 实测样例引导、3D canvas、2D 地图、个人页、刷新/哈希路由及真实 hello；页面显示前端构建号、加载时和真实响应后端 SHA。浏览器内模拟配置 HTTP 503 后，样例仍可访问、接口按钮禁用，未回退 localhost；移除模拟后恢复。控制台仅有原有 favicon.ico 404，不影响页面/API；OSM 可见署名仍由 #31 跟进。
- 课程机新 SSH 连接曾被重置，已有 staging HTTPS hello 持续返回 200；恢复检查及 Backend environments run `37513257959` 重试后成功，验证旧后端控制与新网页注册表兼容。

**尚待合并后验证**：`LIVELIFE_FRONTEND_ENABLED` 仍未开启；main 首次网页构建、Frontend checks → Preview environments 完整事件链路、自动 PR 评论/别名、真实关闭/重开/删除及跨 PR 联调，需要按上文顺序验证。当前分支网页为人工验收发布，并非自动网页开关已上线。另一名成员的正式 PR 评审与独立复现尚未完成；完整成员教程延后到 #28。
