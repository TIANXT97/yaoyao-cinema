# 安卓原生构建指南 (Capacitor + ExoPlayer)

本文档面向需要在工位或本地环境构建打包 **夭夭影社安卓客户端（APK）** 的开发者。

---

## 1. 架构与依赖概述

夭夭影社安卓客户端采用 **Capacitor 7.x 原生 WebShell + Media3/ExoPlayer 1.5.1 硬解内核** 的混合架构：
* **Web UI**：Vue 3 单页应用构建后的静态产物（`frontend/dist/`）。
* **原生播放器容器**：`android/app/src/main/java/com/yaoyao/cinema/PlayerActivity.kt`。
* **通信插件**：`NativePlayerPlugin.kt`，负责从 Vue 端接收视频播放直链并拉起原生全屏硬解播放器。

---

## 2. 环境前置要求

* **JDK**：OpenJDK 21 或更高（`compileOptions` 与 `kotlinOptions` 目标锁定为 Java 21）。
* **Android SDK**：
  * `compileSdkVersion`: 35
  * `targetSdkVersion`: 35
  * `minSdkVersion`: 23 (Android 6.0+)
* **Node.js**：v20+ / npm v10+

---

## 3. 完整构建步骤

### Step 1. 前端构建与静态产物同步
在执行安卓构建前，必须确保前端代码已完成最新构建并同步进 Capacitor assets：

```powershell
# 1. 编译前端生产产物
cd frontend
npm install
npm run build
cd ..

# 2. 同步静态文件到 Android 原生目录 (android/app/src/main/assets/public)
npx cap sync android
```

### Step 2. 原生 APK 打包

进入 `android/` 目录执行 Gradle 构建：

```powershell
cd android

# 构建 Debug 版本 (用于工位连接调试或模拟器运行)
.\gradlew.bat assembleDebug

# 构建 Release 版本
.\gradlew.bat assembleRelease
cd ..
```

构建生成的 APK 文件位于：
* **Debug APK**：`android/app/build/outputs/apk/debug/app-debug.apk`
* **Release APK**：`android/app/build/outputs/apk/release/app-release.apk`（若未配签名则生成 `app-release-unsigned.apk`）

---

## 4. APK 签名规范与踩坑记录 (Release Signing)

### 4.1 签名必要性：解析软件包时出现问题 (33) `packageInfo is null`
* **现象**：从 Release 下载的未签名 APK（`app-release-unsigned.apk`）在 Android 11+ 设备上安装时，系统安装器直接报错：`解析软件包时出现问题。(33) 详细信息: packageInfo is null`。
* **原因**：现代 Android 核心安全机制要求必须包含合法的 V2/V3 完整性签名块，缺省签名或纯 V1 签名的 Release APK 会被系统安装器底层校验直接拒绝并判定包信息无效。
* **规避**：发版产物必须通过正式 Keystore 进行 Release 签名（`signingConfig signingConfigs.release`），严禁向用户分发未签名的 APK。

### 4.2 Gradle 多工程相对路径解析避坑
在 Gradle 多项目架构下，`android/app/build.gradle` 属于子工程：
* `file(path)` 默认以 `android/app/` 为基准目录。
* CI 环境若将密钥恢复至 `android/release.keystore`（根目录），传递环境变量 `ANDROID_KEYSTORE_PATH="release.keystore"` 会导致 `file(...)` 找不到文件，抛出：
  ```
  SigningConfig "release" is missing required property "storeFile".
  ```
* **稳健写法**：
  在 `android/app/build.gradle` 中优先通过 `rootProject.file(...)` 解析，若不存在再回退到 `file(...)`；同时在 GitHub Actions 中将密钥同时双写到 `android/` 与 `android/app/`，确保双重保险。

---

## 5. GitHub Actions 云端自动构建与发版 (推荐)

仓库已集成 `.github/workflows/android-release.yml`，无需在工位配置重量级 Android SDK，即可在云端全自动打包装箱：

### 触发方式 1：打 Tag 自动发版
当项目需要发版时，只需推送版本标签：
```bash
git tag v1.0.3
git push origin v1.0.3
```
GitHub Actions 会自动：
1. 检出代码并安装 Node.js 20 与 OpenJDK 21 环境；
2. 构建前端单页产物并执行 `npx cap sync android`；
3. 执行 `./gradlew assembleRelease` 编译原生 APK；
4. 自动生成 GitHub Release 并将 `yaoyao-cinema-v1.0.3.apk` 作为附件资产挂载发布。

### 触发方式 2：使用 gh CLI 手动触发流水线
随时在工位触发云端编译：
```powershell
& 'E:\AI工具\gh\bin\gh.exe' workflow run android-release.yml -f tag_name=v1.0.3
```

---

## 6. 关键配置说明

1. **明文流量传输许可**（局域网 HTTP 直链播放）：
   * 配置文件位于 `android/app/src/main/res/xml/network_security_config.xml`。
   * 已显式放行内网 IP `192.168.31.*` 及局域网 HTTP 通信，确保在内网免 HTTPS 证书情况下正常加载海报与 206 字节流。

2. **硬件加速与画质直出**：
   * `AndroidManifest.xml` 中已开启 `android:hardwareAccelerated="true"`。
   * 原生播放器直接接管 SurfaceView，调用芯片 GPU 进行 4K H.264/HEVC 硬解，不产生任何 CPU 软解发热。
