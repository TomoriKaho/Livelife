# 课程机统一构建与队列

代码拉取、依赖准备、检查、测试和构建统一在课程机执行。GitHub Actions 负责调度和结果呈现；后端留在课程机运行，网页包直接传到公网机，由项目 Nginx 发布。启用证据见[当前实施状态](../docs/deployment.md#当前实施状态)。

课程机固定 Node 24.13.0、npm 11.6.2、Python 3.12、uv 0.12.23 和 Supervisor 4.3.0。工具版本及校验由安装脚本维护，本地开发无需改用服务器镜像或修改锁文件。

本文维护工具安装、调度、源码拉取、预算及 SSH 控制传输。成员判断检查结果见[部署入口](../docs/deployment.md#构建结果怎么判断)；接口字段见[控制接口](CONTROL_API.md#构建控制接口)，回归见[部署工具测试](tests/README.md)。

## 执行顺序与结果

1. 开发者 push 或打开/更新/重开 PR，触发 Backend build request / Frontend build request。它们不检出代码、不执行构建、不取得部署私钥；绿色仅表示请求通知已发出。
2. workflow_run.completed 触发 main 上的 Preview environments。控制器重新查询 GitHub 的 run、来源仓库、固定工作流路径、当前分支 SHA 和 PR 状态；旧提交、关闭/删除分支及 fork 均不提交任务。特权代码只来自 main，不执行分支中的部署脚本。
3. 公网机转发 build_submit，课程机持久化到 `/home/group5/livelife/builds/queue.sqlite3`。整个项目最多同时运行 **2 个任务**，包含拉取、依赖安装、检查、测试与构建；其余 FIFO 排队。同 SHA、同模块的首次 push/PR 通知复用一份检查，前后端是两个独立任务。同 SHA 的 push/PR 通知即使乱序到达也复用同一任务，不能把较晚到达的旧通知误报为检查失败。相同分支尚未执行的旧 SHA 被新的请求取代；已运行的任务结束后再次核对 SHA，不能发布过期提交。
4. 课程机用 GitHub 直连拉取已指定 SHA，复用 source.git，不跟随浮动分支。缓存提交以 `refs/livelife/source/<SHA>` 保留，使 Git 能协商增量传输；旧浅缓存中已有的有效提交会先补齐引用，避免只有对象、没有引用而重复拉取大包。源码拉取持有项目 source.lock；fetch 单次上限 180 秒、最多 3 次尝试，连续 30 秒低于 1 KiB/s 时终止慢连接。超时先终止整个 Git 进程组，再清理本次新建的 shallow.lock，已有锁不自动删除；失败日志包含 Git stderr，便于区分网络和锁错误。每个任务有独立 worktree、虚拟环境、日志和产物目录；仅构建目录与依赖缓存可写，主目录、SSH 文件和队列数据库不进入构建沙箱，环境中没有 GitHub token 或部署私钥。每个任务限制为最多 4 个可用 CPU；Node 堆上限 1536 MiB，不等同于整个进程的 OS 内存硬限制。
5. npm 使用 `https://registry.npmmirror.com`，Python 优先使用 `https://mirrors.aliyun.com/pypi/simple`，依赖准备失败时仅重试到清华镜像，测试失败不会重试掩盖；npm/uv/pip 下载缓存分别位于 builds/cache。为避免 uv.lock 内原始 wheel URL 绕过镜像，仅在临时 worktree 改写官方包源域名，版本和原有哈希保持；不修改仓库锁文件。源或包不可用就报错，不静默放弃锁文件。Node 镜像包核对 Node 官方 SHASUMS，APT 工具核对官方 APT 元数据 SHA-256。
6. Backend checks 包含部署工具 unittest、后端 pytest/ruff/格式检查及真实 hello。Frontend checks 包含 npm ci、行为测试、类型检查、Vite build 和预览资源 URL 校验。后端通过后保留原 venv，发布时链接到这份已测试环境；不再下载 wheel 或第二次安装。网页由受信程序打包，manifest 固定 SHA、构建编号和 digest。
7. Actions 每次通过短 RPC 查询 build_status，按 offset 获取日志并写回 GitHub。SHA 的 Frontend checks / Backend checks 状态由 pending 改为 success/failure；日志中的 workflow command 禁用解析，不能把分支输出当成 Actions 指令。失败令控制工作流非零退出，保留原成功环境。检查成功与部署成功分别记录，发布失败不会抹掉真实测试结果。
8. 发布前再次核对分支/PR。后端 deploy_built 沿用端口预约、健康检查、generation 和引用生命周期；网页 web_publish_built 从课程机获取 frontend.tgz，在公网机校验、解包、准备配置和引用、原子切换。大包不经过 GitHub Runner，也不会在公网机执行产物里的脚本。网页开关关闭时仍可检查前端，明确记录 checked 而不发布。

每条命令上限 20 分钟，任务检查阶段合计最多 30 分钟；Actions 队列等待和检查查询合计最多 40 分钟，控制 job 最多 45 分钟。日志上限 4 MiB，每次回传最多 32 KiB。工具/源码失败同样记为 failure。worker 重启后未完成任务记为失败，不伪造成功；重新运行请求可重建，已成功的同 SHA 可复用。

课程机任务记录和网页包默认保留 7 天。后端 release.json 中仍指向的任务目录永久保留到实例真正清理，避免回收正在运行或固定绑定/回滚使用的 venv。公网网页仍按自身当前/上一版本及容量规则保存，不跟随课程机包到期删除。磁盘不足 1 GiB 时拒绝新构建。下载缓存和 source.git 是项目级缓存；长期磁盘配额与缓存淘汰需要根据实际增长维护，不将 1.4 TiB 共享磁盘视为本组独占。

## 课程机 SSH 控制连接复用

公网机通过 OpenSSH ControlMaster 共用一条已认证的课程机控制连接。不同 Actions/RPC 进程在该连接上打开独立会话；构建状态查询、产物传输和部署控制不再每次重新进行 TCP/SSH 握手。主连接空闲 120 秒自动退出，后续请求重新建立；现有各后端的长期转发隧道继续独立运行。

`/opt/livelife/ssh` 归 `livelife` 所有、权限必须为 0700，内部控制 socket 及创建锁不向其他用户开放。socket 名称包含连接参数和密钥/known_hosts 文件身份；凭证文件更换后使用新连接。复用仍保留固定密钥、BatchMode 和 StrictHostKeyChecking；不绕过主机公钥校验。

首次创建用文件锁协调并发请求，只串行化连接建立，正常 RPC 会话可并发。主连接失效后下次请求重新建立，并移除属于本账号的失效 socket；不删除其他文件或未知 socket。调用禁止在复用失败时偷偷回退新 TCP 连接。仅新主连接建立时的临时握手拒绝可重试，最多四次，等待约 1/2/4 秒加随机延迟；密钥拒绝和主机公钥变化立即报错。主连接建立使用 `-N`，重试阶段没有发送业务操作；已发送 RPC 的响应丢失不会自动重放，需按已有部署记录确认结果后重跑。

新安装由 `bootstrap-public.sh` 创建私有目录。已有安装更新受信控制模块时，先执行：

```bash
sudo install -d -o livelife -g livelife -m 700 /opt/livelife/ssh
```

更新 `control/livelife/runtime.py` 和 `control/livelife/ssh_transport.py` 前保存备份，原子替换模块。下一次受限 RPC 即生效，不需重启 Nginx、后端或已有隧道。GitHub 特权控制程序继续来自 main；构建 SHA、产物校验、引用与发布 generation 规则不变。

排查时先查看 Actions 的具体阶段。`Exceeded MaxStartups` 表示 SSH 入口拒绝了尚未认证的新连接，不表示后端运行数量已达到上限。检查复用主连接时，以服务账号运行（将摘要替换为目录中实际 socket 名）：

```bash
sudo -u livelife ssh -p 1021 -S '/opt/livelife/ssh/c-<摘要>' -O check group5@8.130.213.80
```

重复控制查询应显示同一主连接 PID。关闭主连接只能针对确认空闲的项目控制 socket；会中断该连接上正在执行的会话，不能作为常规清理方式。空闲退出由 OpenSSH 自动完成。不要删除其他服务文件或为了测试重启课程机 SSH。

## 维护者安装与排查教程

先在课程机以 group5 使用已审查部署文件，运行 bootstrap-course.sh。脚本只更新 `/home/group5/livelife`，将固定工具安装到 build-tools，不需 Docker/sudo，不修改系统 APT/Python/npm。若 APT 镜像缺少本机缓存元数据中的版本，核对并刷新项目工具使用的元数据或使用有相同官方 SHA-256 的备用来源；不要绕过校验。

```bash
python3 ~/livelife/control/install-build-tools.py ~/livelife
~/livelife/build-tools/node/bin/node --version
~/livelife/build-tools/node/bin/node ~/livelife/build-tools/node/lib/node_modules/npm/bin/npm-cli.js --version
~/livelife/control-venv/bin/python -m supervisor.supervisorctl \
  -c ~/livelife/supervisor/supervisord.conf status build-worker
```

首次 build_submit 会由项目 Supervisor 启动 build-worker。工作流合入 main 后，检查 statuses:write 权限；现有 SSH 私钥和 known_hosts 不变。main 首次网页请求和网页开关的顺序见[网页维护](WEB_PREVIEW.md#维护者启用顺序)，成员教程见[测试入口](../docs/testing.md)。


控制请求与字段见[构建控制接口](CONTROL_API.md#构建控制接口)。

## 源码拉取锁排查

遇到 source.lock 或 shallow.lock 错误时，先查看队列、活跃 Git 进程与锁持有者。仅在确认没有相关运行任务后，由维护者在 source.lock 内备份并处理遗留锁；不能直接删除活跃锁。拉取超时后的进程组停止、锁清理范围和 stderr 回传由部署工具回归覆盖。
