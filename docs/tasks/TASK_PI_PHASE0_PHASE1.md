# Phase 0 & Phase 1 开发任务书（针对 DeepSeek 执刀）

## ⚠️ 纪律约束（违者重做）
1. **严格阅读并遵循 docs/ARCHITECTURE.md**：所有文件名、目录结构、数据表字段名、API 路由路径、HTTP 206 实现细节必须与 ARCHITECTURE.md 完全一致，严禁凭空自创！
2. **严禁过度重构，专注本阶段目标**：
   - 目标范围：创建后端核心工程骨架、数据库 ORM/连接层、HTTP 206 原画分块流、基础媒体扫描与 API 路由。
   - 不要跳步去写复杂爬虫或前端页面，先跑通后端最小可用闭环（MVP）。
3. **完成标准**：
   - 目录规范落地
   - 代码无语法错误，通过 python -m py_compile
   - 提供最少 1 个可直接执行的验证命令

## 任务分解
1. 创建后端目录骨架：
   - `server/app/__init__.py`
   - `server/app/core/config.py` (包含 Pydantic Settings，路径配置，端口等)
   - `server/app/core/database.py` (SQLite WAL 连接池与 SessionLocal)
   - `server/app/models/` (SQLAlchemy 模型：Video, Series, Actor, Tag, VideoActor, VideoTag, WatchHistory, ScraperCache，必须完全对齐 ARCHITECTURE.md 2.2)
   - `server/app/services/streaming.py` (完整实现 HTTP 206 Partial Content 分块流，对齐 2.3 伪代码)
   - `server/app/services/scanner.py` (基础媒体文件扫描服务，支持 mkv, mp4, avi, wmv 等)
   - `server/app/api/` (main.py, routers/media.py, routers/history.py, routers/system.py)
   - `server/requirements.txt`
   - `server/Dockerfile`
   - `docker-compose.yml`
