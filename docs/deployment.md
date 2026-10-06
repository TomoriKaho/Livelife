# 环境、Actions 与发布教程

## 当前实施状态

frontend/ 已提供本地网页工程，运行 `npm run build` 后可用 `npm run preview` 查看构建产物；安装、端口及环境变量配置见 [工程规范](engineering.md#目录与启动命令)。backend/ 已提供本地 hello 服务，启动和检查步骤见工程规范；本分支尚无业务后端、Docker 配置、部署凭证、APP 构建配置或可执行工作流，没有已验证的远程服务地址。本地构建预览不代表正式工程已部署。

#29 增加了后端环境管理工具、服务器初始化脚本与 Actions 工作流。课程机直接运行 Python 后端，不使用 Docker；公网机提供 HTTPS API，经 SSH 隧道访问课程机。跨 PR 联调固定后端提交版本。

正式后端由 #24 初始化，当前已有待合并的后端 PR #32。本分支没有合入后端业务工程；网页预览由 #27 接入，APK 自动构建由 #28 接入。两台服务器的控制程序、IP HTTPS、认证和隧道已配置，三个临时 Git 版本的端到端验证已通过。main 的完整 Actions 部署仍待工作流与正式后端合入，实际验证与未完成项见文末。

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
3. 检查成功后，**Backend environments** 从 main 执行控制程序。同仓库分支自动部署，fork 仅检查，不取得部署秘密。
4. 已有 PR 时自动更新同一条说明，提供固定版本 hello 链接、SHA 和 PR 最新入口；没有 PR 时从控制工作流 Summary 获取地址与到期时间。
5. 使用维护者私下提供的访问凭证打开链接。网页预览需要 #27，API 链接不表示网页已部署。
6. 新提交更新 PR 入口；失败显示候选 SHA 并保留原成功部署，不能把旧版当成本次提交通过。

`workflow_dispatch` 和 `workflow_run` 控制工作流需要先进入 main。缺少真实后端入口或依赖的分支会明确跳过打包/部署，不生成虚假的成功地址。

### 跨 PR 联调怎么指定

通常不需要指定。#27 默认连接 staging；同一分支改后端时连接自己的部署。跨 PR 时：

1. 确认目标后端 PR 已部署最新提交，例如 #40。
2. **Actions → Backend environments → Run workflow**，operation 选 `bind`，frontend_pr 填 `41`，backend_target 填 `pr-40`。
3. 工具检查两个 PR 属于本仓库且打开，解析 #40 的成功部署，保存 `frontend:41 → be-完整SHA`。最新提交尚未部署时，报错并保留原绑定。
4. 返回 `api_base_url`、`api_path`、`backend_sha`、`frontend_sha`。#27 读取此结果更新自己的运行时配置；#29 的 bind 本身不会修改前端网页。

#40 更新后，#41 仍连接原 SHA。需要切换时重新 bind；target 改成 `staging` 恢复默认，填 `be-完整SHA` 可选择仍存在的特定版本。#27 更新前端时先 lookup 原绑定，保留后端 SHA 并同步前端 SHA，不能每次推送都覆盖成 staging。

## 保留、关闭、重开和回收

每个 owner 只有一条保留记录，重复调用不累加计数：

- `main`：永不允许释放，版本随成功部署更新。
- `pr:40`：后端 PR 打开时保留其最新成功部署。
- `frontend:41`：绑定保留固定版本，直到释放或前端 PR 关闭。
- `branch:<分支摘要>`：未关联 PR 的部署租约，72 小时到期，重新部署可续期。

浏览器打开与否、人数和请求次数不影响保留。PR 关闭释放它的后端记录和前端绑定，其他前端仍引用的版本继续运行。分支删除仅释放分支租约。每十五分钟核对 PR 状态、回收到期租约，弥补任务队列遗漏或 webhook 清理失败。

最后一个引用释放后等待一小时再清理。PR reopened 会检查并部署当前 SHA；实例还在则复用/恢复，已清理则重新安装。固定引用不能静默回退到 staging。

管理命令在服务器持有文件锁，端口与记录变更串行；不使用会丢弃较早 pending 任务的全局 Actions concurrency 队列。SQLite 保存工作流 generation。关闭留下墓碑，较早构建延迟完成不能复活已关闭 PR。清理先撤路由并保存待清理记录，再停止进程；课程机不可达时保留端口占用并重试，不给新版本分配未释放端口。

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
| LIVELIFE_BACKEND_ENABLED | Variable | 完成人工验证后设 `true` |

第二把私钥和 Basic 密码不进入 GitHub。检查/打包 job 无部署秘密；控制程序从 main checkout，只解析限定的 artifact 文件，不执行其中的脚本。fork 不部署；课程机仅持测试权限，不接正式数据库/凭证。venv 是依赖隔离，不能当成安全沙箱。

enabled 未设置时控制 job 跳过，CI 仍检查基础设施。工作流进入 main 前无法验证完整 workflow_run 链路；进入 main 后验证 Runner → 公网机 → 课程机的真实连接。

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

2026-10-07 实测记录：

- 公网 IP 的可信 HTTPS 证书已签发；无凭证访问管理数据入口返回 401。
- 两级专用 SSH 密钥、known_hosts 和课程机受限端口转发已验证；公网机可以直接调用课程机控制接口。
- 三份不同 SHA 的临时 FastAPI 服务直接运行在课程机，各用独立端口，经公网 HTTPS 返回约定 hello JSON、正确 SHA 响应头与可用 Swagger 文档。
- 正式后端 PR #32 的提交 `2e10044c70cbd9bc80bcaab173f6104c4d9ecb56` 在独立本地副本通过 8 项 pytest、ruff、格式检查和 hello 打包；其 uv.lock 导出的运行依赖与 Linux wheel 已在课程机离线安装，并重复通过 HTTPS、固定绑定及回收验证。
- 前端固定绑定在后端 owner 释放后继续保留该版本；全部引用释放后，临时实例、路由和隧道已清理。未将验证服务登记为 main。
- 项目网关、恢复 timer 与证书续期 timer 已启用；GitHub 部署密钥、主机公钥和连接变量已配置，LIVELIFE_BACKEND_ENABLED 已设 true。工作流进入 main 前不会因此获得完整自动部署链路。

测试访问凭证由维护者私下提供，初始凭证保存在公网机 `/opt/livelife/credentials/access.txt`，权限 600；不在文档或 PR 中公开密码。尚无正式后端路由时，不把 API 示例当成可用应用入口。

本分支验证见 [基础设施验证](testing.md#后端部署基础设施验证)。工作流尚需经成员评审合入 main，再与 #24 合入的后端验证完整 workflow_run、PR 自动说明、main 更新与 reopened 链路；网页关联由 #27 完成。完成这些验收前不关闭 #29。

## 合并前的分支预览

推送不等于合并。按上面的“成员如何获得测试链接”在线自测，记录 SHA；前端预览需要 #27，APP 仍需实际安装包和真机验证。

## 发布与正式部署

staging 整体验收后记录 SHA，再建立 Tag、Release 与发布说明。Release 可附 APK、指南和版本信息。生产使用独立配置与明确授权，不复用临时预览清理；创建 Release 本身不会部署。

## Capacitor 构建与首阶段验证包

网页构建 → Capacitor 同步 → Android/iOS 原生构建及签名 → 分发与真机验证。后端不随 APK 打包。Android 使用手机可访问的 HTTPS API，不能使用电脑 localhost；包记录前后端 SHA、安装步骤及未测能力。iOS 与商店发布另行安排。

参考：[Capacitor 构建流程](https://capacitorjs.com/docs/basics/workflow)。
