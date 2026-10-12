# CLAUDE.md —— 夭夭影社编码 Agent 工作手册

> 专为 **工位 Claude** 编写的代码实操 SOP。  
> 跨项目通用机器级规范已由全局 `E:\AI工具\claude-run\CLAUDE.md` 约束，本项目文档聚焦**夭夭影社仓库级架构、规范与避坑法则**。

---

## 1. 项目概况与核心架构

**夭夭影社（Yaoyao Cinema）**：运行在家庭飞牛 NAS（`192.168.31.235:9900`）上的私人原画海报墙影院系统。

**技术栈**：
```
后端    FastAPI 0.115+  +  SQLite WAL (aiosqlite)
前端    Vue 3 + Tailwind CSS v4 + Pinia + Vue Router + Vite
安卓    Capacitor 7.x + Media3 / ExoPlayer 1.5.1
部署    Docker 单容器 yaoyao-cinema:latest (`docker-compose.yml`)
```

**核心设计哲学**：**零转码直出**。NAS 仅负责高速切片吐字节流，解码与画质呈现全部交给播放终端 GPU 硬解。

---

## 2. 职责分工与节点边界

| 节点 | 角色 | 动作边界 |
|---|---|---|
| **工位 PC** (`DESKTOP-DTE8QPT`) | **代码开发** | ✅ 编辑代码（后端 Python / 前端 Vue / 安卓 Kotlin）<br>✅ 静态检查（`npm run type-check`、`pytest --collect-only`）<br>✅ Git commit / push<br>❌ **不干**：本地起 uvicorn 跑全套后端（无本地媒体库）、本地 docker build/run |
| **NAS** (`192.168.31.235`) | **真实运行** | ✅ 真实环境构建与部署 (`docker compose build / up`)<br>✅ 容器生命周期维护、数据库迁移实际执行<br>✅ 端到端 curl / 链路健康检查（由老板或 NAS 夭夭 agent 运行） |

---

## 3. 工位标准开发工作流

在仓库根目录下执行所有操作：

### Step 1. 同步代码
```bash
git fetch origin main
git status
```

### Step 2. 修改代码与开发
按需修改代码：
* 后端：`server/`（API 路由在 `server/api/`，业务在 `server/services/`，刮削在 `server/scraper/`）
* 前端：`frontend/src/`（组件、页面、路由、Pinia Store）
* 安卓：`android/app/src/main/java/com/yaoyao/cinema/`

### Step 3. 静态语法检查（工位验证）
工位只做静态分析，不启动重量级真实环境：
```powershell
# 后端语法与用例收集检查
pytest --collect-only

# 前端类型检查（进入 frontend 目录执行）
cd frontend
npm run type-check
cd ..
```

### Step 4. Git 提交与推送
* commit 规范：`type(scope): 中文简述`
* 推送协议：原生 SSH (`git@github.com:TIANXT97/yaoyao-cinema.git`)
```bash
git add <修改文件>
git commit -m "feat(stream): 支持新的切片预载策略"
git push origin main
```

### Step 5. 汇报话术（标准降级规范）
push 完成后，**不要**自行登录 NAS 构建发版。统一汇报并输出标准提示：
> ✅ push 完成。是否要 NAS 部署？默认 **否**。

---

## 4. NAS 按需部署与发版（仅在老板要求时执行）

当老板明确发出部署指令时，执行部署链：

```powershell
# 1. 触发 NAS 拉取最新代码并重新构建启动容器（永远指定服务名）
ssh nas 'cd /vol1/1000/vibe-projects/yaoyao-cinema && git pull && docker compose build yaoyao-cinema && docker compose up -d yaoyao-cinema'

# 2. 验证容器健康状态
ssh nas 'curl -s http://127.0.0.1:9900/api/system/health'
```

---

## 5. 数据库迁移 SOP（绝对红线）

SQLite 数据库文件位于 NAS 宿主机 `/vol1/1000/vibe-projects/yaoyao-cinema/data/yaoyao.db`。

1. **迁移写法规范**：  
   必须在 `server/database.py:init_schema()` 中使用 **PRAGMA 查列 + ALTER TABLE 追加**。  
   ⚠️ **严禁使用 `ALTER TABLE ADD COLUMN IF NOT EXISTS`**（SQLite 不支持该语法，会导致启动 syntax error 并陷入 crash loop）。

   ```python
   # 正确示例：
   cols = {row["name"] for row in await self.fetchall("PRAGMA table_info(videos)")}
   if "new_column" not in cols:
       await self.execute("ALTER TABLE videos ADD COLUMN new_column TEXT DEFAULT ''")
   ```

2. **部署前备份**（涉及 schema 变更时）：
   ```bash
   ssh nas 'cp /vol1/1000/vibe-projects/yaoyao-cinema/data/yaoyao.db /vol1/1000/vibe-projects/yaoyao-cinema/data/yaoyao.db.bak.$(date +%Y%m%d_%H%M%S)'
   ```

---

## 6. 核心避坑指南

* **坑 #1：修改 NAS 代码不生效**  
  代码打包在 Docker 镜像内（bind mount 仅挂载了 `data/` 和 `/media/`）。改动必须执行 `docker compose build yaoyao-cinema` 重构镜像方可生效。
* **坑 #2：apt 安装 ffmpeg 缓慢卡死**  
  `server/Dockerfile` 中已硬编码清华大学镜像源（`mirrors.tuna.tsinghua.edu.cn`），**绝对不要改回 `deb.debian.org`**。
* **坑 #3：新增 API 接口 404**  
  在 `server/api/` 新增路由后，必须在 `server/api/router.py` 中引入并通过 `api_router.include_router(...)` 显式挂载。
* **坑 #4：Docker 操作影响无关容器**  
  执行 docker compose 必须始终携带服务名 `yaoyao-cinema`，严禁裸跑 `docker compose up -d`。
* **坑 #5：Git 历史安全红线**  
  禁止 `--force` 或 `reset --hard` 覆盖 main 分支历史。唯一例外见 `AGENTS.md` §3.4「凭据与敏感资产清洗」紧急豁免。

---

## 7. 文档索引

* 项目顶层设计与技术宪法：`docs/ARCHITECTURE.md`
* Alist 云盘接入设计：`docs/ALIST_INTEGRATION_PLAN.md`
* 双 Agent 协作与权限契约：`AGENTS.md`
* 历史任务规划记录：`docs/tasks/TASK_*.md`

---

*Last updated: 2026-10-12 by Claude Fable 5.*  
*遵循三节点按需部署工作流规范。*
