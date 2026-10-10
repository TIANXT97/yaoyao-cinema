

# ARCHITECTURE.md — 夭夭影社（Yaoyao Cinema）全案系统架构规范

> **版本** 1.0.0 · **架构师** Claude Opus 4.6 · **日期** 2025-07  
> **面向读者** 后续编码执行者（DeepSeek / Cursor / 人工开发）  
> **部署宿主** 飞牛 fnOS NAS · `192.168.31.235` · 存储根 `/vol1/1000/vibe-projects/yaoyao-cinema/`

---

## 目录

1. [全局架构总览](#1-全局架构总览)
2. [服务端架构（FastAPI + SQLite WAL）](#2-服务端架构)
   - 2.1 [技术栈锁定](#21-技术栈锁定)
   - 2.2 [数据库表设计](#22-数据库表设计)
   - 2.3 [HTTP 206 Partial Content 分块流](#23-http-206-partial-content-分块流)
   - 2.4 [元数据刮削流水线](#24-元数据刮削流水线)
   - 2.5 [API 路由总表](#25-api-路由总表)
3. [前端与 PWA 架构（Vue 3 + Tailwind CSS v4）](#3-前端与-pwa-架构)
   - 3.1 [设计规范：东方纯白极简通透](#31-设计规范)
   - 3.2 [组件拆解与状态管理](#32-组件拆解与状态管理)
   - 3.3 [PWA Manifest 与 Service Worker](#33-pwa-manifest-与-service-worker)
4. [安卓原生封装架构（Capacitor）](#4-安卓原生封装架构)
   - 4.1 [Capacitor 集成结构](#41-capacitor-集成结构)
   - 4.2 [原生硬解播放器接入](#42-原生硬解播放器接入)
5. [完整工程目录树](#5-完整工程目录树)
6. [分步开发任务清单](#6-分步开发任务清单)

---

## 1. 全局架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        夭夭影社 · 系统全景                           │
│                                                                     │
│  ┌──────────────┐   HTTPS / LAN    ┌─────────────────────────────┐ │
│  │  苹果端 PWA   │◄───────────────►│                             │ │
│  │  Safari Shell │   JSON + 206    │    FastAPI 服务端            │ │
│  └──────────────┘                  │    (uvicorn, port 9900)     │ │
│                                    │                             │ │
│  ┌──────────────┐   HTTPS / LAN    │  ┌───────────┐ ┌─────────┐ │ │
│  │  安卓 App     │◄───────────────►│  │ API 路由层 │ │ 刮削引擎 │ │ │
│  │  Capacitor    │   JSON + 206    │  └─────┬─────┘ └────┬────┘ │ │
│  │  + ExoPlayer  │                 │        │            │      │ │
│  └──────────────┘                  │  ┌─────▼────────────▼────┐ │ │
│                                    │  │   SQLite WAL          │ │ │
│                                    │  │   yaoyao.db           │ │ │
│                                    │  └───────────────────────┘ │ │
│                                    │                             │ │
│                                    │  ┌───────────────────────┐ │ │
│                                    │  │   /media (NAS 存储)    │ │ │
│                                    │  │   视频 / 封面 / NFO    │ │ │
│                                    │  └───────────────────────┘ │ │
│                                    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 核心设计原则

| 原则 | 描述 |
|------|------|
| **零转码直出** | 服务端绝不做任何视频转码/重封装，仅回传原始字节流 + `206 Partial Content` |
| **NFO 优先** | 本地 `.nfo` 文件为元数据第一来源，刮削结果亦回写 NFO 以脱网持久化 |
| **极简唯美** | 前端遵循"东方纯白通透"美学，反对任何装饰性冗余元素 |
| **双轨同构** | 同一套 Vue SPA 代码，PWA 模式直出苹果端，Capacitor 包裹出安卓端 |
| **单文件部署** | 全站 SQLite 单库、前端 `dist/` 由 FastAPI 静态伺服，零外部依赖 |

### 技术栈全景

| 层级 | 技术 | 版本锁定 |
|------|------|----------|
| 服务端运行时 | Python | ≥ 3.11 |
| Web 框架 | FastAPI | ≥ 0.115 |
| ASGI 服务器 | Uvicorn | ≥ 0.30 |
| 数据库 | SQLite WAL 模式 | 内置 `aiosqlite` |
| ORM/查询 | 原生 SQL + `aiosqlite` | — |
| 刮削 HTTP | `httpx` (async) | ≥ 0.27 |
| 图片处理 | Pillow | ≥ 10.0 |
| 视频探针 | `ffprobe` (ffmpeg) | 系统级 |
| 前端框架 | Vue 3 Composition API | ≥ 3.5 |
| 构建工具 | Vite | ≥ 6.0 |
| CSS 框架 | Tailwind CSS | v4 |
| 状态管理 | Pinia | ≥ 2.2 |
| 工具库 | VueUse | ≥ 11.0 |
| 路由 | Vue Router | ≥ 4.4 |
| 安卓封装 | Capacitor | ≥ 6.0 |
| 原生播放器 | AndroidX Media3 (ExoPlayer) | ≥ 1.4 |

---

## 2. 服务端架构

### 2.1 技术栈锁定

```
Python 3.11+ / FastAPI / Uvicorn / aiosqlite / httpx / Pillow / ffprobe
```

服务端监听端口 **9900**，绑定 `0.0.0.0`，单进程 + 异步协程足以支撑私有场景的全部并发（预估同时观看 ≤ 3 路）。

### 2.2 数据库表设计

数据库文件：`/vol1/1000/vibe-projects/yaoyao-cinema/data/yaoyao.db`

开启 WAL 模式以实现并发读写：

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

#### 2.2.1 `videos` — 影片主表

```sql
CREATE TABLE videos (
    id              TEXT PRIMARY KEY,           -- UUID v4
    -- 基础信息
    title           TEXT NOT NULL,              -- 显示标题
    original_title  TEXT,                       -- 原始标题（日文等）
    sort_title      TEXT,                       -- 排序用标题
    bangou          TEXT,                       -- 番号（如 OPPENHEIMER-2023, FC2-PPV-1234567）
    bangou_norm     TEXT,                       -- 归一化番号（大写去连字符，用于去重匹配）
    -- 分类维度
    series_id       TEXT REFERENCES series(id), -- 所属系列
    studio          TEXT,                       -- 制作商 / 厂牌
    director        TEXT,                       -- 导演
    -- 时间
    release_date    TEXT,                       -- ISO 日期 YYYY-MM-DD
    date_added      TEXT NOT NULL DEFAULT (datetime('now')),
    -- 媒体文件
    file_path       TEXT NOT NULL UNIQUE,       -- 视频绝对路径
    file_name       TEXT NOT NULL,              -- 文件名
    file_size       INTEGER NOT NULL DEFAULT 0, -- 字节数
    duration        INTEGER DEFAULT 0,          -- 秒
    resolution      TEXT,                       -- 如 "1920x1080"
    video_codec     TEXT,                       -- 如 "hevc", "h264"
    audio_codec     TEXT,                       -- 如 "aac", "opus"
    container       TEXT,                       -- 如 "mp4", "mkv"
    bitrate         INTEGER,                    -- bps
    -- 图片资源（相对路径，相对于 media_root）
    poster_path     TEXT,                       -- 封面海报 2:3
    thumb_path      TEXT,                       -- 缩略图 16:9
    backdrop_path   TEXT,                       -- 背景大图
    -- 元数据
    plot            TEXT,                       -- 简介
    rating          REAL,                       -- 评分 0-10
    -- 刮削状态
    scrape_status   TEXT DEFAULT 'pending',     -- pending | matched | failed | manual
    scrape_source   TEXT,                       -- 最后刮削来源
    scrape_time     TEXT,                       -- 最后刮削时间
    nfo_path        TEXT,                       -- NFO 文件路径
    -- 播放状态
    play_count      INTEGER DEFAULT 0,
    last_played     TEXT,
    -- 标记
    is_favorite     INTEGER DEFAULT 0,          -- 0/1
    is_hidden       INTEGER DEFAULT 0,          -- 0/1 隐藏（不在默认列表出现）
    -- 时间戳
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_videos_bangou_norm ON videos(bangou_norm);
CREATE INDEX idx_videos_release_date ON videos(release_date);
CREATE INDEX idx_videos_series ON videos(series_id);
CREATE INDEX idx_videos_scrape_status ON videos(scrape_status);
CREATE INDEX idx_videos_favorite ON videos(is_favorite);
CREATE INDEX idx_videos_added ON videos(date_added);
```

#### 2.2.2 `series` — 系列表

```sql
CREATE TABLE series (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    name_ja         TEXT,                       -- 日文名
    description     TEXT,
    poster_path     TEXT,
    video_count     INTEGER DEFAULT 0,          -- 冗余计数，触发器维护
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### 2.2.3 `actors` — 演员表

```sql
CREATE TABLE actors (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,              -- 显示名
    name_ja         TEXT,                       -- 日文名
    aliases         TEXT,                       -- JSON 数组：别名列表
    photo_path      TEXT,                       -- 头像
    birth_date      TEXT,
    measurements    TEXT,                       -- 三围
    cup_size        TEXT,
    height          INTEGER,                    -- cm
    nationality     TEXT,
    video_count     INTEGER DEFAULT 0,          -- 冗余计数
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_actors_name ON actors(name);
```

#### 2.2.4 `video_actors` — 影片-演员关联

```sql
CREATE TABLE video_actors (
    video_id        TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    actor_id        TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
    PRIMARY KEY (video_id, actor_id)
);
```

#### 2.2.5 `tags` — 标签表

```sql
CREATE TABLE tags (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    name_ja         TEXT,
    category        TEXT DEFAULT 'genre',       -- genre | theme | feature
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### 2.2.6 `video_tags` — 影片-标签关联

```sql
CREATE TABLE video_tags (
    video_id        TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    tag_id          TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (video_id, tag_id)
);
```

#### 2.2.7 `watch_history` — 观看历史

```sql
CREATE TABLE watch_history (
    id              TEXT PRIMARY KEY,
    video_id        TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    position        INTEGER NOT NULL DEFAULT 0, -- 播放位置（秒）
    duration        INTEGER NOT NULL DEFAULT 0, -- 视频总时长（秒）
    progress        REAL NOT NULL DEFAULT 0,    -- 进度 0.0-1.0
    completed       INTEGER DEFAULT 0,          -- 是否看完 0/1
    watched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    device          TEXT                        -- 设备标识
);

CREATE INDEX idx_watch_video ON watch_history(video_id);
CREATE INDEX idx_watch_time ON watch_history(watched_at);

-- 最新一条记录即为"续播点"，查询:
-- SELECT * FROM watch_history WHERE video_id = ? ORDER BY watched_at DESC LIMIT 1
```

#### 2.2.8 `scraper_cache` — 刮削缓存

```sql
CREATE TABLE scraper_cache (
    id              TEXT PRIMARY KEY,
    bangou_norm     TEXT NOT NULL,              -- 归一化番号
    source          TEXT NOT NULL,              -- 数据源标识
    raw_json        TEXT NOT NULL,              -- 原始 JSON 响应
    fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT,                       -- 过期时间
    UNIQUE(bangou_norm, source)
);

CREATE INDEX idx_cache_bangou ON scraper_cache(bangou_norm);
```

#### ER 关系图

```
series 1──* videos *──* actors
                   *──* tags
                   1──* watch_history
                   *──1 scraper_cache (via bangou_norm)
```

### 2.3 HTTP 206 Partial Content 分块流

#### 2.3.1 设计原则

- **绝对零转码**：服务端仅做文件字节的 Range 切片返回
- **MIME 自动推断**：根据文件后缀映射 `video/mp4`, `video/x-matroska`, `video/webm`
- **分块尺寸**：默认 2 MB（`CHUNK_SIZE = 2 * 1024 * 1024`）
- **支持 Safari / Chrome / ExoPlayer 的 Range 请求行为差异**

#### 2.3.2 核心伪代码

```python
# server/api/stream.py

CHUNK_SIZE = 2 * 1024 * 1024  # 2MB

MIME_MAP = {
    ".mp4": "video/mp4",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    ".ts": "video/mp2t",
    ".wmv": "video/x-ms-wmv",
}

async def stream_video(request: Request, video_id: str):
    """
    HTTP 206 Partial Content 分块流伺服
    完整支持 Range: bytes=start-end 协议
    """
    # 1. 查库获取 file_path
    video = await db.get_video(video_id)
    if not video:
        raise HTTPException(404, "视频不存在")

    file_path = Path(video["file_path"])
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")

    file_size = file_path.stat().st_size
    suffix = file_path.suffix.lower()
    content_type = MIME_MAP.get(suffix, "application/octet-stream")

    # 2. 解析 Range 头
    range_header = request.headers.get("range")

    if not range_header:
        # 无 Range → 返回完整文件（首次探测 / 下载）
        # 但为优化，仍用 StreamingResponse 分块发送
        return StreamingResponse(
            file_iterator(file_path, 0, file_size - 1),
            status_code=200,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
            },
        )

    # 3. 解析 "bytes=start-end"
    start, end = parse_range(range_header, file_size)
    content_length = end - start + 1

    # 4. 返回 206 Partial Content
    return StreamingResponse(
        file_iterator(file_path, start, end),
        status_code=206,
        headers={
            "Content-Type": content_type,
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
            # CORS 头（跨域播放需要）
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Range",
            "Access-Control-Expose-Headers": "Content-Range, Content-Length",
        },
    )

def parse_range(range_header: str, file_size: int) -> tuple[int, int]:
    """
    解析 Range: bytes=start-end
    支持:
      - bytes=0-           → 从 0 到文件末
      - bytes=1000-1999    → 精确范围
      - bytes=-500         → 最后 500 字节
    """
    range_spec = range_header.replace("bytes=", "").strip()

    if range_spec.startswith("-"):
        # 倒数 N 字节
        suffix_length = int(range_spec)
        start = max(file_size + suffix_length, 0)
        end = file_size - 1
    elif range_spec.endswith("-"):
        # 从 start 到末尾
        start = int(range_spec[:-1])
        end = file_size - 1
    else:
        parts = range_spec.split("-")
        start = int(parts[0])
        end = int(parts[1])

    # 边界保护
    start = max(0, start)
    end = min(end, file_size - 1)

    if start > end:
        raise HTTPException(416, "Range Not Satisfiable")

    return start, end

async def file_iterator(path: Path, start: int, end: int):
    """异步文件分块读取生成器"""
    async with aiofiles.open(path, "rb") as f:
        await f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk_size = min(CHUNK_SIZE, remaining)
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
```

#### 2.3.3 Safari / Chrome / ExoPlayer 行为差异处理

| 客户端 | 首次请求行为 | 处理策略 |
|--------|-------------|----------|
| Safari (iOS) | 先发 `Range: bytes=0-1` 探测，再发 `bytes=0-` | 正常 206 响应即可 |
| Chrome | 直接 `Range: bytes=0-` | 正常 206 |
| ExoPlayer | 可能发 `bytes=0-` 或精确范围 | 正常 206，`Accept-Ranges` 必须存在 |

**关键：CORS 头必须包含 `Access-Control-Expose-Headers: Content-Range`，否则 Safari PWA 无法读取 Range 响应。**

### 2.4 元数据刮削流水线

#### 2.4.1 流水线总览

```
┌───────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  文件扫描  │────►│  番号解析器   │────►│  多源刮削器   │────►│  数据持久化   │
│  Scanner   │     │  BangouParser│     │  Scraper     │     │  Persister   │
└───────────┘     └──────────────┘     └─────────────┘     └──────────────┘
      │                  │                    │                     │
      ▼                  ▼                    ▼                     ▼
 遍历媒体目录      从文件名提取        并发查询多个源        写入 DB + NFO
 过滤视频文件      番号 + 归一化       合并最优结果          下载封面图片
 ffprobe 探针      识别无码/FC2        缓存 raw_json        2:3 智能裁切
```

#### 2.4.2 阶段一：文件扫描器（Scanner）

```python
# server/scraper/scanner.py

MEDIA_ROOT = Path("/vol1/1000/vibe-projects/yaoyao-cinema/media")
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".webm", ".ts", ".wmv", ".mov", ".rmvb"}

async def scan_media_library():
    """
    深度遍历媒体目录，发现新文件 → 注册进 videos 表
    已存在文件（file_path 匹配）跳过
    文件消失 → 标记为 missing（不删除记录）
    """
    existing_paths = await db.get_all_video_paths()  # Set[str]
    discovered = set()

    for root, dirs, files in os.walk(MEDIA_ROOT):
        for fname in files:
            if Path(fname).suffix.lower() in VIDEO_EXTS:
                full_path = str(Path(root) / fname)
                discovered.add(full_path)

                if full_path not in existing_paths:
                    # 新文件：ffprobe 提取元信息
                    probe = await ffprobe_async(full_path)
                    video_record = {
                        "id": str(uuid4()),
                        "title": Path(fname).stem,
                        "file_path": full_path,
                        "file_name": fname,
                        "file_size": Path(full_path).stat().st_size,
                        "duration": probe.get("duration", 0),
                        "resolution": probe.get("resolution"),
                        "video_codec": probe.get("video_codec"),
                        "audio_codec": probe.get("audio_codec"),
                        "container": Path(fname).suffix.lstrip("."),
                        "bitrate": probe.get("bitrate"),
                        "scrape_status": "pending",
                    }
                    # 检查同目录是否有 NFO
                    nfo_file = find_nfo(full_path)
                    if nfo_file:
                        nfo_data = parse_nfo(nfo_file)
                        video_record.update(nfo_data)
                        video_record["scrape_status"] = "matched"
                        video_record["nfo_path"] = str(nfo_file)

                    await db.insert_video(video_record)

    # 标记已删除文件
    missing = existing_paths - discovered
    if missing:
        await db.mark_missing(missing)
```

#### 2.4.3 阶段二：番号解析器（BangouParser）

```python
# server/scraper/bangou_parser.py

import re

# 正则规则集（优先级从高到低）
PATTERNS = [
    # FC2-PPV 系列
    (r"(?:FC2[-_]?PPV[-_]?)(\d{5,7})", lambda m: f"FC2-PPV-{m.group(1)}"),
    # 标准番号：字母3-10 + 数字3-5（如 OPPENHEIMER-2023, ABP-123, CAWD-001）
    (r"([A-Z]{2,10})[-_]?(\d{3,5})", lambda m: f"{m.group(1)}-{m.group(2)}"),
    # 无码系列：数字6+_数字3+（如 010120_001 → 一本道格式）
    (r"(\d{6})[-_](\d{3,4})", lambda m: f"{m.group(1)}_{m.group(2)}"),
    # n/k + 4位数字（如 n1234, k1234 → Tokyo-Hot / カリビアン）
    (r"\b([nk])(\d{4})\b", lambda m: f"{m.group(1).upper()}{m.group(2)}"),
    # HEYZO-NNNN
    (r"(?:HEYZO)[-_]?(\d{4})", lambda m: f"HEYZO-{m.group(1)}"),
]

def parse_bangou(filename: str) -> dict | None:
    """
    从文件名中提取番号

    返回:
        {
            "bangou": "OPPENHEIMER-2023",          # 标准显示格式
            "bangou_norm": "SSIS001",       # 归一化（大写、去连字符、用于去重）
            "type": "censored" | "uncensored" | "fc2"
        }
    """
    name = Path(filename).stem.upper()

    for pattern, formatter in PATTERNS:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            bangou = formatter(match)
            bangou_norm = re.sub(r"[-_\s]", "", bangou.upper())

            # 类型判断
            if "FC2" in bangou:
                btype = "fc2"
            elif re.match(r"\d{6}_\d{3,4}", bangou) or bangou.startswith(("N", "K", "HEYZO")):
                btype = "uncensored"
            else:
                btype = "censored"

            return {
                "bangou": bangou,
                "bangou_norm": bangou_norm,
                "type": btype,
            }

    return None  # 无法识别番号
```

#### 2.4.4 阶段三：多源刮削器（Scraper）

```python
# server/scraper/sources/__init__.py

"""
刮削源优先级（按类型）:

有码 (censored):
  1. javbus.com          → 综合信息最全
  2. javdb.com           → 评分 + 磁力
  3. javlibrary.com      → 用户评分
  4. dmm.co.jp           → 官方数据

无码 (uncensored):
  1. javbus.com/uncensored
  2. caribbeancom.com    → 加勒比官网
  3. 1pondo.tv           → 一本道官网
  4. heyzo.com           → HEYZO 官网

FC2:
  1. fc2hub.com          → FC2 聚合
  2. javdb.com           → FC2 区
  3. adult.contents.fc2.com → FC2 官网（受限）
"""

class ScraperPipeline:
    """多源刮削流水线管理器"""

    def __init__(self):
        self.sources = {
            "censored": [JavBusScraper(), JavDBScraper(), DMMScraper()],
            "uncensored": [JavBusUncensoredScraper(), CaribbeanScraper(), PondoScraper()],
            "fc2": [FC2HubScraper(), JavDBFC2Scraper()],
        }

    async def scrape(self, bangou: str, bangou_norm: str, btype: str) -> dict | None:
        """
        按优先级遍历数据源，首个成功即返回

        返回标准化结构:
        {
            "title": str,
            "original_title": str,
            "release_date": str,       # YYYY-MM-DD
            "studio": str,
            "director": str,
            "actors": [{"name": str, "name_ja": str, "photo_url": str}],
            "tags": [str],
            "plot": str,
            "rating": float,
            "series": str,
            "poster_url": str,         # 封面 URL
            "backdrop_url": str,       # 背景图 URL
            "source": str,             # 来源标识
        }
        """
        # 先查缓存
        cached = await db.get_scraper_cache(bangou_norm)
        if cached and not is_expired(cached):
            return json.loads(cached["raw_json"])

        # 按类型选择源列表
        source_list = self.sources.get(btype, self.sources["censored"])

        for source in source_list:
            try:
                result = await asyncio.wait_for(
                    source.fetch(bangou, bangou_norm),
                    timeout=15.0
                )
                if result:
                    # 写入缓存
                    await db.upsert_scraper_cache(
                        bangou_norm=bangou_norm,
                        source=source.name,
                        raw_json=json.dumps(result, ensure_ascii=False),
                    )
                    return result
            except (httpx.HTTPError, asyncio.TimeoutError) as e:
                logger.warning(f"[{source.name}] {bangou} 刮削失败: {e}")
                continue

        return None
```

#### 2.4.5 阶段四：数据持久化与封面处理

```python
# server/scraper/persister.py

async def persist_scrape_result(video_id: str, result: dict):
    """
    将刮削结果持久化：
    1. 更新 videos 表字段
    2. 关联/创建 actors, tags, series
    3. 下载并处理封面图片
    4. 生成/更新 NFO 文件
    """
    # 1. 下载封面 → 智能裁切
    if result.get("poster_url"):
        poster_path = await download_and_crop_poster(
            url=result["poster_url"],
            video_id=video_id,
            aspect_ratio=(2, 3),  # 强制 2:3 竖版
        )
    if result.get("backdrop_url"):
        backdrop_path = await download_image(
            url=result["backdrop_url"],
            video_id=video_id,
            suffix="backdrop",
        )

    # 2. 创建/关联演员
    actor_ids = []
    for actor_data in result.get("actors", []):
        actor = await db.get_or_create_actor(actor_data)
        actor_ids.append(actor["id"])

    # 3. 创建/关联标签
    tag_ids = []
    for tag_name in result.get("tags", []):
        tag = await db.get_or_create_tag(tag_name)
        tag_ids.append(tag["id"])

    # 4. 创建/关联系列
    series_id = None
    if result.get("series"):
        series = await db.get_or_create_series(result["series"])
        series_id = series["id"]

    # 5. 更新 videos 表
    await db.update_video(video_id, {
        "title": result.get("title"),
        "original_title": result.get("original_title"),
        "release_date": result.get("release_date"),
        "studio": result.get("studio"),
        "director": result.get("director"),
        "plot": result.get("plot"),
        "rating": result.get("rating"),
        "series_id": series_id,
        "poster_path": poster_path,
        "backdrop_path": backdrop_path,
        "scrape_status": "matched",
        "scrape_source": result.get("source"),
        "scrape_time": datetime.now().isoformat(),
    })

    # 6. 关联表
    await db.set_video_actors(video_id, actor_ids)
    await db.set_video_tags(video_id, tag_ids)

    # 7. 写回 NFO
    await write_nfo(video_id)


async def download_and_crop_poster(url: str, video_id: str, aspect_ratio=(2, 3)) -> str:
    """
    下载封面 → 智能 2:3 裁切

    日式封面通常是横版大图，人物在右侧。
    裁切策略：取右半部分作为竖版海报（人物面部区域）。
    """
    raw_bytes = await httpx_client.get(url)
    img = Image.open(BytesIO(raw_bytes.content))
    w, h = img.size

    target_ratio = aspect_ratio[0] / aspect_ratio[1]  # 0.667
    current_ratio = w / h

    if abs(current_ratio - target_ratio) < 0.05:
        # 已经接近 2:3，直接缩放
        cropped = img
    elif current_ratio > target_ratio:
        # 横版图 → 裁右侧
        new_w = int(h * target_ratio)
        left = w - new_w  # 取右侧
        cropped = img.crop((left, 0, w, h))
    else:
        # 竖版但比例不对 → 裁中间
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        cropped = img.crop((0, top, w, top + new_h))

    # 缩放到标准尺寸
    cropped = cropped.resize((400, 600), Image.LANCZOS)

    # 保存
    save_dir = MEDIA_ROOT / "posters"
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{video_id}.jpg"
    cropped.save(save_path, "JPEG", quality=90)

    return str(save_path.relative_to(MEDIA_ROOT))
```

#### 2.4.6 NFO 文件规范（兼容 Jellyfin / Emby）

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>Oppenheimer 奥本海默</title>
  <originaltitle>Oppenheimer 2023 4K REMUX</originaltitle>
  <sorttitle>OPPENHEIMER-2023</sorttitle>
  <num>OPPENHEIMER-2023</num>
  <studio>Universal Pictures</studio>
  <director>Christopher Nolan</director>
  <year>2021</year>
  <premiered>2021-01-19</premiered>
  <plot>传记/剧情/历史...</plot>
  <runtime>120</runtime>
  <rating>8.5</rating>
  <tag>巨乳</tag>
  <tag>新人</tag>
  <genre>巨乳</genre>
  <genre>新人</genre>
  <actor>
    <name>Cillian Murphy</name>
    <thumb>posters/actors/cillian_murphy.jpg</thumb>
  </actor>
  <set>
    <name>奥本海默</name>
  </set>
  <art>
    <poster>poster.jpg</poster>
    <fanart>backdrop.jpg</fanart>
  </art>
</movie>
```

### 2.5 API 路由总表

**基础路径：** `http://192.168.31.235:9900/api`

#### 2.5.1 影片 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/videos` | 影片列表（分页、排序、筛选） |
| `GET` | `/videos/{id}` | 影片详情（含演员、标签、续播点） |
| `PUT` | `/videos/{id}` | 更新影片元数据 |
| `DELETE` | `/videos/{id}` | 删除影片记录（不删文件） |
| `POST` | `/videos/{id}/favorite` | 切换收藏状态 |
| `POST` | `/videos/{id}/hide` | 切换隐藏状态 |

**`GET /videos` 查询参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码 |
| `per_page` | int | 30 | 每页数量 (max 100) |
| `sort` | str | `date_added` | 排序字段: `date_added`, `release_date`, `title`, `rating`, `play_count`, `last_played`, `file_size` |
| `order` | str | `desc` | `asc` / `desc` |
| `search` | str | — | 关键词搜索（标题、番号、演员名） |
| `actor_id` | str | — | 按演员筛选 |
| `tag_id` | str | — | 按标签筛选 |
| `series_id` | str | — | 按系列筛选 |
| `studio` | str | — | 按制作商筛选 |
| `favorite` | bool | — | 仅收藏 |
| `status` | str | — | 刮削状态筛选 |

#### 2.5.2 流媒体 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/stream/{id}` | HTTP 206 视频流 |
| `GET` | `/images/{path:path}` | 静态图片（封面、头像等） |

#### 2.5.3 观看历史 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/history` | 上报播放进度 |
| `GET` | `/history/recent` | 最近观看（续播列表） |
| `GET` | `/history/{video_id}` | 获取某影片的续播点 |

#### 2.5.4 刮削 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/scraper/scan` | 触发全库文件扫描 |
| `POST` | `/scraper/scrape/{id}` | 对单个影片执行刮削 |
| `POST` | `/scraper/scrape-all` | 对所有 pending 影片批量刮削 |
| `GET` | `/scraper/status` | 刮削任务状态 |

#### 2.5.5 分类浏览 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/actors` | 演员列表（带影片计数） |
| `GET` | `/actors/{id}` | 演员详情 + 作品列表 |
| `GET` | `/tags` | 标签列表（带影片计数） |
| `GET` | `/series` | 系列列表 |
| `GET` | `/studios` | 制作商列表（从 videos 聚合） |

#### 2.5.6 系统 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/system/stats` | 系统统计（总数、大小、刮削进度） |
| `GET` | `/system/health` | 健康检查 |

---

## 3. 前端与 PWA 架构

### 3.1 设计规范

#### 设计哲学：东方纯白极简通透（Anti-Slop Minimalist Editorial）

> 像翻阅一本高端摄影画册，每一帧都是精心策展的艺术品。
> 留白即信息，通透即力量，克制即奢侈。

#### 3.1.1 色彩系统

```css
/* tailwind.config — 自定义色彩 Token */
:root {
  /* —— 主色调：纯白宣纸 —— */
  --yy-bg-primary:     #FFFFFF;       /* 主背景 · 纯白 */
  --yy-bg-secondary:   #FAFAFA;       /* 次背景 · 微暖灰 */
  --yy-bg-tertiary:    #F5F5F5;       /* 三级背景 · 淡灰 */
  --yy-bg-elevated:    #FFFFFF;       /* 浮层卡片 */

  /* —— 文字层级 —— */
  --yy-text-primary:   #1A1A1A;       /* 主标题 · 近墨 */
  --yy-text-secondary: #666666;       /* 副文本 · 灰 */
  --yy-text-tertiary:  #999999;       /* 辅助文字 · 浅灰 */
  --yy-text-muted:     #CCCCCC;       /* 占位 / 禁用 */

  /* —— 功能色 —— */
  --yy-accent:         #D4A574;       /* 点缀 · 烫金 / 暖杏 */
  --yy-accent-hover:   #C49464;       /* 点缀悬停 */
  --yy-divider:        #EBEBEB;       /* 分割线 · 极淡 */
  --yy-overlay:        rgba(0,0,0,0.03); /* 遮罩 · 几乎透明 */

  /* —— 播放器专用（暗色） —— */
  --yy-player-bg:      #000000;       /* 播放器背景 · 纯黑 */
  --yy-player-control: rgba(255,255,255,0.85); /* 控件 */
}
```

#### 3.1.2 字体系统

```css
/* 中英文混排最佳实践 */
--yy-font-sans: "SF Pro Text", "PingFang SC", "Hiragino Sans",
                "Noto Sans SC", system-ui, sans-serif;
--yy-font-serif: "Noto Serif SC", "Source Han Serif SC",
                 "SimSun", serif;
--yy-font-mono: "SF Mono", "JetBrains Mono", "Fira Code", monospace;

/* 字重 */
--yy-font-light:    300;
--yy-font-regular:  400;
--yy-font-medium:   500;

/* 字号 */
--yy-text-xs:   0.75rem;   /* 12px · 最小辅助 */
--yy-text-sm:   0.875rem;  /* 14px · 正文辅助 */
--yy-text-base: 1rem;      /* 16px · 正文 */
--yy-text-lg:   1.125rem;  /* 18px · 小标题 */
--yy-text-xl:   1.5rem;    /* 24px · 区块标题 */
--yy-text-2xl:  2rem;      /* 32px · 页标题 */
```

#### 3.1.3 间距与圆角

```css
/* 8px 基准网格 */
--yy-space-1:  0.25rem;    /* 4px */
--yy-space-2:  0.5rem;     /* 8px */
--yy-space-3:  0.75rem;    /* 12px */
--yy-space-4:  1rem;       /* 16px */
--yy-space-6:  1.5rem;     /* 24px */
--yy-space-8:  2rem;       /* 32px */
--yy-space-12: 3rem;       /* 48px */
--yy-space-16: 4rem;       /* 64px */

/* 圆角 · 克制温和 */
--yy-radius-sm:  4px;
--yy-radius-md:  8px;
--yy-radius-lg:  12px;
--yy-radius-xl:  16px;
```

#### 3.1.4 动效规范

```css
/* 过渡 · 丝滑但不浮夸 */
--yy-ease:          cubic-bezier(0.25, 0.1, 0.25, 1);
--yy-ease-out:      cubic-bezier(0, 0, 0.25, 1);
--yy-duration-fast: 150ms;
--yy-duration-base: 250ms;
--yy-duration-slow: 400ms;

/* 原则：
   - 所有交互反馈 ≤ 250ms
   - 页面切换 300-400ms 滑动
   - 海报 hover 仅轻微 scale(1.02) + 阴影浮起
   - 禁止弹跳、旋转、抖动等花哨动效
*/
```

#### 3.1.5 设计要素清单

| 要素 | 规范 |
|------|------|
| 海报卡片 | 纯图无边框，hover 时 `scale(1.02)` + `box-shadow: 0 8px 32px rgba(0,0,0,0.08)` |
| 卡片标题 | 海报下方 8px，`font-weight: 400`，单行省略 |
| 番号标签 | `font-size: 12px`，`color: var(--yy-text-tertiary)`，`letter-spacing: 0.05em` |
| 分割线 | `1px solid var(--yy-divider)`，不使用粗线 |
| 按钮 | 文字按钮为主，无背景色，hover 时底部加 1px 下划线 |
| 图标 | Lucide Icons（线性 1.5px 描边），禁用填充图标 |
| 空状态 | 中心一行浅灰文字，不使用插画 |
| 加载态 | 海报骨架屏（浅灰矩形 + 脉冲动画），不使用旋转菊花 |
| 滚动条 | macOS 风格自动隐藏，或 `scrollbar-width: none` |
| 导航栏 | 底部固定 tab bar（iOS 风格），图标 + 文字，无背景遮罩仅 `backdrop-filter: blur(16px)` |

### 3.2 组件拆解与状态管理

#### 3.2.1 页面路由

```typescript
// src/router/index.ts
const routes = [
  {
    path: '/',
    component: Layout,
    children: [
      { path: '',           name: 'Home',       component: () => import('@/pages/HomePage.vue') },
      { path: 'library',    name: 'Library',     component: () => import('@/pages/LibraryPage.vue') },
      { path: 'favorites',  name: 'Favorites',   component: () => import('@/pages/FavoritesPage.vue') },
      { path: 'history',    name: 'History',     component: () => import('@/pages/HistoryPage.vue') },
      { path: 'actors',     name: 'Actors',      component: () => import('@/pages/ActorsPage.vue') },
      { path: 'actor/:id',  name: 'ActorDetail', component: () => import('@/pages/ActorDetailPage.vue') },
      { path: 'search',     name: 'Search',      component: () => import('@/pages/SearchPage.vue') },
      { path: 'settings',   name: 'Settings',    component: () => import('@/pages/SettingsPage.vue') },
    ]
  },
  {
    path: '/play/:id',
    name: 'Player',
    component: () => import('@/pages/PlayerPage.vue'),
    meta: { fullscreen: true, hideTabBar: true }
  },
]
```

#### 3.2.2 核心组件树

```
src/components/
├── layout/
│   ├── AppLayout.vue              # 主布局壳（slot + tab bar）
│   ├── TabBar.vue                 # 底部导航（5 tab）
│   └── PageHeader.vue             # 页面顶部标题栏
│
├── video/
│   ├── PosterCard.vue             # 海报卡片（2:3 封面 + 标题 + 番号）
│   ├── PosterGrid.vue             # 海报瀑布流网格（响应式列数）
│   ├── VideoDetailDrawer.vue      # 底部上滑详情抽屉（Sheet）
│   ├── VideoMeta.vue              # 元数据展示（演员、标签、年份等）
│   └── ProgressBar.vue            # 观看进度条（卡片底部彩条）
│
├── player/
│   ├── VideoPlayer.vue            # 播放器主容器
│   ├── PlayerControls.vue         # 播放控件层
│   ├── GestureOverlay.vue         # 手势识别覆盖层
│   └── ProgressSlider.vue         # 进度滑块
│
├── browse/
│   ├── ActorCard.vue              # 演员卡片（圆形头像 + 名字）
│   ├── TagPill.vue                # 标签药丸
│   ├── FilterBar.vue              # 筛选 / 排序工具栏
│   └── SearchInput.vue            # 搜索输入框
│
└── common/
    ├── LazyImage.vue              # 图片懒加载 + 骨架
    ├── InfiniteScroll.vue         # 无限滚动触发器
    ├── BottomSheet.vue            # 通用底部弹出面板
    ├── Skeleton.vue               # 骨架屏组件
    └── EmptyState.vue             # 空状态提示
```

#### 3.2.3 状态管理（Pinia Stores）

```typescript
// src/stores/video.ts
export const useVideoStore = defineStore('video', () => {
  // === 状态 ===
  const videos = ref<Video[]>([])
  const currentVideo = ref<Video | null>(null)
  const loading = ref(false)
  const pagination = ref({ page: 1, perPage: 30, total: 0 })
  const filters = ref<VideoFilters>({
    sort: 'date_added',
    order: 'desc',
    search: '',
    actorId: undefined,
    tagId: undefined,
    seriesId: undefined,
    studio: undefined,
    favorite: undefined,
  })

  // === 动作 ===
  async function fetchVideos(reset = false) { ... }
  async function fetchVideoDetail(id: string) { ... }
  async function toggleFavorite(id: string) { ... }
  async function loadMore() { ... }  // 无限滚动追加

  return { videos, currentVideo, loading, pagination, filters,
           fetchVideos, fetchVideoDetail, toggleFavorite, loadMore }
})

// src/stores/player.ts
export const usePlayerStore = defineStore('player', () => {
  const isPlaying = ref(false)
  const currentTime = ref(0)
  const duration = ref(0)
  const progress = computed(() => duration.value ? currentTime.value / duration.value : 0)
  const isFullscreen = ref(false)
  const showControls = ref(true)
  const videoId = ref<string | null>(null)

  // 续播点
  const resumePosition = ref(0)

  // 手势状态
  const gestureState = ref<'idle' | 'seeking' | 'volume' | 'brightness'>('idle')

  async function reportProgress() { ... }  // 节流上报（每 10 秒）
  async function loadResumePoint(id: string) { ... }

  return { isPlaying, currentTime, duration, progress, isFullscreen,
           showControls, videoId, resumePosition, gestureState,
           reportProgress, loadResumePoint }
})

// src/stores/history.ts
export const useHistoryStore = defineStore('history', () => {
  const recentVideos = ref<WatchRecord[]>([])
  async function fetchRecent() { ... }
  return { recentVideos, fetchRecent }
})
```

#### 3.2.4 播放器手势系统

```typescript
// src/composables/usePlayerGestures.ts

/**
 * 全屏播放器手势识别
 *
 * 手势映射：
 * ┌────────────────────────────────────┐
 * │  左半区上下滑  │  右半区上下滑      │
 * │  = 亮度调节    │  = 音量调节        │
 * │                │                    │
 * │          左右滑 = 快进/退           │
 * │          单击 = 切换控件            │
 * │          双击左 = 后退 10s          │
 * │          双击右 = 前进 10s          │
 * └────────────────────────────────────┘
 */

export function usePlayerGestures(playerRef: Ref<HTMLVideoElement | null>) {
  const { direction, distanceX, distanceY, isSwiping } = useSwipe(playerRef)
  const { x } = useElementBounding(playerRef)

  // 判断触摸区域（左/右半区）
  function getTouchZone(touchX: number): 'left' | 'right' {
    const rect = playerRef.value?.getBoundingClientRect()
    if (!rect) return 'right'
    return touchX < rect.left + rect.width / 2 ? 'left' : 'right'
  }

  // 单击 → 显示/隐藏控件
  // 双击左区 → seek -10s
  // 双击右区 → seek +10s
  // 水平滑动 → 快进/退（每 px = 0.5s）
  // 左区垂直滑动 → 亮度
  // 右区垂直滑动 → 音量

  return { /* 暴露手势状态 */ }
}
```

#### 3.2.5 海报网格响应式列数

```vue
<!-- PosterGrid.vue -->
<template>
  <div class="grid gap-3 sm:gap-4"
       :class="gridCols">
    <PosterCard v-for="video in videos" :key="video.id" :video="video"
                @click="openDetail(video)" />
    <InfiniteScroll @load="$emit('load-more')" />
  </div>
</template>

<!--
  响应式列数：
  iPhone SE (375px)   → 3 列
  iPhone 14 (390px)   → 3 列
  iPad Mini (768px)   → 4 列
  iPad Pro (1024px)   → 5 列
  Desktop (1280px+)   → 6 列

  Tailwind classes:
  grid-cols-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6
-->
```

### 3.3 PWA Manifest 与 Service Worker

#### 3.3.1 Web App Manifest

```json
// public/manifest.json
{
  "name": "夭夭影社",
  "short_name": "夭夭",
  "description": "TIAN 的私家影院",
  "start_url": "/",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#FFFFFF",
  "theme_color": "#FFFFFF",
  "icons": [
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-maskable-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }
  ],
  "categories": ["entertainment"],
  "lang": "zh-CN"
}
```

#### 3.3.2 Service Worker 缓存策略

```typescript
// src/sw.ts (vite-plugin-pwa 配置)

/**
 * 缓存策略分层：
 *
 * 1. App Shell (HTML/JS/CSS)     → CacheFirst, 版本更新时全量替换
 * 2. API 数据 (/api/*)           → NetworkFirst, 30s 超时回退缓存
 * 3. 图片 (/api/images/*)        → CacheFirst, 最大缓存 500 张
 * 4. 视频流 (/api/stream/*)      → NetworkOnly, 绝不缓存（太大 + Range 请求）
 *
 * 策略原则：
 * - 视频永远走网络（不缓存 GB 级文件）
 * - 海报封面缓存加速体验
 * - API 网络优先保证数据新鲜
 */

// vite.config.ts 中的 PWA 插件配置
VitePWA({
  registerType: 'autoUpdate',
  workbox: {
    navigateFallback: '/index.html',
    runtimeCaching: [
      {
        // API 数据 → NetworkFirst
        urlPattern: /^https?:\/\/.*\/api\/(?!stream|images).*/,
        handler: 'NetworkFirst',
        options: {
          cacheName: 'api-cache',
          networkTimeoutSeconds: 30,
          expiration: { maxEntries: 200, maxAgeSeconds: 86400 },
        },
      },
      {
        // 图片 → CacheFirst
        urlPattern: /^https?:\/\/.*\/api\/images\/.*/,
        handler: 'CacheFirst',
        options: {
          cacheName: 'image-cache',
          expiration: { maxEntries: 500, maxAgeSeconds: 604800 },
          cacheableResponse: { statuses: [0, 200] },
        },
      },
      // 视频流不缓存（默认行为即 NetworkOnly）
    ],
  },
})
```

#### 3.3.3 iOS Safari PWA 特殊处理

```html
<!-- index.html head 区域 -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="夭夭影社">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">

<!-- 启动屏幕（防止白屏闪烁） -->
<link rel="apple-touch-startup-image"
      media="(device-width: 390px) and (device-height: 844px) and (-webkit-device-pixel-ratio: 3)"
      href="/splash/splash-1170x2532.png">
<link rel="apple-touch-startup-image"
      media="(device-width: 393px) and (device-height: 852px) and (-webkit-device-pixel-ratio: 3)"
      href="/splash/splash-1179x2556.png">
<!-- ... 其他尺寸 -->

<!-- viewport：刘海屏适配 -->
<meta name="viewport"
      content="width=device-width, initial-scale=1.0, maximum-scale=1.0,
               user-scalable=no, viewport-fit=cover">
```

```css
/* 安全区域适配 */
.tab-bar {
  padding-bottom: env(safe-area-inset-bottom);
}
.page-header {
  padding-top: env(safe-area-inset-top);
}
```

---

## 4. 安卓原生封装架构

### 4.1 Capacitor 集成结构

```
yaoyao-cinema/
├── frontend/                    # Vue 项目
│   ├── capacitor.config.ts      # Capacitor 配置
│   ├── android/                 # Capacitor 生成的安卓工程（gitignore 部分）
│   │   ├── app/
│   │   │   ├── src/main/
│   │   │   │   ├── java/com/yaoyao/cinema/
│   │   │   │   │   ├── MainActivity.kt
│   │   │   │   │   └── plugins/
│   │   │   │   │       └── NativePlayerPlugin.kt
│   │   │   │   ├── res/
│   │   │   │   └── AndroidManifest.xml
│   │   │   └── build.gradle.kts
│   │   └── build.gradle.kts
│   └── ...
```

#### Capacitor 配置文件

```typescript
// frontend/capacitor.config.ts

import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.yaoyao.cinema',
  appName: '夭夭影社',
  webDir: 'dist',

  server: {
    // 生产模式：加载本地打包文件
    // 开发模式：可选 liveReload
    androidScheme: 'https',
    // 允许访问 NAS 局域网地址
    allowNavigation: ['192.168.31.235:9900'],
  },

  android: {
    // 允许明文 HTTP（局域网场景）
    allowMixedContent: true,
    // 全屏沉浸
    backgroundColor: '#FFFFFF',
  },

  plugins: {
    StatusBar: {
      style: 'LIGHT',           // 浅色状态栏
      backgroundColor: '#FFFFFF',
    },
    Keyboard: {
      resize: 'body',
      style: 'LIGHT',
    },
    ScreenOrientation: {},       // 播放器横屏锁定
  },
};

export default config;
```

### 4.2 原生硬解播放器接入

#### 4.2.1 方案概述

```
┌──────────────────────────────────────────┐
│  WebView (Vue App)                       │
│  ┌────────────────────────────────────┐  │
│  │  点击播放按钮                       │  │
│  │  ↓ Capacitor Bridge 调用           │  │
│  │  NativePlayer.play({ url, pos })   │  │
│  └────────────────────────────────────┘  │
│                  │                        │
│                  ▼                        │
│  ┌────────────────────────────────────┐  │
│  │  NativePlayerPlugin (Kotlin)       │  │
│  │  → 启动 PlayerActivity             │  │
│  │  → ExoPlayer (Media3) 硬解播放     │  │
│  │  → 播放结束后回调进度给 WebView     │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

#### 4.2.2 原生插件定义

```kotlin
// android/app/src/main/java/com/yaoyao/cinema/plugins/NativePlayerPlugin.kt

@CapacitorPlugin(name = "NativePlayer")
class NativePlayerPlugin : Plugin() {

    @PluginMethod
    fun play(call: PluginCall) {
        val url = call.getString("url") ?: run {
            call.reject("url is required")
            return
        }
        val position = call.getLong("position", 0L)   // 续播位置 (ms)
        val title = call.getString("title", "")

        val intent = Intent(activity, PlayerActivity::class.java).apply {
            putExtra("url", url)
            putExtra("position", position)
            putExtra("title", title)
        }

        // 注册结果回调
        startActivityForResult(call, intent, "playResult")
    }

    override fun handleOnActivityResult(
        requestCode: Int, resultCode: Int, data: Intent?
    ) {
        super.handleOnActivityResult(requestCode, resultCode, data)
        val savedCall = bridge.getSavedCall(callbackId) ?: return

        if (resultCode == Activity.RESULT_OK && data != null) {
            val result = JSObject().apply {
                put("position", data.getLongExtra("position", 0))
                put("duration", data.getLongExtra("duration", 0))
                put("completed", data.getBooleanExtra("completed", false))
            }
            savedCall.resolve(result)
        } else {
            savedCall.resolve(JSObject().put("cancelled", true))
        }
    }
}
```

#### 4.2.3 ExoPlayer (Media3) 播放 Activity

```kotlin
// android/app/src/main/java/com/yaoyao/cinema/PlayerActivity.kt

class PlayerActivity : AppCompatActivity() {

    private lateinit var player: ExoPlayer
    private lateinit var playerView: PlayerView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 全屏沉浸
        WindowCompat.setDecorFitsSystemWindows(window, false)
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE

        setContentView(R.layout.activity_player)
        playerView = findViewById(R.id.player_view)

        val url = intent.getStringExtra("url") ?: return finish()
        val position = intent.getLongExtra("position", 0L)

        // 初始化 ExoPlayer
        player = ExoPlayer.Builder(this)
            .setMediaSourceFactory(
                DefaultMediaSourceFactory(this)
                    // HTTP Range 支持
                    .setDataSourceFactory(DefaultHttpDataSource.Factory()
                        .setUserAgent("YaoyaoCinema/1.0")
                        .setAllowCrossProtocolRedirects(true)
                    )
            )
            .build()
            .also { exo ->
                playerView.player = exo
                val mediaItem = MediaItem.fromUri(url)
                exo.setMediaItem(mediaItem)
                exo.seekTo(position)
                exo.playWhenReady = true
                exo.prepare()
            }
    }

    override fun onDestroy() {
        // 回传播放进度
        val resultIntent = Intent().apply {
            putExtra("position", player.currentPosition)
            putExtra("duration", player.duration)
            putExtra("completed", player.currentPosition >= player.duration * 0.9)
        }
        setResult(Activity.RESULT_OK, resultIntent)
        player.release()
        super.onDestroy()
    }
}
```

#### 4.2.4 前端调用桥接

```typescript
// src/composables/useNativePlayer.ts

import { Capacitor } from '@capacitor/core'
import { registerPlugin } from '@capacitor/core'

interface NativePlayerPlugin {
  play(options: {
    url: string
    position?: number   // ms
    title?: string
  }): Promise<{
    position: number
    duration: number
    completed: boolean
    cancelled?: boolean
  }>
}

const NativePlayer = registerPlugin<NativePlayerPlugin>('NativePlayer')

export function useNativePlayer() {
  const isNative = Capacitor.isNativePlatform()

  async function playVideo(videoId: string, resumeMs = 0) {
    const url = `${API_BASE}/stream/${videoId}`

    if (isNative) {
      // 安卓原生播放器
      const result = await NativePlayer.play({
        url,
        position: resumeMs,
        title: '...',
      })
      if (!result.cancelled) {
        // 上报进度
        await reportProgress(videoId, result.position, result.duration)
      }
    } else {
      // PWA / 浏览器 → 使用 HTML5 <video> 播放器
      router.push({ name: 'Player', params: { id: videoId } })
    }
  }

  return { playVideo, isNative }
}
```

---

## 5. 完整工程目录树

```
/vol1/1000/vibe-projects/yaoyao-cinema/
│
├── README.md                              # 项目说明
├── ARCHITECTURE.md                        # 本文件
├── docker-compose.yml                     # （可选）容器化部署
├── Makefile                               # 常用命令快捷方式
│
├── data/                                  # 运行时数据（gitignore）
│   ├── yaoyao.db                          # SQLite 数据库
│   ├── yaoyao.db-wal                      # WAL 日志
│   └── yaoyao.db-shm                      # 共享内存
│
├── media/                                 # 媒体文件存储根（gitignore）
│   ├── videos/                            # 视频文件（或软链接到实际位置）
│   │   ├── censored/                      # 有码
│   │   ├── uncensored/                    # 无码
│   │   └── fc2/                           # FC2
│   ├── posters/                           # 海报 2:3
│   ├── thumbs/                            # 缩略图 16:9
│   ├── backdrops/                         # 背景大图
│   ├── actors/                            # 演员头像
│   └── nfo/                               # NFO 元数据文件
│
├── server/                                # 后端（FastAPI）
│   ├── __init__.py
│   ├── main.py                            # 入口：app 实例、生命周期、中间件
│   ├── config.py                          # 配置管理（路径、端口、常量）
│   ├── database.py                        # SQLite 连接池、初始化、迁移
│   ├── models.py                          # Pydantic 数据模型（请求/响应）
│   │
│   ├── api/                               # API 路由层
│   │   ├── __init__.py
│   │   ├── router.py                      # 总路由注册
│   │   ├── videos.py                      # /api/videos 增删改查
│   │   ├── stream.py                      # /api/stream/{id} 206 流
│   │   ├── images.py                      # /api/images/{path} 静态图
│   │   ├── history.py                     # /api/history 观看历史
│   │   ├── actors.py                      # /api/actors
│   │   ├── tags.py                        # /api/tags
│   │   ├── series.py                      # /api/series
│   │   ├── scraper_api.py                 # /api/scraper 刮削控制
│   │   └── system.py                      # /api/system 系统状态
│   │
│   ├── scraper/                           # 刮削引擎
│   │   ├── __init__.py
│   │   ├── pipeline.py                    # 刮削流水线调度
│   │   ├── scanner.py                     # 文件扫描器
│   │   ├── bangou_parser.py               # 番号解析器
│   │   ├── persister.py                   # 结果持久化 + 封面处理
│   │   ├── nfo_handler.py                 # NFO 读写
│   │   ├── image_processor.py             # 封面裁切 / 缩放
│   │   └── sources/                       # 各数据源适配器
│   │       ├── __init__.py
│   │       ├── base.py                    # 数据源基类（接口定义）
│   │       ├── javbus.py                  # JavBus 刮削器
│   │       ├── javdb.py                   # JavDB 刮削器
│   │       ├── dmm.py                     # DMM 刮削器
│   │       ├── javbus_uncensored.py       # JavBus 无码区
│   │       ├── caribbean.py               # 加勒比
│   │       ├── pondo.py                   # 一本道
│   │       ├── heyzo.py                   # HEYZO
│   │       ├── fc2hub.py                  # FC2Hub
│   │       └── javdb_fc2.py               # JavDB FC2 区
│   │
│   ├── services/                          # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── video_service.py               # 影片 CRUD 逻辑
│   │   ├── history_service.py             # 观看历史逻辑
│   │   └── stats_service.py               # 统计聚合
│   │
│   ├── utils/                             # 工具函数
│   │   ├── __init__.py
│   │   ├── ffprobe.py                     # ffprobe 异步封装
│   │   ├── http_client.py                 # httpx 全局客户端
│   │   └── logger.py                      # 日志配置
│   │
│   └── requirements.txt                   # Python 依赖
│       # fastapi>=0.115
│       # uvicorn[standard]>=0.30
│       # aiosqlite>=0.20
│       # aiofiles>=24.1
│       # httpx>=0.27
│       # Pillow>=10.0
│       # pydantic>=2.8
│       # python-multipart>=0.0.9
│
├── frontend/                              # 前端（Vue 3）
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── vite.config.ts                     # Vite 配置（代理、PWA 插件）
│   ├── tailwind.config.ts                 # Tailwind CSS v4 配置
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── env.d.ts
│   ├── capacitor.config.ts                # Capacitor 配置
│   │
│   ├── index.html                         # 入口 HTML（PWA meta）
│   │
│   ├── public/
│   │   ├── manifest.json                  # PWA Manifest
│   │   ├── favicon.ico
│   │   ├── icons/
│   │   │   ├── icon-192.png
│   │   │   ├── icon-512.png
│   │   │   ├── icon-maskable-512.png
│   │   │   └── apple-touch-icon.png
│   │   └── splash/                        # iOS 启动屏
│   │       ├── splash-1170x2532.png
│   │       ├── splash-1179x2556.png
│   │       └── ...
│   │
│   ├── src/
│   │   ├── main.ts                        # 入口：createApp、插件注册
│   │   ├── App.vue                        # 根组件
│   │   ├── style.css                      # 全局样式（CSS 变量、Tailwind @import）
│   │   │
│   │   ├── router/
│   │   │   └── index.ts                   # Vue Router 路由表
│   │   │
│   │   ├── stores/                        # Pinia 状态
│   │   │   ├── video.ts                   # 影片列表 / 详情
│   │   │   ├── player.ts                  # 播放器状态
│   │   │   ├── history.ts                 # 观看历史
│   │   │   └── app.ts                     # 全局 App 状态（主题、设备信息）
│   │   │
│   │   ├── pages/                         # 页面视图
│   │   │   ├── HomePage.vue               # 首页（继续观看 + 最新 + 推荐）
│   │   │   ├── LibraryPage.vue            # 全部影片（海报墙 + 筛选）
│   │   │   ├── FavoritesPage.vue          # 收藏夹
│   │   │   ├── HistoryPage.vue            # 观看历史
│   │   │   ├── ActorsPage.vue             # 演员列表
│   │   │   ├── ActorDetailPage.vue        # 演员详情 + 作品
│   │   │   ├── SearchPage.vue             # 搜索
│   │   │   ├── SettingsPage.vue           # 设置（扫描、刮削、关于）
│   │   │   └── PlayerPage.vue             # 全屏播放器页面
│   │   │
│   │   ├── components/                    # 组件（见 3.2.2 组件树）
│   │   │   ├── layout/
│   │   │   │   ├── AppLayout.vue
│   │   │   │   ├── TabBar.vue
│   │   │   │   └── PageHeader.vue
│   │   │   ├── video/
│   │   │   │   ├── PosterCard.vue
│   │   │   │   ├── PosterGrid.vue
│   │   │   │   ├── VideoDetailDrawer.vue
│   │   │   │   ├── VideoMeta.vue
│   │   │   │   └── ProgressBar.vue
│   │   │   ├── player/
│   │   │   │   ├── VideoPlayer.vue
│   │   │   │   ├── PlayerControls.vue
│   │   │   │   ├── GestureOverlay.vue
│   │   │   │   └── ProgressSlider.vue
│   │   │   ├── browse/
│   │   │   │   ├── ActorCard.vue
│   │   │   │   ├── TagPill.vue
│   │   │   │   ├── FilterBar.vue
│   │   │   │   └── SearchInput.vue
│   │   │   └── common/
│   │   │       ├── LazyImage.vue
│   │   │       ├── InfiniteScroll.vue
│   │   │       ├── BottomSheet.vue
│   │   │       ├── Skeleton.vue
│   │   │       └── EmptyState.vue
│   │   │
│   │   ├── composables/                   # 组合式函数
│   │   │   ├── useApi.ts                  # API 请求封装（fetch + 错误处理）
│   │   │   ├── usePlayerGestures.ts       # 播放器手势
│   │   │   ├── useNativePlayer.ts         # 安卓原生播放器桥接
│   │   │   ├── useInfiniteScroll.ts       # 无限滚动逻辑
│   │   │   ├── usePlatform.ts             # 平台检测（iOS PWA / Android / Web）
│   │   │   └── useDebounce.ts             # 防抖 / 节流
│   │   │
│   │   ├── api/                           # API 类型 & 调用封装
│   │   │   ├── client.ts                  # 基础 HTTP 客户端配置
│   │   │   ├── videos.ts                  # 影片 API
│   │   │   ├── history.ts                 # 历史 API
│   │   │   ├── actors.ts                  # 演员 API
│   │   │   ├── scraper.ts                 # 刮削 API
│   │   │   └── system.ts                  # 系统 API
│   │   │
│   │   ├── types/                         # TypeScript 类型定义
│   │   │   ├── video.ts
│   │   │   ├── actor.ts
│   │   │   ├── tag.ts
│   │   │   ├── history.ts
│   │   │   └── api.ts                     # 通用 API 响应类型
│   │   │
│   │   └── utils/                         # 前端工具
│   │       ├── format.ts                  # 格式化（时间、文件大小等）
│   │       ├── constants.ts               # 常量
│   │       └── platform.ts                # 平台判断辅助
│   │
│   ├── android/                           # Capacitor Android 工程
│   │   ├── app/
│   │   │   ├── src/main/
│   │   │   │   ├── AndroidManifest.xml
│   │   │   │   ├── java/com/yaoyao/cinema/
│   │   │   │   │   ├── MainActivity.kt
│   │   │   │   │   ├── PlayerActivity.kt
│   │   │   │   │   └── plugins/
│   │   │   │   │       └── NativePlayerPlugin.kt
│   │   │   │   └── res/
│   │   │   │       ├── layout/
│   │   │   │       │   └── activity_player.xml
│   │   │   │       ├── values/
│   │   │   │       │   ├── strings.xml
│   │   │   │       │   ├── styles.xml
│   │   │   │       │   └── colors.xml
│   │   │   │       └── drawable/
│   │   │   └── build.gradle.kts
│   │   ├── build.gradle.kts
│   │   ├── settings.gradle.kts
│   │   └── gradle.properties
│   │
│   └── dist/                              # 构建产物（gitignore）
│       └── ...
│
├── scripts/                               # 运维脚本
│   ├── start.sh                           # 启动服务端 + 前端构建
│   ├── stop.sh                            # 停止服务
│   ├── scan.sh                            # 触发文件扫描
│   ├── backup-db.sh                       # 数据库备份
│   └── setup.sh                           # 首次初始化环境
│
└── .gitignore
```

---

## 6. 分步开发任务清单

> 以下任务按照**严格串行依赖**排列。每个任务完成后应可独立验证通过。
> 估时仅为参考，实际执行由 DeepSeek / Cursor 等编码代理完成。

### Phase 0：项目骨架与环境（约 2h）

| # | 任务 | 输出物 | 验证标准 |
|---|------|--------|----------|
| 0.1 | 创建项目目录结构（完整如第 5 章） | 全部空目录 + `__init__.py` | `tree` 输出匹配 |
| 0.2 | 编写 `server/requirements.txt` 并创建 venv | Python 虚拟环境 | `pip install -r requirements.txt` 无报错 |
| 0.3 | 初始化前端项目：`pnpm create vite frontend --template vue-ts` | 前端骨架 | `pnpm dev` 可启动 |
| 0.4 | 安装前端依赖：Tailwind v4、Pinia、VueRouter、VueUse、vite-plugin-pwa | `package.json` 更新 | 依赖安装无冲突 |
| 0.5 | 编写 `.gitignore`、`Makefile`、`scripts/start.sh` | 运维文件 | `make help` 可用 |

### Phase 1：服务端核心（约 6h）

| # | 任务 | 输出物 | 验证标准 |
|---|------|--------|----------|
| 1.1 | 实现 `config.py`：路径常量、端口、环境变量读取 | 配置模块 | 可 import 并打印配置 |
| 1.2 | 实现 `database.py`：SQLite 连接池 + 全部建表 DDL + WAL 开启 | DB 初始化 | 启动后 `yaoyao.db` 生成、6 张表存在 |
| 1.3 | 实现 `models.py`：全部 Pydantic 请求/响应模型 | 类型定义 | 类型检查通过 |
| 1.4 | 实现 `main.py`：FastAPI app、lifespan、CORS、静态文件挂载 | 入口文件 | `uvicorn server.main:app` 可启动 |
| 1.5 | 实现 `api/stream.py`：HTTP 206 分块流 | 流媒体端点 | `curl -H "Range: bytes=0-1000" .../api/stream/{id}` 返回 206 |
| 1.6 | 实现 `api/videos.py`：CRUD + 分页 + 筛选 + 排序 | 影片 API | Swagger UI 可交互测试 |
| 1.7 | 实现 `api/history.py`：进度上报 + 续播查询 | 历史 API | 上报后查询可返回最新进度 |
| 1.8 | 实现 `api/images.py`：静态图片伺服 | 图片端点 | 浏览器可加载海报图 |
| 1.9 | 实现 `api/actors.py`, `tags.py`, `series.py` | 分类 API | 列表查询含影片计数 |
| 1.10 | 实现 `api/system.py`：健康检查 + 统计 | 系统 API | `/api/system/health` 返回 OK |

### Phase 2：刮削引擎（约 8h）

| # | 任务 | 输出物 | 验证标准 |
|---|------|--------|----------|
| 2.1 | 实现 `scraper/scanner.py`：文件遍历 + ffprobe 探测 | 扫描器 | 扫描 media 目录，新文件入库 |
| 2.2 | 实现 `scraper/bangou_parser.py`：番号正则提取 | 解析器 | 测试用例覆盖所有番号格式 |
| 2.3 | 实现 `scraper/sources/base.py`：数据源基类定义 | 接口规范 | 抽象方法完整 |
| 2.4 | 实现 `scraper/sources/javbus.py`：JavBus 有码刮削 | 刮削器 | 输入 `OPPENHEIMER-2023` 返回完整结构 |
| 2.5 | 实现 `scraper/sources/javdb.py`：JavDB 刮削 | 刮削器 | 输入番号返回数据 |
| 2.6 | 实现 `scraper/sources/fc2hub.py` + `javdb_fc2.py` | FC2 刮削器 | FC2 番号可刮削 |
| 2.7 | 实现 `scraper/sources/javbus_uncensored.py` 等无码源 | 无码刮削器 | 无码番号可刮削 |
| 2.8 | 实现 `scraper/image_processor.py`：2:3 智能裁切 | 图片处理 | 横版大图正确裁出竖版海报 |
| 2.9 | 实现 `scraper/nfo_handler.py`：NFO 读写 | NFO 处理 | 可读取/生成标准 NFO |
| 2.10 | 实现 `scraper/persister.py`：结果持久化 | 数据落库 | 刮削结果完整写入 DB + 图片下载 |
| 2.11 | 实现 `scraper/pipeline.py`：流水线调度 | 主调度器 | 端到端：文件 → 番号 → 刮削 → 入库 |
| 2.12 | 实现 `api/scraper_api.py`：刮削控制 API | 刮削 API | POST 触发扫描/刮削并返回状态 |

### Phase 3：前端基础框架（约 5h）

| # | 任务 | 输出物 | 验证标准 |
|---|------|--------|----------|
| 3.1 | 配置 Tailwind v4 + CSS 变量系统（3.1 章全部 Token） | 样式基础 | CSS 变量在浏览器 DevTools 可见 |
| 3.2 | 实现 `AppLayout.vue` + `TabBar.vue`（底部 5 Tab） | 布局壳 | 5 个 Tab 可点击切换路由 |
| 3.3 | 实现 `src/router/index.ts`：完整路由表 | 路由 | 各页面可导航 |
| 3.4 | 实现 `src/api/client.ts`：fetch 封装 + 错误处理 | HTTP 客户端 | 可调用后端 API |
| 3.5 | 实现 Pinia stores：`video.ts`, `player.ts`, `history.ts` | 状态管理 | Store 可挂载并响应 |
| 3.6 | 实现通用组件：`LazyImage`, `Skeleton`, `InfiniteScroll`, `EmptyState` | 基础组件 | 组件可独立渲染 |

### Phase 4：前端页面与交互（约 8h）

| # | 任务 | 输出物 | 验证标准 |
|---|------|--------|----------|
| 4.1 | 实现 `PosterCard.vue` + `PosterGrid.vue`（响应式网格） | 海报组件 | iPhone/iPad/Desktop 列数正确 |
| 4.2 | 实现 `LibraryPage.vue`：全部影片 + 排序 + 筛选 + 无限滚动 | 主页面 | 滚动加载、排序切换流畅 |
| 4.3 | 实现 `VideoDetailDrawer.vue`：底部上滑详情面板 | 详情抽屉 | 点击卡片弹出、显示元数据、可播放 |
| 4.4 | 实现 `HomePage.vue`：继续观看横条 + 最新入库 + 按系列推荐 | 首页 | 续播列表有数据、布局美观 |
| 4.5 | 实现 `PlayerPage.vue` + `VideoPlayer.vue`：HTML5 全屏播放器 | 播放器 | 视频可播放、进度条可拖动 |
| 4.6 | 实现 `GestureOverlay.vue` + `usePlayerGestures.ts` | 手势系统 | 双击快进、滑动调音量/亮度 |
| 4.7 | 实现进度上报：播放中每 10s 自动上报 + 离开时上报 | 续播功能 | 关闭播放器再进入可续播 |
| 4.8 | 实现 `FavoritesPage.vue`, `HistoryPage.vue` | 收藏 & 历史 | 收藏/取消反映即时、历史时间线正确 |
| 4.9 | 实现 `ActorsPage.vue` + `ActorDetailPage.vue` | 演员页 | 圆形头像网格、点击查看作品 |
| 4.10 | 实现 `SearchPage.vue`：即时搜索（防抖 300ms） | 搜索 | 输入关键词实时出结果 |
| 4.11 | 实现 `SettingsPage.vue`：手动触发扫描/刮削、查看状态 | 设置 | 点击扫描可触发后端任务 |
| 4.12 | 实现 `FilterBar.vue`：排序方式 + 标签筛选 + 演员筛选 | 筛选栏 | 切换筛选条件列表即时刷新 |

### Phase 5：PWA 封装（约 2h）

| # | 任务 | 输出物 | 验证标准 |
|---|------|--------|----------|
| 5.1 | 配置 `vite-plugin-pwa` + Service Worker 缓存策略 | PWA 支持 | Lighthouse PWA 评分 ≥ 90 |
| 5.2 | 制作 PWA 图标全套（192/512/maskable/apple-touch） | 图标文件 | iOS 添加到桌面图标正确 |
| 5.3 | 制作 iOS Splash 启动图（主要 iPhone 尺寸） | 启动图 | 冷启动无白屏 |
| 5.4 | 测试 Safari PWA standalone 模式 | — | 无地址栏、全屏体验、视频可播放 |

### Phase 6：安卓 Capacitor 封装（约 4h）

| # | 任务 | 输出物 | 验证标准 |
|---|------|--------|----------|
| 6.1 | `npx cap init` + `npx cap add android` | 安卓工程 | `npx cap sync` 无报错 |
| 6.2 | 配置 `capacitor.config.ts`（允许局域网混合内容） | 配置文件 | WebView 可加载 NAS API |
| 6.3 | 实现 `NativePlayerPlugin.kt` + `PlayerActivity.kt` | 原生插件 | 可从 WebView 调起原生播放器 |
| 6.4 | 实现 `useNativePlayer.ts` 前端桥接 | 桥接层 | 安卓端点击播放调用原生、返回进度 |
| 6.5 | ExoPlayer 配置：硬件解码优先、HTTP Range 数据源 | 播放器 | 4K HEVC 硬解流畅 |
| 6.6 | AndroidManifest 配置：网络权限、横屏、全屏主题 | Manifest | App 可安装并正常运行 |
| 6.7 | 构建签名 APK 并测试 | APK 文件 | 真机安装可用 |

### Phase 7：联调与优化（约 3h）

| # | 任务 | 输出物 | 验证标准 |
|---|------|--------|----------|
| 7.1 | 端到端联调：扫描 → 刮削 → 海报展示 → 播放 → 续播 | — | 完整链路走通 |
| 7.2 | iOS Safari PWA 播放兼容性测试（特别是 Range 请求） | — | iPhone 可流畅播放 |
| 7.3 | 安卓 App 播放兼容性测试（MKV/MP4/HEVC/H.264） | — | 主流格式均可硬解 |
| 7.4 | 海报网格性能优化：虚拟滚动（若 >500 部则引入） | — | 1000+ 海报滚动 60fps |
| 7.5 | 编写启动脚本 `scripts/start.sh` + systemd service | 运维脚本 | NAS 重启后服务自动恢复 |

---

### 总估时汇总

| Phase | 主题 | 估时 |
|-------|------|------|
| 0 | 项目骨架 | ~2h |
| 1 | 服务端核心 | ~6h |
| 2 | 刮削引擎 | ~8h |
| 3 | 前端基础 | ~5h |
| 4 | 前端页面 | ~8h |
| 5 | PWA 封装 | ~2h |
| 6 | 安卓封装 | ~4h |
| 7 | 联调优化 | ~3h |
| **总计** | | **~38h** |

---

> **本文档为夭夭影社全部工程实现的唯一架构真相来源（Single Source of Architectural Truth）。**
> **后续任何编码工作应严格遵循此架构，如有偏离需先修订本文档。**
> 
> *为 TIAN 而造，唯此一家。* 🎬