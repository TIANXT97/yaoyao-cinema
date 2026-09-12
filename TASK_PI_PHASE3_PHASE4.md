# Phase 3 & Phase 4 前端工程开发任务书（针对 DeepSeek 执刀）

## 绝对铁律纪律（违者重罚重做）
1. **严格阅读并遵循 docs/ARCHITECTURE.md 第 3 章（前端与 PWA 架构）与第 4 章**：
   - 设计风格：东方纯白极简通透（Anti-Slop Minimalist Editorial），纯白底色（#FFFFFF / #FAFAFA），呼吸感留白，精致极细边框（border-stone-100），禁止暗黑粗糙极客风。
   - 目录规范必须完全对齐 ARCHITECTURE.md 第 5 章目录树中的 `frontend/` 结构！
2. **技术栈要求**：
   - Vue 3 (Composition API / <script setup>) + Vite + Tailwind CSS + Pinia + Vue Router + Lucide Icons (或轻量 svg 图标)
   - 支持移动端、iPad 响应式适配与触控手势
3. **交付模块清单**：
   - 3.1 基础脚手架配置：`frontend/package.json`, `vite.config.ts`, `index.html`, `tailwind.config.js` / Tailwind v4 配置
   - 3.2 路由与状态管理：`src/router/index.ts`, `src/stores/video.ts`, `src/stores/player.ts`
   - 3.3 API 客户端：`src/api/client.ts`, `src/api/videos.ts`, `src/api/history.ts`, `src/api/scraper.ts`
   - 3.4 核心通用组件：
     - `src/components/layout/Navbar.vue` (纯白顶栏，极简搜索与导航)
     - `src/components/media/VideoCard.vue` (2:3 精致海报卡片，微阴影，右上角原画/时长角标，悬浮动效)
     - `src/components/media/VideoGrid.vue` (响应式瀑布流网格，支持未看/收藏/分类筛选)
     - `src/components/player/CustomPlayer.vue` (自研 HTML5 原画手势播放器：双击快进/后退 10s、垂直滑动音量/亮度、播放进度断点每 10s 自动上报)
   - 3.5 核心页面：
     - `src/views/HomeView.vue` (主页海报墙 + 最近播放 + 快速筛选)
     - `src/views/VideoDetailView.vue` (影片大图 Backdrop、演员头像网格、标签、一键原画直播)
     - `src/views/PlayerView.vue` (沉浸式全屏原画直解播放页)
     - `src/views/FavoritesView.vue` (主人私房收藏)
     - `src/views/HistoryView.vue` (播放历史与续播时间线)
     - `src/views/SettingsView.vue` (媒体库扫描与刮削控制台)
4. **编译与自测标准**：
   - 前端必须在本地运行 `npm run build` 打包成功，生成 `frontend/dist`，无任何 TypeScript / 语法错误。
