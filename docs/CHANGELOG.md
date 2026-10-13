# 变更日志 (CHANGELOG)

本文档记录 **夭夭影社（Yaoyao Cinema）** 的关键功能迭代与历史版本演进。

---

## [v1.0.4] - 2026-10-13

### 修复
- **设置页白屏防护**：
  - 统计与刮削进度模板表达式升级为全链路安全可选链（`stats?.videos?.matched` 等），后端返回空或异常时优雅显示 0，彻底根绝未捕获 TypeError 造成的全屏死白崩溃 (#21)。
  - API 基址输入智能纠错：对绝对地址自动规整并补全 `/api` 后缀，避免 404 路由报错 (#21)。
- **安卓海报加载与 Mixed Content 根除**：
  - Capacitor 运行时协议由 `https` 调整为 `http`，WebView 与本地 NAS / 中继服务协议拉齐，彻底消除混合内容拦截 (#22)。
  - `LazyImage` 图片组件增加失败自动重试机制（自动重试 2 次并携带防缓存参数），耗尽后优雅展示破损占位图标 (#22)。
  - 完善单元测试矩阵（Vitest + @vue/test-utils 12 项用例全通）。
- **版本升格**：
  - 升格 Android 宿主版本号至 `versionCode 4`、`versionName "1.0.4"`。
  - 同步提升前后端及应用内检查版本为 `1.0.4`。

## [v1.0.3] - 2026-10-12

### 应用内更新与分发 (App Self-Update & Release)
- **应用内直连 GitHub 检查更新**：
  - 设置页实装「版本与更新」模块，直接请求 GitHub 官方开放 API（`https://api.github.com/repos/TIANXT97/yaoyao-cinema/releases/latest`）。
  - 支持语义化版本号比对，自动展示更新日志并提供 APK 下载链接。
  - 内置高速镜像加速通道（`ghfast.top`），国内网络环境无需代理亦可满速直接拉取 APK。
- **Android 构建版本升级**：
  - 升格 Android 宿主版本号至 `versionCode 3`、`versionName "1.0.3"`。
  - 同步提升后端与前端包版本为 `1.0.3`。
- **原生 APK 自动化构建流水线**：
  - 新增 GitHub Actions CI/CD 流水线（`.github/workflows/android-release.yml`），支持基于 Release Tag 触发原生编译并自动发布 APK 附件。

### 安全加固 (Security Hardening)
- **刮削图片防 SSRF 加固**：
  - 引入 `socket.inet_aton` 归一化层，阻断 Linux 环境下通过十进制、十六进制或点分缩写（如 `127.1`、`0x7f.1`、`2130706433`）伪造内网/回环 IP 的绕过攻击。
  - 在异步线程池中执行 `socket.getaddrinfo` 预解析，拦截指向内网私有地址的域名，且不阻塞主事件循环以保障切片流播放流畅。
  - 下载链路改用独立客户端并禁用自动重定向（`follow_redirects=False`），实现逐跳 Location 递归 SSRF 审查（最大 5 跳），防止 302 越权穿透至内网或云厂商元数据接口（`169.254.169.254`）。
  - 增加 15 MB 流式分块下载上限截断与 Pillow 30,000,000 像素解压上限，防御超大文件耗尽内存及像素解压炸弹。
  - 镜像回退策略剔除与失败主站域名相同的镜像条目，降低无效重试开销。

### 流媒体与云端直链 (Streaming & Alist Integration)
- **切片流断连优雅退出**：
  - 视频分块迭代器 `file_iterator` 捕获 `asyncio.CancelledError`、`ConnectionResetError`、`BrokenPipeError` 并静默终止迭代，消除播放器频繁拖拽 Seek 断流引起的服务端 traceback 刷屏。
- **Alist 云流超时熔断与内存缓存**：
  - 提取 `server/services/alist_service.py` 专用模块。
  - 实施 `ALIST_TIMEOUT = 4.0s` 请求硬超时控制与规范化 504 响应，阻断网盘冷启动与异常网络挂死 NAS 线程。
  - 建立 30s TTL 轻量内存直链缓存，有效过滤播放器短时高频探测、HEAD 请求与多次重试对 Alist API 的突发冲击。

### 元数据与刮削流水线 (Metadata & Scraper)
- **XML 1.0 非法字符清洗**：
  - 在 `nfo_source.py` 中引入 `_ILLEGAL_XML_CHARS` 正则，在 NFO XML 生成时自动剥除控制字符（如 `\x00-\x08\x0b\x0c\x0e-\x1f￾￿` 等），避免脏数据导致下游解析器抛出 `ParseError`。

### 移动端与客户端容器 (Mobile & Client)
- **Capacitor 原生网关自动回退**：
  - 前端增补 `isCapacitorNative()` 运行时检测，在 Android 原生 WebView / Capacitor 容器环境下自动兜底使用内网服务器网关 `http://192.168.31.235:9900/api`，解决未配置基址时出现的冷启动白屏。

### 治理与工作流
- 重构 `CLAUDE.md` 与 `AGENTS.md`，确立工位 PC 与 NAS 夭夭的三节点协作契约。
- 确立 PR 协作工作流：工位负责特性开发、静态自测并提 PR；PR 合并至 `main` 及 NAS 端部署由夭夭统一执行。
- 补齐开发指导与变更日志文档体系。

---

## [v1.0.1] - 2026-10-11

### 播放器与交互增强
- **原生播放器手势支持**：
  - 双击屏幕左/右侧实现快退/快进 10 秒。
  - 屏幕水平横向滑动实现进度精准拖拽，并显示时间浮层。
  - 进度条区域排除系统边缘手势，修复底部拖动冲突。
- **流媒体服务**：
  - `/api/stream/{id}` 补齐 HTTP `HEAD` 方法支持，优化 Safari 及外部嗅探器的首片分块探测。

### 历史记录与继续观看重塑
- **极简设计重构**：
  - 观看历史与“继续观看”视觉重构为纯白极简文字 + 进度条风格，彻底剔除冗余海报干扰。
  - 剧集归一化：多集连播时，整部剧严格只展示最后一次观看的剧集进度。
- **数据一致性**：
  - 支持观看历史与继续观看记录物理级级联彻底删除。

---

## [v1.0.0] - 2026-10-10

### 核心功能与架构落地
- **零转码直出**：
  - 基于 FastAPI + `aiosqlite` 实现 HTTP 206 Partial Content 高性能切片串流。
  - 播放全程 NAS CPU 占用趋近于 0%，依赖设备端 GPU 硬解。
- **极简海报墙与元数据刮削**：
  - 前端基于 Vue 3 + Tailwind CSS v4 构建通透纯白海报墙。
  - 多源刮削流水线（本地 NFO 优先，自动回写脱网持久化）。
  - 支持二级分类胶囊导航条（电影、剧集、动漫等）实时响应与过滤。
  - 默认开启剧集聚合展示与选集播放列表，消除单集海报堆叠。
- **Alist 云盘深度融合**：
  - 支持 `cloud://` 协议，通过 Alist 获取 302 签名直链直出播放。
  - 云端海报 302 直通与父级继承机制，免占用 NAS 上行带宽与存储空间。
- **跨平台与安卓原生硬解**：
  - PWA 模式支持 Safari / Edge 独立添加到主屏幕。
  - 集成 Capacitor 7.x 原生壳，接入 Media3 / ExoPlayer 1.5.1 硬解播放器内核。
- **生产容器化**：
  - 交付一体化 `docker-compose.yml`，打通宿主机媒体库挂载与 SQLite WAL 持久化。

