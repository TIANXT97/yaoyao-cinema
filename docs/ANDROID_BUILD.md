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
* **Release APK**：`android/app/build/outputs/apk/release/app-release-unsigned.apk`

---

## 4. 关键配置说明

1. **明文流量传输许可**（局域网 HTTP 直链播放）：
   * 配置文件位于 `android/app/src/main/res/xml/network_security_config.xml`。
   * 已显式放行内网 IP `192.168.31.*` 及局域网 HTTP 通信，确保在内网免 HTTPS 证书情况下正常加载海报与 206 字节流。

2. **硬件加速与画质直出**：
   * `AndroidManifest.xml` 中已开启 `android:hardwareAccelerated="true"`。
   * 原生播放器直接接管 SurfaceView，调用芯片 GPU 进行 4K H.264/HEVC 硬解，不产生任何 CPU 软解发热。
