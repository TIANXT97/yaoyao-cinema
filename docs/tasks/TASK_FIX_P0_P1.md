# 夭夭影社（Yaoyao Cinema）P0 & P1 关键缺陷彻底根治任务书

请作为主力执刀医师（DeepSeek Flash / GLM / Opus 水准），对审查报告中指出的 **全部 P0 缺陷与核心 P1 缺陷** 进行外科手术式精修：

## 1. P0 阻断性缺陷根治
- **P0-1 安卓 API 基址与运行时配置**：
  - 在 `frontend/src/api/client.ts` 实现灵活基址：优先 `localStorage.getItem('yaoyao.apiBase')`，其次 `import.meta.env.VITE_API_BASE`，最后兜底当前页面的相对路径 `/api`。
  - 在 `frontend/src/views/SettingsView.vue` 中提供“NAS 服务器地址（API 基址）”设置项，支持用户输入（如 `http://192.168.31.235:9900/api`）并持久化。
  - 修复 `useNativePlayer.ts` 中的播放 URL 构造，确保在 Capacitor 原生模式下拼接正确的完整 NAS 地址。
- **P0-2 ScanResult 默认值与并发扫描 500**：
  - 完善 `server/models.py` 的 `ScanResult` 所有字段默认值；
  - 完善 `server/scraper/scanner.py` 中的并发状态返回。
- **P0-3 PlayerActivity 结果丢失**：
  - 在 `android/.../PlayerActivity.kt` 中重写 `finish()`，在 `finish()` 调用前执行 `sendResult()`，确保回传。
- **P0-4 原生播放器打通接入**：
  - 在 `frontend/src/views/VideoDetailView.vue`、`HomeView.vue` 等播放入口处，引入 `useNativePlayer`：若是原生环境（`isNative` 为 true），直接调起 `playVideo` 走 ExoPlayer 硬件硬解直出；若是 Web/PWA，走 CustomPlayer。

## 2. P1 关键数据缺陷根治
- **P1-5 镜像 URL 拼接 Bug**：修复 `server/scraper/sources/base.py` 中 `urlsplit` 逻辑，确保反爬镜像正确拼接。
- **P1-6 历史记录同秒多写导致重复**：优化 `server/services/history_service.py` 中的 `get_recent` 查询，使用窗口函数或去重。
- **P1-7 数据库唯一约束与并发安全**：在 `server/database.py` 中给 `actors(name)` 增加唯一索引；`get_or_create_*` 采用 `INSERT OR IGNORE` 安全模式。
- **P1-8 后台任务防 GC 与并发锁**：修复 `server/api/scraper_api.py`，维护强引用集合 `_background_tasks`；`pipeline.scrape_all` 加互斥锁。
- **P1-10 播放历史时长单位对齐**：统一全流程毫秒计算，禁止跨单位回退。

## 3. 验收标准
- 执行 `python3 tests/test_scraper.py` 确保测试通过；
- 执行 `python3 -m py_compile` 确保所有 Python 源码无错误；
- 在 `frontend/` 执行 `npm run build` 确保前端无错误打包成功，且同步至 `android/app/src/main/assets/public/`。
