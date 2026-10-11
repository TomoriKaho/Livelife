# Android 测试包分发维护

本文维护原生配置、课程机工具、测试签名、发布和恢复。下载安装、本地调试见[Android 工程说明](../frontend/android/README.md)，真机验收见[测试入口](../docs/testing.md#android-测试包操作)，启用证据见[部署入口](../docs/deployment.md#当前实施状态)。正式发布及 iOS 另行安排。

## 原生配置契约

分发包内置 schema_version=1 的 native-config.json：apk_id、build_id、frontend_sha、version_code、version_name、environment、api_base_url、backend_mode、backend_sha、status_url、expires。build_id 为 apk-加32位部署ID；versionCode 由公网机单调分配，分发包名固定 io.github.tomorikaho.livelife.dev，本地 debug 使用 .local 后缀。

原生来源为 https://localhost；hello CORS 允许该来源，并暴露 X-Livelife-Backend-SHA。网页配置仍要求同源，原生配置仅接受构建指定的公开 HTTPS origin。staging 跟随 main，own/fixed 固定后端 SHA；没有可用配置时不回退 localhost。启动、恢复前台和接口测试前读取独立安装包状态，失败或过期时停止接口测试，但内置样例页面可用。安装包引用独立于网页和浏览器在线人数。启用证据见[当前实施状态](../docs/deployment.md#当前实施状态)，真机步骤见[测试说明](../docs/testing.md#真机验收记录)。

## Android 工具和权限

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

## 发布顺序与恢复

控制请求与字段见[Android 控制接口](CONTROL_API.md#android-控制接口)。

受信控制程序只从 main 检出。自动链路必须有经 GitHub 来源校验且真正通过的课程机构建结果；fork、旧提交、关闭 PR 和非法工作流不自动部署。手动控制也从 main 执行，client_ref 仅指定沙箱构建源码。

公网机先持久化候选配置、versionCode 和 apk:ID 引用，再提交构建。重复通知复用有效记录；明确重跑/手动构建分配新版本。签名阶段在项目文件锁内串行执行，验证包名、versionCode、versionName、SDK、内置配置、大小、校验值和最终签名指纹。HTML/状态/二维码不缓存；APK 文件名不可变，提供下载类型与 Content-Disposition。

新包准备完成后，更新数据库候选和网关并提交；旧任务由 generation 和关闭墓碑拒绝。失败保留原 current 记录，候选标记失败。中断留下 pending 记录，两小时后恢复/清理释放它；文件删除在状态提交后执行，重复清理安全。关闭后 build-ID 状态仍可返回 released，手机据此禁用接口测试。

单 APK 上限 64 MiB，展开上限 256 MiB、10,000 条目，拒绝路径穿越、链接、特殊文件、重复条目和配置不一致。APK 物理存储预算 2 GiB，不包含工具目录；不足先回收已到期文件，仍不足拒绝新包。

## Android 启用和排查

新安装时先配置工具及签名，再将 Repository Variable `LIVELIFE_ANDROID_ENABLED` 设为 true。现有启用证据见[当前实施状态](../docs/deployment.md#当前实施状态)。没有新的 Actions 私钥或签名 Secrets，复用现有受限 SSH 身份。

1. 审查并安装课程机及公网机增量控制程序，备份原控制文件、网关和状态；使用项目目录和既定端口。
2. 完成工具、许可证和测试密钥配置，验证沙箱未签名构建、签名校验和 HTTPS 下载。
3. 工作流合入 main 后开启开关，运行 main 的 Frontend build request。
4. 确认 Android checks、下载页、QR 和 APK 配对；再验证前端 PR、混合 PR、后端-only 手动构建、关闭和重开。
5. 成员按真机清单验收，记录版本。正式评审及合并由成员完成。

暂停自动构建可将开关设为 false，既有文件/后端不会因此立即删除。开关关闭期间没有 Android 定期核对，恢复后先运行 collect/reconcile；涉及永久撤销的 PR 需维护者用 apk_release 清理。公开下载不提供业务鉴权；当前只接 hello，后续业务权限在服务端实现。

Android checks 失败看 Preview environments 的课程日志和错误阶段。只是重复运行控制通知可能复用旧任务；强制重建使用 android-build。source.lock 等待 10 分钟、队列等待 30 分钟、单命令 20 分钟、任务预算 30 分钟；不要直接删除活跃锁或关闭未确认的后端。
