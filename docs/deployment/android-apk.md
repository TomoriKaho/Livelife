# Android 测试包部署与维护（#28）

成员操作见[Android 开发与测试教程](../android-testing.md)，网页/后端的既有部署见[部署说明](../deployment.md)。这里只维护 Android 增量配置，不包含正式发布或 iOS。

## 工具和权限

课程机使用 /home/group5/livelife，Android 加入现有全项目双任务队列。分支代码运行在命名空间沙箱中，工具只读，只有任务目录和下载缓存可写；没有签名密钥、SSH 私钥或 GitHub Token。沙箱只提供一个虚拟用户记录，/proc 保持空文件系统；JDK 使用明确的只读库路径启动，避免依赖 /proc/self/exe。Gradle 不运行 daemon，最多两个 worker，堆内存约 1.5 GiB。

工具固定为 Node 24.13.0、npm 11.6.2、Capacitor core/android/cli 8.5.2、App 8.1.2、JDK 21.0.8+9、Gradle 8.14.3、AGP 8.13.0、SDK 36、Build Tools 36.0.0、最低 SDK 24。JDK 使用 Azul 官方包及固定 SHA-256；SDK 由 Google HTTPS 仓库校验清单验证；Gradle 验证官方 SHA-256。每个工具下载校验成功后立即写入 build-tools/android-tools.json，后续工具安装失败不会丢失已完成记录；此前已有但未记录的工具不会被虚构为重新校验过。npm 使用 npmmirror，Gradle 依赖优先阿里 Google/Central 镜像，官方源作为依赖下载的后备；锁定版本不因镜像改变。

在审查过的项目 checkout 中更新课程控制代码，然后：

```bash
python3 ~/livelife/control/install-android-tools.py ~/livelife
~/livelife/build-tools/jdk/bin/java -version
JAVA_HOME="$HOME/livelife/build-tools/jdk" \
  ~/livelife/build-tools/android-sdk/cmdline-tools/19.0/bin/sdkmanager \
  --sdk_root="$HOME/livelife/build-tools/android-sdk" --licenses
```

维护者阅读并接受 SDK 许可证；也可将本人已接受的 android-sdk-license 文件复制到该 SDK 的 licenses 目录。不要通过伪造接受记录跳过许可证。安装器本身不自动接受。安装完成后保留项目工具缓存，普通构建不重新下载 JDK/SDK。

公网机使用 /opt/livelife，新增 /opt/livelife/apks，继续由项目 HTTPS 443 分发。bootstrap-public 安装 qrcode[pil]==8.2；公网上只有受信校验、签名工具运行，不执行分支 Gradle、脚本或 APK。

课程机工具安装完成后，在公网机已安装控制程序的目录执行：

```bash
cd /opt/livelife/control
/opt/livelife/control-venv/bin/python install-android-signer.py /opt/livelife
sudo -u livelife /opt/livelife/control-venv/bin/python setup-android-signing.py /opt/livelife
```

install-android-signer 通过既有受限 SSH，从课程机读取校验过的 JDK/Build Tools，无需公网机再次下载。若以 root 安装，确保 build-tools 可被 livelife 执行、credentials 归 livelife 且目录权限 700。setup-android-signing 只创建测试密钥；已存在则验证并复用，不自动更换。android-test.jks、android-test.pass 权限 600，android-test.sha256 记录公开证书指纹。私钥和密码不进入 GitHub、产物、页面或日志。维护者另行保存受保护的私钥备份，丢失密钥会影响覆盖升级。

## 控制接口及发布顺序

现有受限 SSH JSON RPC 增加：

| op | 输入与结果 |
|---|---|
| apk_reserve | environment、branch、sha、generation、target、mode、explicit、force；分配版本并持久保留后端，返回内置配置 |
| apk_lookup | environment；返回本次状态、上一成功包及显式选择 |
| apk_publish_built | apk_id、job；从课程机读取已通过的未签名 APK，校验、签名、发布 |
| apk_fail | apk_id、error；记录失败、释放候选引用 |
| apk_release | environment、generation；关闭入口并释放该环境包，main 禁止释放 |

课程内部 build_submit 增加 component=android 和 config；build_artifact 增加 component=android，仍严格匹配已成功的任务及 SHA。android_tools 仅传输固定项目工具目录，是维护接口，不提供任意文件读取。

受信控制程序只从 main 检出。自动链路必须有经 GitHub 来源校验且真正通过的课程机构建结果；fork、旧提交、关闭 PR 和非法工作流不自动部署。手动控制也从 main 执行，client_ref 仅指定沙箱构建源码。

公网机先持久化候选配置、versionCode 和 apk:ID 引用，再提交构建。重复通知复用有效记录；明确重跑/手动构建分配新版本。签名阶段在项目文件锁内串行执行，验证包名、versionCode、versionName、SDK、内置配置、大小、校验值和最终签名指纹。HTML/状态/二维码不缓存；APK 文件名不可变，提供下载类型与 Content-Disposition。

新包准备完成后，更新数据库候选和网关并提交；旧任务由 generation 和关闭墓碑拒绝。失败保留原 current 记录，候选标记失败。中断留下 pending 记录，两小时后恢复/清理释放它；文件删除在状态提交后执行，重复清理安全。关闭后 build-ID 状态仍可返回 released，手机据此禁用接口测试。

单 APK 上限 64 MiB，展开上限 256 MiB、10,000 条目，拒绝路径穿越、链接、特殊文件、重复条目和配置不一致。APK 物理存储预算 2 GiB，不包含工具目录；不足先回收已到期文件，仍不足拒绝新包。

## 启用和排查

新增 Repository Variable：LIVELIFE_ANDROID_ENABLED=true；初始关闭。没有新的 Actions 私钥或签名 Secrets，复用现有受限 SSH 身份。

1. 审查并安装课程机及公网机增量控制程序，备份原控制文件、网关和状态；使用项目目录和既定端口。
2. 完成工具、许可证和测试密钥配置，验证沙箱未签名构建、签名校验和 HTTPS 下载。
3. 工作流合入 main 后开启开关，运行 main 的 Frontend build request。
4. 确认 Android checks、下载页、QR 和 APK 配对；再验证前端 PR、混合 PR、后端-only 手动构建、关闭和重开。
5. 成员按真机清单验收，记录版本。正式评审及合并由成员完成。

暂停自动构建可将开关设为 false，既有文件/后端不会因此立即删除。开关关闭期间没有 Android 定期核对，恢复后先运行 collect/reconcile；涉及永久撤销的 PR 需维护者用 apk_release 清理。公开下载不提供业务鉴权；本任务只接 hello，后续业务权限在服务端实现。

Android checks 失败看 Preview environments 的课程日志和错误阶段。只是重复运行控制通知可能复用旧任务；强制重建使用 android-build。source.lock 等待 10 分钟、队列等待 30 分钟、单命令 20 分钟、任务预算 30 分钟；不要直接删除活跃锁或关闭未确认的后端。

## 实施记录

2026-10-07：已在 28-android-test-apk 分支实现 Android 工程、原生配置、队列、受信签名、独立引用、下载页、二维码和自动/手动控制。尚未合入 main，LIVELIFE_ANDROID_ENABLED 尚未开启；完整自动链路与真实 APK 发布结果将在本任务验证后补记。成员真机验收待执行，不将自动构建通过记为真机通过。
