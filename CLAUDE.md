# CLAUDE.md —— 编码 Agent 工作手册

> 写给 **Claude**（或任何被老板叫来改代码的 AI agent）。
> 你第一次接手这个项目时，**请把这份文档从头到尾读一遍再动手**。
>
> 这份文档跟 `README.md` 的区别：README 是项目门面；这份是**工作 SOP**，告诉你**能做什么、怎么做、出错怎么救**。

---

## 1. 项目是什么

**夭夭影社**——一个跑在飞牛 NAS（`192.168.31.235:9900`）上的私人影院。

**技术栈**:
```
后端    FastAPI 0.115+  +  SQLite WAL (aiosqlite)
前端    Vue 3 + Tailwind CSS v4 + Pinia + Vue Router + Vite
安卓    Capacitor 7.x + Media3/ExoPlayer 1.5.1
部署    Docker 单容器 yaoyao-cinema:latest (`docker-compose.yml`)
```

**核心设计哲学**: **零转码直出**——NAS 只切视频字节片，GPU 硬解全部交给设备。

---

## 2. 我的工作边界

### ✅ 该我做的

| 类别 | 具体范围 |
|---|---|
| **后端代码** | `server/api/*.py`、`server/services/*.py`、`server/scraper/*.py`、`server/database.py`、`server/models.py` |
| **前端代码** | `frontend/src/views/`、`components/`、`api/`、`stores/`、`router/` |
| **安卓原生** | `android/app/src/main/java/com/yaoyao/cinema/*.kt` |
| **测试** | `tests/` 下的单元测试 |
| **文档** | `docs/` 下面除 README/CLAUDE/AGENTS 之外的所有 |
| **bug 排查** | docker logs / SQLite 状态 / 请求响应 |

### ❌ 不该我做的

| 类别 | 原因 | 该谁干 |
|---|---|---|
| 重启 NAS 主机 / 杀 Docker Daemon / 重启整个 docker.service | 系统级动作，可能挂掉正在用的容器 | **老板本人** |
| 改 `mihomo-gateway` 容器配置 / macvlan 网络 | 家庭旁路由，挂了全家网 | **Hermes/夭夭-agent** |
| 改 `alist` 容器或者新增它负责的云盘 | 网盘接入跟影院无关 | **Hermes/夭夭-agent** |
| 直接修改 `data/yaoyao.db` 文件 | 数据库文件被前后都拿，手改会炸 | **写 migration + `server/database.py`** |
| 绕过 GitHub 直接改 NAS 上源码 | `git pull` 会覆盖你的改动 | **永远走 Git push** |
| `docker compose up -d` 不带服务名 | 会重建 compose 内的所有 service（你的 `docker-compose.yml` 只含 yaoyao-cinema 这一只；**另外的 alist/mihomo-gateway 在你 NAS 上是独立 compose 项目，不会被这条命令影响**） | **永远 `docker compose up -d yaoyao-cinema` 指定服务名**，习惯写死是个保险 |
| `git push --force` / `reset --hard` 主线 | 历史是金库 | **只做 fast-forward** |

### ⚠️ 需老板审批的

| 动作 | 例 |
|---|---|
| Docker daemon 配置改动 | 改 `daemon.json` / `proxy.conf` |
| 新增系统级依赖 | `apt-get install ffmpeg`（**已加**）/ 新 python 包 |
| 改 `docker-compose.yml` 的网络/卷挂载 | macvlan 或新增 bind mount |
| 数据库 schema 变更 | 加列 / 加表 / 改 primary key |
| 磁盘清理 / 删 docker 镜像 | `docker system prune` |

### 📌 Roadmap（你 push 完后会发生什么）

| 阶段 | 流程 | 现状 |
|---|---|---|
| **现在** | `git push` → 你在 GitHub 开 PR → 老板 merge → 老板告诉你 merge 完成 → **老板 ssh 到 NAS 重发版** | ✅ **走这个** |
| **中期** | push tag `v1.x.x` → GitHub Actions 自动 build → GHCR → NAS watchtower 拉 | ⏳ TODO |
| **远期** | NAS 上只跑镜像，源码永不挂载 | ⏳ TODO |

> ⚠️ 关键现实：**push 完不会自动触发 NAS 发布**。需要老板人工走 `git pull && docker compose up -d --build` 这条链。

---

## 3. 工作环境速查表

### 3.1 代码真相

| 位置 | 状态 | 正确性 |
|---|---|---|
| GitHub `TIANXT97/yaoyao-cinema` `/main` | **唯一权威源** ✅ | 永远是它 |
| NAS `/vol1/1000/vibe-projects/yaoyao-cinema/` | 同步副本 | 靠老板 `git pull` |
| 你 PC 上 `git clone` 的那份 | 工作区 | 未 push 前先别丢 |

> ⚠️ 铁律：**如果 NAS 副本和 GitHub `main` 不一致，那个 NAS 工作树副本是错的。从 `git fetch origin && git reset --hard origin/main` 重置**。

### 3.2 运行时（NAS）

| 资源 | 标识 |
|---|---|
| **service 名 / container 名 / image 名** | 都叫 `yaoyao-cinema` |
| **对外端口** | `192.168.31.235:9900` |
| **容器内 SQLite** | `/app/data/yaoyao.db` |
| **宿主机 SQLite** | `/vol1/1000/vibe-projects/yaoyao-cinema/data/yaoyao.db`（bind mount） |
| **媒体库根** | 宿主 `/vol1/1000/私人影库/` → 容器 `/media` |
| **前端 dist** | `/app/frontend/dist`（容器内），build 自 `frontend/` |
| **容器入口命令** | `uvicorn server.main:app --host 0.0.0.0 --port 9900 --proxy-headers`（容器内 PID 1，重启入口 = `docker restart yaoyao-cinema`） |

> ⚠️ **`127.0.0.1:9900`** 是给 NAS 宿主机或容器自己 curl 用的，不是你 PC 能访问的。PC 用 `192.168.31.235:9900`。

### 3.3 SSH 到 NAS

用 `~/.ssh/config` 配置 `ssh nas`：

```ssh-config
Host nas
    HostName 192.168.31.235
    User TIANXT
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    ProxyCommand cmd /c pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\Users\DELL\ssh-tools\socks5-bridge.ps1" %h %p 127.0.0.1 10808
    StrictHostKeyChecking accept-new
```

> 📌 **前置条件**: 你的 Torium 隧道（`E:\AI工具\Torium\THORIUM.BAT`）在跑，**且**已在 NAS 上 push-key 过一次。
> 一次性密钥注册脚本在 `C:\Users\DELL\ssh-tools\push-key.ps1`。

---

## 4. 代码改动前永远先做这 5 件事

| # | 永远先做 | 为啥 |
|---|---|---|
| 1 | `git fetch origin main` | 看远端 `main` 有没新提交 |
| 2 | `git checkout -b feat/<说明> origin/main` | 永远从 main 派生分支 |
| 3 | 在仓库根目录跑**所有**命令 | 不要在 `server/` 或 `frontend/` 里跑 |
| 4 | commit 前先 `pytest` + `npm run build`(后端和前端都过一遍) | 确保代码能跑 |
| 5 | commit msg 写成 `type(scope): 中文一句` + bullet | 例：`feat(stream): 支持HTTP HEAD探测` |

---

## 5. 工作 Recipe

### 5.1 改后端：新增 `PATCH /api/videos/{id}/tags`

```bash
# 仓库根目录下执行,所有命令从此 开始

# 1. fetch 并派生分支
git fetch origin main
git checkout -b feat/video-tags-api origin/main

# 2. 改代码
$EDITOR server/api/videos.py
# (新增 @router.patch(...), 业务逻辑, 返回类型)

# 3. 添加测试 (如果没有这个文件,新建一个;参考 tests/test_scraper.py 模板)
$EDITOR tests/test_api_videos.py

# 4. 跑测试 (注意pytest从 根目录跑,不要到 server/里)
pytest tests/ -v

# 5. 本地跑一次 后端 + 前端 验证（Windows PowerShell 写法）
#    (Step A) 起后端:
#        $env:YAOYAO_ROOT        = (Get-Location).Path
#        $env:YAOYAO_DATA_DIR    = "$env:YAOYAO_ROOT/data"
#        $env:YAOYAO_DB_PATH     = "$env:YAOYAO_ROOT/data/yaoyao.db"
#        $env:YAOYAO_MEDIA_ROOT  = "E:\media" # 本地示例根,没有就改为临时目录
#        $env:YAOYAO_FRONTEND_DIST = "$env:YAOYAO_ROOT/frontend/dist"
#
#        uvicorn server.main:app --host 127.0.0.1 --port 9900 --reload
#    
#    (Step B) 另开 终端 起前端 (Windows PowerShell):
#        cd frontend
#        $env:VITE_PROXY_TARGET = "http://127.0.0.1:9900"
#        npm run dev
#        # 浏览器开 http://localhost:5173
#        # 注意 vite.config.ts 已经识别 VITE_PROXY_TARGET 环境变量
#    
#    (Windows 注意: export/VITE_XXX=xxx 那种Unix shell 内联赋值在 PowerShell 不可用)

# 6. commit + push
git add server/api/videos.py tests/test_api_videos.py
git commit -m "feat(videos): 支持PATCH视频标签更新
- PATCH /api/videos/{video_id}/tags
- 增删标签, 幂等操作
- 新增标签不存在时返回404"

git push origin feat/video-tags-api

# 7. 到 GitHub 开 PR,等老板 merge 到 main
#    (例外: hotfix 且老板在场,可以直接 合并 main)

# 8. 老板 merge 后,你拿到完整 main:
git fetch origin main
git checkout main
git reset --hard origin/main

# 9. 老板接 push,登 NAS 重发版:
ssh nas 'cd /vol1/1000/vibe-projects/yaoyao-cinema && git pull && docker compose build yaoyao-cinema && docker compose up -d yaoyao-cinema'

# 10. 等 health check 通过后验证:
ssh nas 'curl -s http://127.0.0.1:9900/api/system/health'

# 拿一个真实 video_id (不写 python 内嵌,用 jq)
$video_id = ssh nas "curl -s 'http://127.0.0.1:9900/api/videos?per_page=1' | jq -r '.items[0].id'"
ssh nas "curl -s -X PATCH 'http://127.0.0.1:9900/api/videos/$video_id/tags' -H 'Content-Type: application/json' -d '{\"add\":[\"test-tag\"]}'"
```

### 5.2 改前端：视频卡片加"已看 80%"

```bash
# 与 5.1 一致,只是改文件在 frontend/ 下

git checkout -b feat/video-card-watched origin/main
$EDITOR frontend/src/components/media/VideoCard.vue
# (可选) $EDITOR frontend/src/api/videos.ts

# 本地调试 frontend (带上后端 proxy)
cd frontend
$env:VITE_PROXY_TARGET = "http://127.0.0.1:9900"
npm run dev
# 浏览器开 http://localhost:5173,前端热重载源码 改动
cd ..

# push + PR + NAS build 同 5.1
```

### 5.3 排查 NAS 服务

```bash
# 看容器
ssh nas 'docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"'

# 看实时日志
ssh nas 'docker logs yaoyao-cinema --tail=80 --follow'

# 服务是否有响应
ssh nas 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9900/api/system/health'

# 看 health 真实原因
ssh nas "docker inspect yaoyao-cinema --format='{{json .State.Health}}' | python3 -m json.tool"

# 看资源占用
ssh nas 'docker stats yaoyao-cinema --no-stream'

# 看 SQLite 整套大小 (含 WAL)
ssh nas 'du -sh /vol1/1000/vibe-projects/yaoyao-cinema/data/yaoyao.db*'

# 测 cloud:// 视频 302 跳转是不是工作
$cloud_id = ssh nas "curl -s 'http://127.0.0.1:9900/api/videos?per_page=50' | jq -r '.items[] | select(.file_path | startswith(\"cloud://\")) | .id' | head -1"
ssh nas "curl -s -I 'http://127.0.0.1:9900/api/stream/$cloud_id' | grep -i location"
```

### 5.4 数据库迁移 SOP

每次改 `server/models.py` 里的 schema **必须**写迁移脚本。

当前项目已经在 `server/database.py:init_schema()` 里**有 ALTER TABLE 逻辑**（自动给老 db 加新列），你加新 schema 时只需在 `init_schema()` 里**追加**新列即可：

```python
# server/database.py —— 正确的 SQLite 幂等迁移模式（当前项目在用）
async def init_schema(self):
    # 先查现有列，缺啥加啥;SQLite 不支持 ALTER TABLE ADD COLUMN IF NOT EXISTS
    cols = {row["name"] for row in await self.fetchall("PRAGMA table_info(videos)")}
    if "storage_type" not in cols:
        await self.execute("ALTER TABLE videos ADD COLUMN storage_type TEXT DEFAULT 'local'")
    if "your_new_col" not in cols:
        await self.execute("ALTER TABLE videos ADD COLUMN your_new_col TEXT DEFAULT ''")
    # ...
```

**部署前**手动备份 db（NAS 它写的，不是你的）：

```bash
ssh nas 'cp /vol1/1000/vibe-projects/yaoyao-cinema/data/yaoyao.db /vol1/1000/vibe-projects/yaoyao-cinema/data/yaoyao.db.bak.$(date +%Y%m%d_%H%M%S)'
```

**如果发现容器 crash loop**（`docker ps` 显示 `Restarting`）:

```bash
# 1. 看日志里是不是 sqlite 错
ssh nas 'docker logs yaoyao-cinema --tail=80 | grep -iE "no such column|OperationalError"'

# 2. 确认是迁移失败,回滚 db:
ssh nas 'cd /vol1/1000/vibe-projects/yaoyao-cinema/data && mv yaoyao.db yaoyao.db.broken && mv yaoyao.db.bak.YYYYMMDD_HHMMSS yaoyao.db && docker compose up -d yaoyao-cinema'
```

### 5.5 打新版本 tag 发版（含 GitHub Actions）

如果你的 NAS 端还是 hot 拉到最新 main 发版：

```bash
# 加一个版本 tag (语义化版本: MAJOR.MINOR.PATCH)
git tag -a v1.0.1 -m "fix(stream): 添加 HEAD 方法支持"
git push origin v1.0.1

# NAS 端发版 (保持跟 main 一致, no detached HEAD):
ssh nas 'cd /vol1/1000/vibe-projects/yaoyao-cinema && git fetch --tags origin && git checkout main && git reset --hard v1.0.1 && docker compose up -d --build yaoyao-cinema'
```

> 📌 **TODO**: 当 你打上 tag 之后 → GitHub Actions 那个 workflow 会自己 build 镜像 推 GHCR,然后 NAS 端 watchtower 自动 拉 the image. 这需要我们 next 一起 部署的 GitHub Actions `.github/workflows/release.yml`。

### 5.6 紧急回滚

> ⚠️ **重要**：本流程是老板本人执行,不是 Claude/agent。
> 因为工程 reset --hard / push 涉及 main 历史修改,违反不允许 agent 自主做此操作的红线。
> **Claude 遇到回滚需求,应该走 `git revert` 生成反向 commit 走 PR → 老板 merge,而不是 reset --hard。**

**正确做法（老板手动做）**:

```bash
# 1. 看 tags,找到上一个能用的版本
git tag -l --sort=-creatordate | head -5

# 2. 本地回 main 到那个 tag
git fetch origin --tags
git checkout main
git reset --hard v1.0.0

# 3. 老板 push 回 origin （你自己 force,自己接受后果）
git push origin main --force-with-lease

# 4. NAS 端你在那里发版,或者等 Hermes
ssh nas 'cd /vol1/1000/vibe-projects/yaoyao-cinema && git fetch origin --tags && git reset --hard v1.0.0 && docker compose up -d --build yaoyao-cinema'
```

**Claude 的正确做法**:

```bash
# 不要 reset --hard。用 revert 生成相反 commit
git revert <坏 commit hash> --no-edit

# push 走正常流程
git push origin fix/revert-bad-commit

# PR -> 老板 merge。
```

> ⚠️ 总之: **两行绝不本**。⑴ 不允许 agent force push main; ⑵ 不允许 agent reset main 历史。实情岀錯知主,让老板 Follow 他自己 选的策略。

---

## 6. 常见坑 & 解法

### 坑 #1: 改了 NAS 上源码但没生效
**症状**: `cat /vol1/1000/vibe-projects/yaoyao-cinema/server/api/stream.py` 是新代码,但 API 返回还是旧行为。  
**根因**: 容器内代码在**镜像里**,bind mount 只有 `data/` 和 `/media/`。改了源码不重 build 不会变。  
**解法**: `docker compose build yaoyao-cinema && docker compose up -d yaoyao-cinema`

### 坑 #2: build 拉 `node:22-alpine` 或 `python:3.11-slim` 失败
**症状**: `failed to fetch anonymous token: i/o timeout`  
**根因**: buildkit 的 token 握手不走 docker daemon 的 HTTP_PROXY。  
**解法**: 事先 `docker pull node:22-alpine` 和 `docker pull python:3.11-slim`,本地有了便不再发 token 请求。这也是这次 build 成功的关键。

### 坑 #3: build 到 ffmpeg apt 卡死
**症状**: `RUN apt-get install ffmpeg` 长时间不下新包,卡住 30 分钟。  
**根因**: ffmpeg 约 170 个 deb 包,`deb.debian.org` 国内直连慢。  
**解法**: `server/Dockerfile` 已经写死 `sed -i s|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g /etc/apt/sources.list.d/debian.sources` 在 Stage 2 python slim,**不要改回去**。
**验证**: build log 里看到 `Get:1 http://mirrors.tuna.tsinghua.edu.cn/` 而不是 `deb.debian.org`。

### 坑 #4: 改 schema 后服务启动 crash loop
**症状**: `docker logs yaoyao-cinema` 报 `OperationalError: no such column: ...`  
**根因**: 你改了 `server/database.py` 加了列,但老 db 是旧 schema。  
**解法**: 参考 §5.4 迁移 SOP,在 `server/database.py:init_schema()` 里用 **PRAGMA table_info 检查再 ALTER** 的写法（SQLite 不支持 IF NOT EXISTS,违者 syntax error）;真出错看 §5.4 的 crash loop 排查。

### 坑 #5: 新 API 是 404
**症状**: `curl /api/your-new-route` → 404  
**根因**: 路由写了但忘了 `include_router` 进 `server/api/router.py`。  
**解法**: 打开 `server/api/router.py`,在 `api_router.include_router(...)` 链尾追加 `api_router.include_router(你的新router)`,同时 `from . import yourmodule` 也要加。

### 坑 #6: `docker compose up -d` 把所有都拉起来了
**症状**: `docker ps` 里 `alist`、`mihomo-gateway` 也被重启了。  
**根因**: `docker compose up -d` 没指定服务名时,会重建 `docker-compose.yml` 文件里能发现的**所有** service。你 NAS 的 yaoyao-cinema 项目的 compose 只含 yaoyao-cinema 一只服务（**mihomo/alist 在另一个 compose 项目里,不会被这条命令拉起**）;但养这个习惯保险。
**解法**: **永远**指定服务名 `docker compose up -d yaoyao-cinema`。

### 坑 #7: `vite.config.ts` proxy 不搭,API 404
**症状**: `npm run dev` 前端起来了,但浏览器 `/api/...` 全 404。  
**根因**: `frontend/vite.config.ts` 里 `server.proxy['/api'].target` 用了 `VITE_PROXY_TARGET` 环境变量,默认 `http://127.0.0.1:9900`,但你的本地后端起了别的端口。  
**解法**: Windows 下 `$env:VITE_PROXY_TARGET = "http://127.0.0.1:<你起的后端端口>"` 然后再 `npm run dev`（PowerShell),或先 `uvicorn server.main:app --port 9900`。

### 坑 #8: 指向 `tests/test_api_videos.py` 但文件不存在
**症状**: §5.1 让你 `pytest tests/test_api_videos.py`,但这个文件实际不存在。  
**根因**: 当前 `tests/` 目录只有 `test_scraper.py`,没有 `test_api_videos.py`,需要你自己新建(参考 `tests/test_scraper.py` 模板)。
**解法**: 改成 `pytest tests/ -v`(跑全部现有测试),或者新建 `tests/test_api_videos.py` 再跑。

> ⚠️ **文档作者(self-eval)**: 这是一个已知文档级别 bug——§9 让你读 `docs/tasks/TASK_*.md`,但 `docs/tasks/` 这个目录其实不存在(历史 phase 文档放在仓库根目录 `TASK_*.md`)。这是文档自描述的失误——下次这些文档真的搬进 `docs/tasks/` 时,这部分就应该更新。

### 坑 #9: 临时动 schema 忘了 update models.py
**症状**: `docker exec` 进容器 can `PRAGMA table_info(videos)` 显示有 latest column,但 `select your_new_col` 还报"no such column"。  
**根因**: 你的 latest commit 被 push 之前,某个 broken build 已经跑了一遍半 init_schema,把列加上了,又把 build 中断了。  
**解法**: 进 NAS `data/` 目录 inspect SQLite:
```
ssh nas 'docker exec yaoyao-cinema python3 -c "
import sqlite3
conn = sqlite3.connect(\"/app/data/yaoyao.db\")
print([r for r in conn.execute(\"PRAGMA table_info(videos)\")][:15])
"'
```
如果 init_schema 是 **PRAGMA 检查再 ALTER** 的正确写法但临时 crashed,那列没被捞出来就 intact;那确实是第一次没跑成,手动加到 init_schema 后**重启即可**（会重跑一遍）。如果是误写 `ADD COLUMN IF NOT EXISTS` (qmodel 提示: 是 syntax error 错),那只可能是 syntax error 崩溃,先把写法回到正确 **PRAGMA + ALTER** 形式再重启。

---

## 7. 找不到答案去哪儿

| 你面对的问题 | 去哪儿查 |
|---|---|
| 项目设计哲学 /「为什么这么做」 | `docs/ARCHITECTURE.md`（**项目宪法**，真值 more authority than this doc） |
| 历史 phase 计划 | `TASK_*.md`（在仓库根目录,不按 README 说的在 docs/） |
| API 全表 | `docs/ARCHITECTURE.md` §2.5 |
| 数据库 schema | **`server/database.py:init_schema()` 是真实状态** + `docs/ARCHITECTURE.md` §2.2 注解 |
| 刮削引擎流程 | **`server/scraper/pipeline.py`** + `docs/ARCHITECTURE.md` §2.4 注解 |
| Alist 集成 | `docs/ALIST_INTEGRATION_PLAN.md`（**处理 `cloud://` 视频查询之前必须读**） |
| 最新代码 | `git log --oneline origin/main -20` |
| Docker 镜像 tag | `docker images yaoyao-cinema` |
| 容器健康 | `docker stats yaoyao-cinema --no-stream` |
| 磁盘大小 | `du -sh /vol1/1000/vibe-projects/yaoyao-cinema/data/yaoyao.db*` |
| 网络隧道（Torium Thoria） | 看 `C:\Users\DELL\ssh-tools\README.md` |

---

## 8. 出错怎么求助

| 情景 | 渠道 |
|---|---|
| 代码 bug 怪 | 先写个 reproducer `tests/test_XX.py`,让测试红起来再 push 半成品 |
| 想加 feature 但没想清楚 | GitHub 开 issue 标 `[RFC]`,老板看 |
| 跟 Hermes 意见冲突 | mirasim 喊老板仲裁,你俩都停手 |
| 紧急 bug 崩了 | 走 hotfix/v1.0.x-emergency 分支,老板 merge 后立即 deploy |
| 不理解文档/代码 | 老板/mirasim 直问。别猜 |

---

## 9. 最优先行动清单

- [ ] 你在读完这份文档后,给自己读完 `docs/ARCHITECTURE.md` (项目宪法) 标记为 read
- [ ] 第一次接触,先试一下 5.1 那个完整流程,别边读边写
- [ ] 遇到 §6 坑 #5 (新 API 404) 时,**记得** truth 就是那句"开 `server/api/router.py` 加 `include_router`"。我在文档中 patch了
- [ ] 记住 §3.3 里 ssh config 是远程访问 NAS 的入口,而 mirasim 是你给老板 / agent 之间对话的通道,两条分开用
- [ ] 遇 §6 坑 #4 crash loop 时别动 db,看 §5.4 "数据库迁移 SOP" 回滚

*Last updated: 2026-10-10 by Claude Fable 5.*  
*这份文档的目的: 下一个 coding agent 打开它就能工作,不需要任何解释。*

