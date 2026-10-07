# Android 开发、下载与测试教程

本文介绍 #28 的 Android 测试包。网页、APK 和后端各有独立版本；网页测试通过不能代替手机验收。完整 Actions 是否已启用，以[维护者实施记录](deployment/android-apk.md#实施记录)为准。

## 1. 根据分工准备环境

只开发 Vue 页面：安装 Node.js 24.13.0 / npm 11.6.2，按[工程规范](engineering.md#目录与启动命令)启动网页即可。只验收 APK：有 Android 手机和浏览器即可，不需要 Android Studio。

负责原生适配、插件、权限和调试的成员安装 Android Studio 2025.2.1 或更新的稳定版。Mac 选择与 CPU 匹配的 Apple Silicon/Intel 安装包。首次启动完成 SDK 安装向导，再进入 SDK Manager 安装：

- Android SDK Platform 36；
- Android SDK Build-Tools 36.0.0；
- Android SDK Platform-Tools（含 adb）；
- Android SDK Command-line Tools；
- 没有手机时安装 Android Emulator，并在 Device Manager 创建模拟器，Apple Silicon 选择 ARM64 镜像。

项目使用 JDK 21、Gradle 8.14.3、Android Gradle Plugin 8.13.0。在 Android Studio → Settings → Build, Execution, Deployment → Build Tools → Gradle 中选择 JDK 21；如果自带 JDK 不是 21，通过下载 JDK 或本地路径指定。不要为了本机 IDE 版本随意升级仓库的 Gradle、SDK 或 Capacitor 版本。

Mac 的 SDK 默认位于 `~/Library/Android/sdk`。Android Studio 可生成未提交的 android/local.properties；终端构建需设置 ANDROID_HOME 和 JAVA_HOME，例如：

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
# 换成你实际安装的 JDK 21 路径；先确认 java -version 为 21。
export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"
java -version
adb version
```

Android Studio 内置 JDK 不一定被 java_home 识别，可直接指定其真实路径。Windows/Linux 从 SDK Manager 查看 SDK 路径，配置相同变量。使用系统 Gradle 无需安装：本地命令使用仓库提交的 Gradle Wrapper。

## 2. 本地运行到手机或模拟器

在 frontend/.env.local 中配置手机可访问的后端，示例：

```dotenv
VITE_API_BASE_URL=https://192.144.253.40/api/staging/
```

该地址是共享测试后端，会随 main 更新。APP 内 localhost 指手机自身，不是开发电脑。本地 HTTP 网络例外不在本任务开启；使用项目 HTTPS 入口。业务登录、定位和推送尚未实现，页面大部分是明确标注的样例。

```bash
cd frontend
npm ci
node --test scripts/*.test.mjs
npm run android:sync
npm run android:open
```

android:sync 会构建 preview 网页并执行 Capacitor sync；修改网页后重新同步，Android Studio 里的原生工程才会包含最新页面。不要设置 VITE_WEB_PREVIEW=true，否则资源会指向网页专用的远程构建路径。

在 Android Studio 打开 frontend/android，等待 Gradle 同步完成，选择设备后点击 Run。也可以：

```bash
npm run android:debug
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

真机：在手机“关于手机”连续点击版本号开启开发者选项，打开 USB 调试，用数据线连接并在手机确认电脑的调试授权。`adb devices` 应显示设备为 device；unauthorized 需要在手机确认。模拟器在 Device Manager 点击启动后会出现在设备列表中。

本地 debug 包名为 io.github.tomorikaho.livelife.dev.local，名称“Livelife 本地调试”；团队分发包名为 io.github.tomorikaho.livelife.dev，名称“Livelife 测试”。两者可以共存，签名和数据独立。本地 debug 由 Android 工具自动签名，分发包由腾讯云专用测试密钥签名；开发者不需要索取服务器私钥。

查看原生日志：Android Studio 的 Logcat 选择设备和应用；也可执行 `adb logcat`。在电脑 Chrome 的 chrome://inspect/#devices 调试本地 debug WebView。团队 release 测试包不开放远程 WebView 调试，问题用版本、现象及日志记录。

## 3. PR 的自动测试包

前端/原生相关 PR 创建、更新、重开后，现有 Frontend build request 发出请求；受信控制器在网页检查通过后调度课程机 Android 构建。后端配套未就绪时等待后端完成或定期核对，不占用 Android 构建槽位。

流程：课程机拉取 SHA → 检查前端 → 构建网页 → Capacitor 同步 → Gradle 生成未签名 APK → 腾讯云读取产物并校验 → 签名并验证 → 发布下载页 → 更新 PR 的同一条自动评论。Android checks 表示 APK 检查/签名/发布结果，实际测试日志在 Preview environments 的 course-build-logs 中。

默认配对：

| 代码变化 | 后端 |
|---|---|
| 只有前端 | main 共享 staging |
| 前后端同时变化 | 同分支已成功部署的配套后端，固定 SHA |
| 已指定联调目标 | 保留所选固定 SHA，另一 PR 更新不会自动改变 APK |
| 只有后端 | 不自动打包，按下一节手动触发 |

PR 评论显示下载页、二维码、versionCode、客户端 SHA、后端模式/SHA/API 和有效期。前端网页链接与 APK 下载页是两个入口；在手机上扫描二维码，进入下载页再下载 APK。

稳定入口：main 为 `https://192.144.253.40/downloads/android/staging/`，PR 为 `/downloads/android/pr-编号/`。每次构建还有独立的 build-ID 下载页。文件名和校验值对应具体安装包，稳定页更新不会改变已经安装的 APK。

## 4. 手动选择客户端与后端

仓库 → Actions → Preview environments → Run workflow，工作流分支选择 main；operation 选择 android-build。

| 输入 | 填法 |
|---|---|
| client_ref | 客户端分支、Tag 或完整 SHA，默认 main |
| frontend_pr | 希望记录下载入口的 PR 编号；后端-only PR 也可填；留空生成独立临时下载页 |
| backend_target | default 沿用配对；staging 使用共享后端；pr-42 解析 #42 已部署版本；be-完整SHA 使用已有固定实例 |
| frontend_branch | Android 手动构建无需填写 |

例如 #42 只有后端改动：client_ref=main、frontend_pr=42、backend_target=pr-42。点击运行，系统确认 #42 是同仓库打开的 PR、其当前后端版本已经部署，再固定该 SHA。结果显示在本次 Actions Summary 及 #42 自动评论里。

指定 pr-42 不意味着跟随 #42：后续 #42 更新后要重新运行，才能得到连接新版后端的新 APK。default 保留已显式指定的目标。staging 跟随 main；实际 hello 响应 SHA 会显示在 APP 内。

不能为 fork 自动取得签名或部署权限；维护者先将要验证的代码导入同仓库分支，再按普通流程构建。

## 5. 下载、安装和覆盖升级

1. 手机扫码或打开 PR 下载页，核对客户端 SHA、后端和有效期。
2. 点击“下载 APK”。浏览器可能提示安装包风险或需要授权：在系统设置中允许当前浏览器“安装未知应用”。测试结束后可关闭该授权。
3. 打开下载的文件并安装“Livelife 测试”。Android 7/API 24 是工程最低版本，设备 WebView、根证书和地图性能仍需实际验证。
4. 在“我的 → 帮助与反馈 → 接口连通性测试”核对 versionCode、客户端 SHA、后端模式及加载时 SHA，再点击测试连接。
5. 记录实际响应后端 SHA 和测试步骤，避免只依据下载页判断手机里已经更新。

所有 PR 共用一个团队测试应用。新 APK 的 versionCode 全局递增，正常覆盖安装会保留该应用数据。不同 PR 不能作为两个独立测试应用同时安装；本地 .local 调试包可以与它共存。

旧 APK 可能比手机上已有包的 versionCode 小，系统会拒绝降级。需要切回旧代码时，手动选择旧客户端 SHA 重新构建，得到更大的 versionCode。不要把卸载重装当作无损切换：卸载会清除应用数据。若遇到签名不一致，先确认安装的是本地 debug 还是团队包，不要索取或重建团队签名私钥。

默认测试包 7 天到期；main 最新成功包永久保留，被替换的旧 main 包再保留 7 天。PR 关闭/合并会撤销该 PR 的入口并释放包。手机不会自动卸载，到期或关闭后接口测试明确提示失效，重新下载新包；内置样例页面仍可查看。

安装包引用与网页引用独立，不根据访问人数计算。仍有效的包保留固定后端；释放最后一份引用后，后端经过宽限期再清理。

## 6. 失败、重跑与上一成功包

打开 PR 的 Android 状态及 Preview environments 日志，区分排队、依赖安装、Gradle、产物校验、签名与发布失败。本次失败时，页面和评论保留上一成功包，并明确它不代表最新提交。

- 自动请求失败：重跑原 Frontend build request 的全部 jobs，或在该分支手动运行 Frontend build request，再查看 Preview environments。
- 想强制重新生成 APK：使用上一节 android-build；版本号会递增。
- 只重跑 Preview environments 的旧自动通知，可能复用原请求/任务；不要把它当作“强制重新构建”。
- 排队超过 30 分钟会失败；任务命令最多 20 分钟、整体预算 30 分钟；源码锁等待最多 10 分钟。日志会说明原因，确认资源和下载条件后重新发起。
- 后端没有部署成功时不能默默换成 staging；先修复后端或主动选择可用目标。
- 下载页不可用或 APK 状态读取失败时，先检查网络、有效期和 PR 是否已关闭，不通过关闭版本校验掩盖问题。

Actions 附件只保存日志和版本/校验记录 7 天；APK 从下载页分发，不作为 GitHub Artifact 副本。本任务不创建正式 Release。

## 7. 真机验收记录

由另一名成员在 PR 评论中填写，未执行项目写“未测”，不要用网页或模拟器结果替代真机结果：

```text
设备 / Android / WebView：
测试日期：
versionCode / APK SHA-256：
客户端 SHA / 后端模式 / 加载时 SHA / 实际响应 SHA：
安装、覆盖升级：
启动、字体、图片、许可证入口：
地图 2D / 3D、拖动缩放、建筑与活动详情：
返回键关闭弹层、页面返回、顶层退出：
安全区、键盘弹出与收起：
真实 hello、断网/错误提示、过期提示：
结果及未测项：
```

发现问题附上复现步骤和版本；构建成功和 AI 自查不替代成员正式评审。
