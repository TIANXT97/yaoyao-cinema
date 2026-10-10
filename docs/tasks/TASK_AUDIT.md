# 夭夭影社（Yaoyao Cinema）全案深度法医级审查任务书

请作为最严格的代码审查法医专家（DeepSeek Flash / Claude Opus 水准），对当前仓库进行全景穿透式静态走查与实弹运行测试：
1. **契约与架构对齐度（Single Source of Truth）**：
   - 检查 `server/` 所有接口实现与 `docs/ARCHITECTURE.md` 是否存在未处理的入参/出参差异或隐藏 bug。
   - 检查 HTTP 206 Partial Content 流（`server/api/stream.py`）是否处理好了边界条件（如 Safari 探测 `bytes=0-1`、超出范围 416、大文件分块内存溢出、连接提前断开 ClientDisconnect 异常防爆）。
2. **刮削与数据一致性（Scraper Pipeline）**：
   - 检查多源爬虫超时、死循环、空指针、NFO 正则漏抓、非法 XML 转义字符。
   - 检查图片下载网络异常是否会挂起阻塞整个扫描流程。
3. **前端与 PWA 健壮性**：
   - 检查前端静态编译结果 `frontend/dist` 是否真能独立服务，是否存在硬编码本地 localhost 或写死端口导致跨设备无法访问的问题。
   - 检查 API 基础地址（`VITE_API_BASE`）与相对路径处理。
4. **安卓 Capacitor 原生工程审查**：
   - 检查 AndroidManifest.xml、build.gradle 语法与依赖配置，原生插件签名一致性。
5. **实战运行验证**：
   - 直接运行 Python 端到端模拟测试，找出所有隐患并列出修复建议。
