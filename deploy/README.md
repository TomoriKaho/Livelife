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

## 预览数据库与启动门禁

采用 `postgres-v1` 的新自动部署使用**每分支持久数据库**。课程机目录为 `databases/branch-<分支名SHA256前32位>/postgres/`，公网注册表的 `branch_databases` 保存分支与来源。API 实例仍按代码版本保留，ID 为 `be-<40位提交SHA>-<32位分支摘要>`；不同分支即使提交相同也有独立实例、端口与数据库。网页、APK 和 PR 别名指向返回的实例地址，不能自行用提交 SHA 拼地址。旧 `be-SHA` 地址与无 database 字段的历史部署继续按原规则恢复。

首次部署的来源规则：优先复制该 PR／分支已经部署的旧版本（同分支升级，全量保留业务数据）；没有旧预览时，复制 PR 的 base 分支当前数据库。未开 PR 的分支默认来源 main；Git 本身没有可靠的“从哪个分支创建”记录，需要其他来源时应在首次部署前设置 PR base，或通过受信部署请求传 `database.source_branch`。已有分支的来源不随改 base、创建/关闭 PR 或新 commit 改变。来源没有数据库时失败，只有首次 main 允许空库初始化。

快照取于**首次部署执行复制时**，不是 Git 建分支时。启动器在来源迁移锁内用 pgembed 同发行版的 `pg_dump` 获取一致性逻辑快照，再用 `pg_restore --single-transaction` 恢复到私有临时集群；不直接复制运行中的 PostgreSQL 文件。公网控制器根据现有同分支引用确定并固化 `copy_mode`，请求方不能自行选择全量复制：

- 同分支旧预览升级使用 `full`：复制数据库完整 schema、Alembic revision、所有表的行和大对象，包括账号及密码哈希、验证码、登录会话、聊天、个人资料与未知业务表；同时继承旧库目录的 Agent 会话密钥。原密钥文件缺失或损坏时拒绝发布，不能静默生成新密钥导致会话失效。复制的是数据库业务内容，不复制集群角色或 ACL；原数据库与密钥文件不修改、不删除。
- 新建分支使用 `public`：仅保留公开数据白名单 `information_items`、`information_places`、`information_place_aliases` 与迁移记录；私人表、未知表数据和大对象不复制，并生成独立的 Agent 会话密钥。新分支重新注册测试账号。新增公开数据表时须评审后加入白名单。

已有分支库再次部署不重新复制、不重新清理账号或聊天。没有 `copy_mode` 的旧登记记录沿用之前的 `public` 语义，不根据来源名称自动升级权限。若曾使用旧版 #90 初始化过脱敏库，更新代码不会补回已排除的数据；应保留两边数据与备份，由维护者单独制定恢复或迁移方案，不能覆盖已使用的新库。

首次复制、迁移和 ORM 列检查全部成功后才保留分支集群并写 `initialized.json`（来源与时间）；失败不发布候选，临时集群可重试。极端中断若留下有 postgres 而无 marker 的目标目录，会拒绝覆盖，需要维护者检查备份和日志后恢复，不能直接删库重试。首次复制成功后，后续 commit 仅复用本分支集群、串行执行 `alembic upgrade head`、检查 revision/ORM 列，再启动 API。并发迁移使用跨进程文件锁；来源迁移与复制也互斥。数据库与启动器由固定 `pgembed==0.2.0` 管理，Linux 只监听 Unix socket，无需 Docker/root。业务 venv 仍来自经过测试的 release。

新分支启动探针最多等待 600 秒，旧模式保持 180 秒；课程机和公网同时要求 hello 与 `/health/ready` 成功。失败保留旧路由，但**迁移已经提交的结构变更不会因后续发布失败而自动撤销**。同一分支的新旧固定代码版本共享该分支数据库，必须采用向后兼容的扩展式迁移。旧代码不认识已有 revision 时恢复会失败；不能把固定代码 URL 当成数据库时间快照。破坏性迁移须单独协调旧引用、备份和恢复，不自动 downgrade。

合并分支只合并代码：目标分支升级自己的数据库，源分支测试数据不自动合并。停止 API 时释放本进程的 pgembed handle；其他版本仍使用该分支库时数据库继续运行。回收 release、关闭 PR、分支引用到期都不删除数据库及来源记录；重开同名分支会复用原数据。维护者需监测磁盘，确认全部引用和进程停止、备份完成后才能手动归档或删除。

数据目录权限 0700，`runtime.json` 中 Agent 会话密钥权限 0600，同分支首次升级继承原密钥、跨 commit 复用，新分支重新生成。API 仅接收必要环境、该分支连接和显式配置的测试 SMTP/模型凭证；`LIVELIFE_BACKEND_SHA` 始终是真实提交 SHA，不含分支摘要。`AUTH_TEST_LOGIN_ENABLED=false` 保持既有行为。此方案是同一课程机账号内的测试隔离，不是抵御恶意代码的安全沙箱，也不用于正式数据或正式凭证。

### 自动部署的测试邮箱配置

课程机固定文件 `/home/group5/livelife/credentials/smtp.json` 为所有采用 `postgres-v1` 启动器的 main、分支及 PR API 提供测试邮箱。它独立于 release 和构建目录，新 SHA 启动时自动读取，不需要每次复制 `backend/.env`，也不需要把邮箱授权码写入 GitHub Actions。现有 legacy 实例不读取此文件，须先按下一节完成数据库启动器升级。

配置仅允许 `SMTP_HOST`、`SMTP_PORT`、`SMTP_FROM`、`SMTP_USERNAME`、`SMTP_PASSWORD`。启动器只给 Uvicorn 子进程加入这些值，迁移、表结构检查和构建任务不接收它们；也不会从控制进程环境或其他 `.env` 中寻找 SMTP。文件缺失时保持邮件未配置，文件损坏、字段非法、链接或权限过宽时拒绝候选启动，错误信息不打印配置内容。配置目录须由运行用户拥有、权限 0700，文件为 0600。

这里的邮箱供整个团队测试环境共用。API 进程仍共用课程机账号，文件权限及环境变量白名单不能阻止同账号分支代码读取它；因此只能放专用测试邮箱凭证，不能放正式邮件或部署凭证。构建任务继续受现有 bubblewrap 沙箱限制。

首次接入时，在课程机上使用已评审 checkout，以 `group5` 操作。先备份已安装的 `backend_runtime.py`；如已存在 `mail_config.py` 也一并备份，然后更新这两个模块，保留其余控制文件及凭证：

```bash
task_root=/home/group5/livelife
install -m 600 deploy/livelife/mail_config.py "$task_root/control/livelife/mail_config.py"
install -m 600 deploy/livelife/backend_runtime.py "$task_root/control/livelife/backend_runtime.py"
install -d -m 700 "$task_root/credentials"
cd "$task_root/control"
"$task_root/control-venv/bin/python" -m livelife.mail_config \
  --root "$task_root" --host smtp.163.com --port 465 \
  --sender pku_livelife@163.com --username pku_livelife@163.com
```

按提示输入邮箱的 SMTP 授权码（隐藏输入），不要把授权码放在命令参数、脚本、提交或日志里。配置工具原子写入文件；163 的 465 端口由后端使用 SMTP SSL。可执行以下只读检查，它只报告配置是否存在及格式、权限是否正确，不代表已经通过 SMTP 认证或邮件送达：

```bash
"$task_root/control-venv/bin/python" -m livelife.mail_config --root "$task_root" --check
```

已运行实例要逐个重启才能读取新配置；普通 recover 或重跑同 SHA 构建不会强制重启现存 API。先核对目标的 SHA、端口、`release.json` 中的 `runtime_mode=postgres-v1` 及 Supervisor 程序名，再仅重启该目标：

```bash
task_instance=be-替换为目标的完整40位SHA
"$task_root/control-venv/bin/python" -m supervisor.supervisorctl \
  -c "$task_root/supervisor/supervisord.conf" restart "$task_instance"
```

验证目标 hello、`/health/ready` 和响应版本，随后在登录页面向成员自己的测试收件地址请求一次验证码并完成登录；记录收件结果，不在日志或 PR 记录验证码、授权码。新 SHA 的 main 和 PR 部署会自动使用同一份配置。配置更新也需重启已运行目标；停用时将 `smtp.json` 移到同一私有目录内的备份名称后重启目标。控制代码回退需成对恢复这两个模块，保留凭证文件和数据库，不重启其他项目或所有实例。

这项接入需一次服务器配置；仅合并代码不会安装受信启动器或创建凭证。服务器启用及真实收信证据统一记录在[当前实施状态](../docs/deployment.md#当前实施状态)。

### 测试模型配置

课程机 `credentials/model.json` 是维护者管理的私有文件：目录 0700、文件 0600、由运行用户拥有且不能是符号链接。结构如下，真实密钥及代理密码只在服务器填写，不提交、不放在命令参数或构建日志中：

```json
{
  "trusted_shas": ["替换为经过核对的完整40位提交SHA"],
  "environment": {
    "AGENT_LLM_BASE_URL": "https://api.openai.com/v1",
    "AGENT_LLM_API_KEY": "<测试用途密钥>",
    "AGENT_LLM_MODEL": "gpt-6.1-sol",
    "AGENT_LLM_REASONING_EFFORT": "high",
    "AGENT_LLM_MAX_OUTPUT_TOKENS": "4096",
    "AGENT_LLM_TIMEOUT_SECONDS": "180",
    "HTTPS_PROXY": "http://<代理用户名>:<URL编码的密码>@127.0.0.1:17890"
  }
}
```

不需要代理时省略 `HTTPS_PROXY`。本配置只接受回环 HTTP 代理，启动器同时设置本机 `NO_PROXY`；代理安装及订阅由维护者单独管理。文件缺失不启用模型，格式或权限错误拒绝启动且不显示内容。`trusted_shas` 只接受完整 SHA，不支持分支名或通配符；空数组表示暂停所有版本的模型注入。新提交默认无模型密钥，维护者核对账户鉴权、配额及具体版本后再加入名单并重启该实例。修改名单不撤销现有进程环境，移除版本也须重启。

启用前安装配套 `model_config.py` 与 `backend_runtime.py` 到课程机 `control/livelife/`，保留本机定制钩子（例如测试账号初始化）及凭证。先备份原文件，使用已经检查的代码；仅 Git 推送不会更新启动器。模型配置只注入对应 Uvicorn 子进程，迁移、表结构检查、构建及未列出的 API 不接收。只向已核对的可信版本启用专用测试密钥；同账号运行不是安全沙箱，SHA 名单不能阻止恶意同账号代码直接读取文件，不可承载正式凭证。

重启命令沿用[测试邮箱配置](#自动部署的测试邮箱配置)，仅重启选中实例。验收至少包括：hello/ready 成功、空白登录和匿名 Agent 请求被拒绝、普通账号登录后流式返回非空文本与真实 usage、令牌注销后不再可调用。回退时移除对应 SHA 并重启，确认模型未配置；回退启动器须同时恢复配套模块，保留数据。服务器启用证据见[部署状态](../docs/deployment.md#当前实施状态)。

### 首次启用与现有服务器升级

新增安装由下节 `bootstrap-course.sh` 安装 Supervisor 与固定 pgembed。已有服务器需要维护者从**已评审版本**更新课程机 `/home/group5/livelife/control/livelife/` 下的 `backend_runtime.py`、`branch_database.py`、`common.py`、`course.py`、`supervisor.py`，以及公网机 `/opt/livelife/control/livelife/` 下的 `branch_database.py`、`common.py`、`registry.py`、`manager.py`、`course.py`、`runtime.py`、`web.py`、`android_build.py`。课程机另执行：

```bash
/home/group5/livelife/control-venv/bin/python -m pip install 'pgembed==0.2.0'
```

更新前备份上述控制文件、注册表和数据库，保留既有 config、凭证和其他服务；逐项比对服务器已有的测试账号初始化、模型配置扩展，不能整包覆盖丢失这些配置。按下述升级窗口操作：先暂停自动部署和回收，再合并客户端地址校验和 Actions 控制代码，让要切换的业务分支同步这一版本，安装两机受信控制程序后再手动部署。旧前端无法识别新分支后缀，因此不能只升级服务器后让旧客户端使用新 URL。不要将未评审分支中的控制程序直接装入服务器。工作流控制代码仍从 main 执行，所以只 push 业务分支或重跑构建不会更新这些已安装的控制文件。

#### 保留现有账号和聊天的升级窗口

1. **先暂停控制任务，再合并。** 维护者暂停 GitHub 的 `Preview environments` 工作流，核对并暂停项目的 `livelife-recover.timer` 和其他 collect/recover 调度；确认已启动的控制任务结束、没有在途发布。记录暂停前状态，勿停止其他项目。构建请求即使成功也不代表发布已执行，恢复后需重新触发目标构建。
2. **盘点并备份。** 根据注册表记录 main、各 PR、固定网页/APK 的实例、SHA、端口、旧数据库目录、Agent runtime.json 和行数基线。公网 SQLite 使用 SQLite backup API 或 `.backup` 获取一致副本，不直接复制活跃数据库文件。课程机对每个目标库用同发行版 `pg_dump --format=custom` 做完整逻辑备份（不得带私人表排除参数），同时私有备份 runtime.json、控制代码、配置及必要 release/Supervisor metadata；核对 dump 可读并在临时库试恢复。备份目录 0700、文件 0600，账号、聊天和密钥不得进入 Git、Actions artifact 或公开日志。
3. **安装配套模块。** 合并后从已评审提交准备受信代码，先更新课程机，再更新公网机；完整模块清单见本节开头，公网必须更新 `web.py`，否则新实例的网页配置 SHA 会错误。核对服务器额外的测试账号初始化与模型配置逻辑，按差异保留，不能整目录覆盖；初始化账号只能补缺，不能重置已复制账号。同步业务分支的客户端地址校验。保持自动控制暂停，并避免在控制请求运行时逐文件替换模块。
4. **暂停目标旧库的全部写入，再复制和切换。** 对同分支旧库，停止所有连接该库的目标 API/采集 worker/定时写入，或在经验证的网关维护规则下禁止写入；确认没有其他写入客户端后补做最终备份。迁移文件锁只约束迁移和复制，不能阻止业务请求写库，`pg_dump` 也只包含快照时已提交的数据。因此必须从最终快照前一直保持停写，直到新入口核验完毕。不要仅暂停 Actions 就认为旧库已经停写。可停止旧 API 而保留数据目录，复制器会按需启动 PostgreSQL。
5. **部署并核验一个环境。** 在其他自动调度仍受控的窗口，通过受信控制器手动执行目标部署；也可在确认没有并发控制任务后恢复控制工作流并单独触发目标构建。核对返回的数据库来源与 `copy_mode=full`，比较账号、聊天、会话、活动等行数与业务内容，验证原账号密码、未过期登录令牌、原 Agent 会话恢复、地图/日历和 hello/ready；不得在日志打印密码、令牌或聊天正文。`full` 保留原始数据和密钥，但不会绕过令牌有效期或应用正常的会话过期/清理规则。新分支单独验证 `copy_mode=public`、无旧账号/聊天且密钥独立。
6. **确认切换后恢复调度。** 再次部署同分支新 commit 验证复用，然后按记录恢复控制工作流、回收/恢复定时任务和使用新库的业务写入。仍指向旧独立库的 API 不得恢复写流量，避免出现两份互相分离的数据；先更新固定网页/APK 配对（旧 APK 必要时撤销并重发），解除旧实例的全部引用，等待宽限期后执行 collect，确认注册表中旧实例已移除，再恢复 recover；未完成时继续保持恢复调度暂停和旧入口维护状态，避免 recover 重新启动旧库写入口。旧库、旧密钥及备份保留，不自动删除。各环境逐一迁移，不操作 `/opt/sounichi-navi`。

切换失败时：新库尚未接受业务写入，可以恢复旧控制代码、原实例和路由，保留新库供排查；若新库已有新增账号或聊天，不能直接切回旧库丢弃新增记录，应再次停写、备份两库并制定数据迁移方案。若初始化 marker 已写入但候选发布失败，重试会复用该快照，不能一边恢复旧库写入一边继续自动重试；恢复旧库写入后须重新评估两库差异，不能假定快照会自动刷新。已提交的 Alembic 迁移不自动回滚。上述为维护步骤，仓库测试通过不代表服务器已执行。

运行模式按 release 固定。新安装只在产物包含 `backend/preview-runtime.json` 且内容为 `{"runtime_mode":"postgres-v1"}` 时启用数据库，并把模式写入 `release.json`；无标记的历史 SHA 重装和 smoke fixture 仍使用 `legacy`。未知模式或损坏标记拒绝启动。已有 `release.json` 缺少 `runtime_mode` 时始终视为 legacy，不因源码有迁移或标记而自动升级；recover 保留其既有 Supervisor 配置，只尝试启动原进程，不创建数据库或密钥。缺失配置时重建原 Uvicorn 启动方式。legacy 只检查 hello，postgres-v1 同时检查数据库 readiness。

先更新课程机控制程序，再更新公网机，避免新版公网健康检查调用旧课程机不存在的 `health_policy`。更新完成后，再运行目标分支的 Backend build request。显式升级已安装目标版本时，维护者须先记录 SHA、端口、原成功路由，并备份该版本 `release.json` 和 `supervisor/programs/be-SHA.conf`；仅在已确认该版本迁移可用、依赖齐备并获得授权后，将目标 metadata 的 `runtime_mode` 设置为 `postgres-v1`，再恢复该目标。没有新增 RPC 写模式的权限或接口。普通 recover 不改变其他旧版本。禁止操作 `/opt/sounichi-navi`。

目标升级失败的回退：停止该目标数据库启动器，恢复备份的 release metadata 和 Supervisor 配置，执行项目 Supervisor 的 reread/update 并启动原目标，验证原 hello 和路由。不能只删除 metadata 模式字段而保留数据库启动命令。保留数据库目录及备份，不自动删除或降级数据库；回退只恢复原运行方式，并不会给旧 API 增加数据库能力。

验证当前入口的 hello、`/health/ready`（应为 `database: connected`），再用正常测试账号验证 `/auth/me`、退出、同分支升级及新提交保留账号/聊天、旧会话恢复、新分支公开数据复制以及私人数据未复制。仓库提供启动器不代表线上已启用，证据见[当前实施状态](../docs/deployment.md#当前实施状态)。回退控制代码时保留仍被运行实例使用的启动器模块和 pgembed；不自动降级或删除数据库。

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

#24 提供 Python 3.12 工程、`backend/app/main.py` 中的 `app`、`backend/pyproject.toml` 与 `backend/uv.lock`，以及约定的 `GET /test/hello`。预览先经[受信启动器](#预览数据库与启动门禁)准备数据库，API 子进程仍运行 `python -m uvicorn app.main:app`，工作目录为 release/backend。不为基础设施改动业务 JSON。

以下为旧 GitHub Runner 打包模式，保留兼容旧产物，不是新请求工作流的执行路径。新路径见[课程机统一构建与队列](BUILDING.md#课程机统一构建与队列)。旧模式使用 Python 3.12 与固定 `uv==0.12.23`：

1. `uv sync --locked` 检查锁文件并安装检查环境；运行实际后端的 pytest、ruff 和格式检查。
2. 启动候选后端，真实请求 hello；失败则不部署。
3. `uv export --locked --no-dev --no-emit-project` 导出运行依赖，在 Runner 上下载 Linux x86_64/Python 3.12 wheel。
4. 打包 Git 中该 SHA 的 backend 源码、生成的 `.deploy-requirements.txt` 和 `.wheels/`，不包含本地虚拟环境或未提交文件。部署产物只上传 manifest.json 与 backend.tgz。
5. 课程机创建版本独立 venv，用 pip 的 `--no-index --find-links` 离线安装；无需在每次预览时访问 PyPI。安装记录在该版本的 `install.log`。

构建和课程机须保持上述系统/架构/运行时兼容。运行依赖必须有 wheel，压缩包上限 20 MiB，文件内容上限 100 MiB、10000 个条目；超限或依赖需要源码编译时明确失败，需要专项调整，不静默在线安装。简化的 requirements.txt 工程仍可用于独立 hello 构建验证；新预览部署要求源码提供 Alembic 迁移及共享 ORM Base，缺失时拒绝启动，不降级为 hello-only 就绪。正式后端以 uv.lock 为准。

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
- 业务回滚：重新部署确认的旧 SHA；新分支模式继续使用该分支数据库，不自动降级。须先确认旧代码与当前 schema 兼容；历史无分支配置的 release 仍使用原 SHA 数据库。正式数据库的回滚策略需另行确认，细节见[预览数据恢复限制](#预览数据库与启动门禁)。

### PR 评论返回 403 时如何处理

1. 打开失败的 **Preview environments** 运行，查看失败步骤。如果 traceback 位于 `GitHub.comment` 的 POST/PATCH 并显示 `HTTP Error 403`，被拒绝的是 GitHub 评论接口；这不能说明腾讯云拦截了 SSH。若失败的是 SSH 超时或公钥认证，则按隧道、网络或密钥问题排查。
2. 展开 **Set up job → GITHUB_TOKEN Permissions**，确认实际权限包含 `PullRequests: write`。在上述控制工作流中声明权限，通过 PR 合入 main；不要仅为评论把仓库所有工作流改成写权限或公开部署私钥。
3. 权限修复合并后，使用新事件验证。合并修复 PR 产生的 closed 事件应成功释放它的引用并创建或更新关闭说明；也可在后续打开的同仓库 PR 上验证预览/绑定说明。直接 Re-run 原来的失败任务仍使用原事件提交的工作流权限，不能用它验证新的 YAML 权限。
4. 检查新运行的真实权限、评论及 Actions 结果。若仍为 403，核对目标 PR 是否锁定、实际 token 权限与仓库/组织策略，保留运行链接；不把用户个人 token 的成功当成 `GITHUB_TOKEN` 已修复。

参考：[GitHub 工作流权限](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)、[PR/Issue 评论接口](https://docs.github.com/en/rest/issues/comments#create-an-issue-comment)、[重跑工作流](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs)。
