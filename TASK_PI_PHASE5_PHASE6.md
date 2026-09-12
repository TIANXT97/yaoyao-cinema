# Phase 5 & Phase 6 PWA 与安卓原生封装任务书（针对 DeepSeek 执刀）

## 绝对铁律纪律（违者重罚重做）
1. **严格阅读并遵循 docs/ARCHITECTURE.md 第 3.3 节（PWA）与第 4 章（安卓原生封装）**：
   - 严禁凭空发明不存在的路径或配置项！
   - PWA 必须配置完整的 manifest、图标支持、Safari iOS 专属 meta（apple-mobile-web-app-capable, apple-mobile-web-app-status-bar-style: default 纯白），实现苹果无框脱壳。
   - 安卓端基于 Capacitor 架构，提供完整的项目结构、配置以及 NativePlayerPlugin 桥接定义。
2. **交付模块清单**：
   - **Phase 5 (PWA)**:
     - `frontend/public/manifest.webmanifest`（对齐 3.3 规范，名称"夭夭影社"，display: "standalone"，theme_color/background_color: "#FAFAFA" / "#FFFFFF"）
     - 优化 `frontend/index.html`：加入 iOS 视口安全区 `viewport-fit=cover`，PWA 全套 meta 标头，apple-touch-icon 引入
     - 生成优雅的 SVG 矢量应用图标（`frontend/public/icon.svg` 及相应各尺寸占位）
     - 引入 Service Worker / 离线缓存支持
   - **Phase 6 (安卓原生封装)**:
     - 在工程根目录下建立 `android/` 或配置 Capacitor 根工程结构
     - `capacitor.config.ts`：配置 appId `com.yaoyao.cinema`，appName `夭夭影社`，webDir `frontend/dist`，配置 cleartext / 局域网混合内容支持
     - 安卓原生骨架：`android/app/src/main/java/com/yaoyao/cinema/` 下的 `MainActivity.kt` 与 `NativePlayerPlugin.kt`（对齐 4.2 节原生 ExoPlayer/Media3 启动与播放逻辑）
     - `android/app/src/main/AndroidManifest.xml`：配置全屏主题、硬件加速、网络权限 `INTERNET`、`ACCESS_NETWORK_STATE` 与媒体直解权限
     - 安卓构建脚本与依赖声明（`build.gradle`）
   - **自动化集成与容器交付**：
     - 更新根目录 `docker-compose.yml` 与 `server/Dockerfile`，将编译好的 `frontend/dist` 直接挂载或打入镜像，让 NAS 启动单容器即同时拥有 API 与纯白通透前端 Web/PWA！
3. **自测验收**：
   - 前端重新 `npm run build` 确保 PWA 相关配置与编译 100% 成功；
   - 安卓工程目录完整且语法/代码无低级拼写错误；
   - Docker 编排配置可用性检查。
