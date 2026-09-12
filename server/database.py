"""夭夭影社 · SQLite 数据库连接池与建表 DDL。

严格对齐 docs/ARCHITECTURE.md 第 2.2 节「数据库表设计」：

* 数据库文件：``<PROJECT_ROOT>/data/yaoyao.db``
* 开库即启用 ``journal_mode = WAL`` / ``foreign_keys = ON`` / ``busy_timeout = 5000``
* 8 张表 + 索引 + 触发器（series.video_count、actors.video_count 由触发器维护）

注意：本模块 **不得** 擅自增删字段；表结构以 ARCHITECTURE.md 2.2 为唯一真相来源。
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping, Optional, Sequence

import aiosqlite

from . import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 建表 DDL（逐字对齐 ARCHITECTURE.md 2.2.1 ~ 2.2.8）
# ---------------------------------------------------------------------------

SCHEMA_SQL: str = """
-- 2.2.1 videos — 影片主表
CREATE TABLE IF NOT EXISTS videos (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    original_title  TEXT,
    sort_title      TEXT,
    bangou          TEXT,
    bangou_norm     TEXT,
    series_id       TEXT REFERENCES series(id),
    studio          TEXT,
    director        TEXT,
    release_date    TEXT,
    date_added      TEXT NOT NULL DEFAULT (datetime('now')),
    file_path       TEXT NOT NULL UNIQUE,
    file_name       TEXT NOT NULL,
    file_size       INTEGER NOT NULL DEFAULT 0,
    duration        INTEGER DEFAULT 0,
    resolution      TEXT,
    video_codec     TEXT,
    audio_codec     TEXT,
    container       TEXT,
    bitrate         INTEGER,
    poster_path     TEXT,
    thumb_path      TEXT,
    backdrop_path   TEXT,
    plot            TEXT,
    rating          REAL,
    scrape_status   TEXT DEFAULT 'pending',
    scrape_source   TEXT,
    scrape_time     TEXT,
    nfo_path        TEXT,
    play_count      INTEGER DEFAULT 0,
    last_played     TEXT,
    is_favorite     INTEGER DEFAULT 0,
    is_hidden       INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_videos_bangou_norm ON videos(bangou_norm);
CREATE INDEX IF NOT EXISTS idx_videos_release_date ON videos(release_date);
CREATE INDEX IF NOT EXISTS idx_videos_series ON videos(series_id);
CREATE INDEX IF NOT EXISTS idx_videos_scrape_status ON videos(scrape_status);
CREATE INDEX IF NOT EXISTS idx_videos_favorite ON videos(is_favorite);
CREATE INDEX IF NOT EXISTS idx_videos_added ON videos(date_added);

-- 2.2.2 series — 系列表
CREATE TABLE IF NOT EXISTS series (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    name_ja         TEXT,
    description     TEXT,
    poster_path     TEXT,
    video_count     INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 2.2.3 actors — 演员表
CREATE TABLE IF NOT EXISTS actors (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    name_ja         TEXT,
    aliases         TEXT,
    photo_path      TEXT,
    birth_date      TEXT,
    measurements    TEXT,
    cup_size        TEXT,
    height          INTEGER,
    nationality     TEXT,
    video_count     INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_actors_name ON actors(name);

-- 2.2.4 video_actors — 影片-演员关联
CREATE TABLE IF NOT EXISTS video_actors (
    video_id        TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    actor_id        TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
    PRIMARY KEY (video_id, actor_id)
);

-- 2.2.5 tags — 标签表
CREATE TABLE IF NOT EXISTS tags (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    name_ja         TEXT,
    category        TEXT DEFAULT 'genre',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 2.2.6 video_tags — 影片-标签关联
CREATE TABLE IF NOT EXISTS video_tags (
    video_id        TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    tag_id          TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (video_id, tag_id)
);

-- 2.2.7 watch_history — 观看历史
CREATE TABLE IF NOT EXISTS watch_history (
    id              TEXT PRIMARY KEY,
    video_id        TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    position        INTEGER NOT NULL DEFAULT 0,
    duration        INTEGER NOT NULL DEFAULT 0,
    progress        REAL NOT NULL DEFAULT 0,
    completed       INTEGER DEFAULT 0,
    watched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    device          TEXT
);

CREATE INDEX IF NOT EXISTS idx_watch_video ON watch_history(video_id);
CREATE INDEX IF NOT EXISTS idx_watch_time ON watch_history(watched_at);

-- 2.2.8 scraper_cache — 刮削缓存
CREATE TABLE IF NOT EXISTS scraper_cache (
    id              TEXT PRIMARY KEY,
    bangou_norm     TEXT NOT NULL,
    source          TEXT NOT NULL,
    raw_json        TEXT NOT NULL,
    fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT,
    UNIQUE(bangou_norm, source)
);

CREATE INDEX IF NOT EXISTS idx_cache_bangou ON scraper_cache(bangou_norm);
"""

# 冗余计数触发器（ARCHITECTURE.md 2.2.2 / 2.2.3 注明「触发器维护」）
TRIGGERS_SQL: str = """
CREATE TRIGGER IF NOT EXISTS trg_videos_series_insert
AFTER INSERT ON videos
WHEN new.series_id IS NOT NULL
BEGIN
    UPDATE series
       SET video_count = video_count + 1,
           updated_at  = datetime('now')
     WHERE id = new.series_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_videos_series_delete
AFTER DELETE ON videos
WHEN old.series_id IS NOT NULL
BEGIN
    UPDATE series
       SET video_count = video_count - 1,
           updated_at  = datetime('now')
     WHERE id = old.series_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_videos_series_update
AFTER UPDATE OF series_id ON videos
BEGIN
    UPDATE series
       SET video_count = video_count - 1,
           updated_at  = datetime('now')
     WHERE id = old.series_id AND old.series_id IS NOT NULL;
    UPDATE series
       SET video_count = video_count + 1,
           updated_at  = datetime('now')
     WHERE id = new.series_id AND new.series_id IS NOT NULL;
END;

CREATE TRIGGER IF NOT EXISTS trg_video_actors_insert
AFTER INSERT ON video_actors
BEGIN
    UPDATE actors
       SET video_count = video_count + 1,
           updated_at  = datetime('now')
     WHERE id = new.actor_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_video_actors_delete
AFTER DELETE ON video_actors
BEGIN
    UPDATE actors
       SET video_count = video_count - 1,
           updated_at  = datetime('now')
     WHERE id = old.actor_id;
END;
"""

# videos 表允许动态写入的列（防止手滑写入未知字段）
VIDEO_COLUMNS: frozenset[str] = frozenset(
    {
        "id",
        "title",
        "original_title",
        "sort_title",
        "bangou",
        "bangou_norm",
        "series_id",
        "studio",
        "director",
        "release_date",
        "date_added",
        "file_path",
        "file_name",
        "file_size",
        "duration",
        "resolution",
        "video_codec",
        "audio_codec",
        "container",
        "bitrate",
        "poster_path",
        "thumb_path",
        "backdrop_path",
        "plot",
        "rating",
        "scrape_status",
        "scrape_source",
        "scrape_time",
        "nfo_path",
        "play_count",
        "last_played",
        "is_favorite",
        "is_hidden",
        "created_at",
        "updated_at",
    }
)


class Database:
    """基于 ``aiosqlite`` 的轻量连接管理器（单连接 + WAL 并发读写）。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path: str = str(db_path or config.DB_PATH)
        self._conn: Optional[aiosqlite.Connection] = None

    # ---------------------------------------------------------------- 连接
    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("数据库尚未连接，请先 await db.connect()。")
        return self._conn

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    async def connect(self) -> aiosqlite.Connection:
        """建立连接并开启 WAL / 外键 / busy_timeout。"""
        if self._conn is not None:
            return self._conn

        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

        # 与 ARCHITECTURE.md 2.2 完全一致的 PRAGMA 序列
        await self._conn.execute("PRAGMA journal_mode = WAL;")
        await self._conn.execute("PRAGMA foreign_keys = ON;")
        await self._conn.execute("PRAGMA busy_timeout = 5000;")
        await self._conn.commit()
        return self._conn

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def init_schema(self) -> None:
        """建表 + 索引 + 触发器（幂等）。"""
        await self.conn.executescript(SCHEMA_SQL)
        await self.conn.executescript(TRIGGERS_SQL)
        await self.conn.commit()
        logger.info("数据库表结构初始化完成: %s", self.db_path)

    # ------------------------------------------------------------ 通用查询
    async def execute(
        self, sql: str, params: Sequence[Any] | Mapping[str, Any] = ()
    ) -> aiosqlite.Cursor:
        cursor = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cursor

    async def executemany(
        self, sql: str, params_seq: Iterable[Sequence[Any]]
    ) -> aiosqlite.Cursor:
        cursor = await self.conn.executemany(sql, params_seq)
        await self.conn.commit()
        return cursor

    async def executescript(self, script: str) -> None:
        await self.conn.executescript(script)
        await self.conn.commit()

    async def fetchall(
        self, sql: str, params: Sequence[Any] | Mapping[str, Any] = ()
    ) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(sql, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(row) for row in rows]

    async def fetchone(
        self, sql: str, params: Sequence[Any] | Mapping[str, Any] = ()
    ) -> Optional[dict[str, Any]]:
        cursor = await self.conn.execute(sql, params)
        row = await cursor.fetchone()
        await cursor.close()
        return dict(row) if row is not None else None

    async def fetchvalue(
        self, sql: str, params: Sequence[Any] | Mapping[str, Any] = ()
    ) -> Any:
        cursor = await self.conn.execute(sql, params)
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return row[0]

    # ------------------------------------------------------- videos 便捷方法
    async def get_video(self, video_id: str) -> Optional[dict[str, Any]]:
        return await self.fetchone("SELECT * FROM videos WHERE id = ?", (video_id,))

    async def get_video_by_path(self, file_path: str) -> Optional[dict[str, Any]]:
        return await self.fetchone(
            "SELECT * FROM videos WHERE file_path = ?", (file_path,)
        )

    async def get_all_video_paths(self) -> set[str]:
        rows = await self.fetchall("SELECT file_path FROM videos")
        return {row["file_path"] for row in rows}

    async def insert_video(self, record: Mapping[str, Any]) -> str:
        """按白名单动态插入一条 videos 记录，返回 id。"""
        data = {k: v for k, v in record.items() if k in VIDEO_COLUMNS}
        if not data:
            raise ValueError("insert_video 收到空记录")

        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        await self.execute(
            f"INSERT INTO videos ({columns}) VALUES ({placeholders})",
            tuple(data.values()),
        )
        return str(data["id"])

    async def update_video(
        self, video_id: str, fields: Mapping[str, Any]
    ) -> int:
        """按白名单动态更新 videos 字段，自动刷新 updated_at，返回受影响行数。"""
        data = {k: v for k, v in fields.items() if k in VIDEO_COLUMNS and k != "id"}
        if not data:
            return 0

        assignments = ", ".join(f"{key} = ?" for key in data)
        params = list(data.values())
        params.append(video_id)
        cursor = await self.execute(
            f"UPDATE videos SET {assignments}, updated_at = datetime('now') "
            f"WHERE id = ?",
            tuple(params),
        )
        return cursor.rowcount

    async def mark_missing(self, paths: Iterable[str]) -> None:
        """处理「文件已从磁盘消失」的影片。

        ARCHITECTURE.md 2.4.2 伪代码描述了 ``db.mark_missing(missing)``，但
        2.2.1 ``videos`` 表结构 **并未定义** missing 标记字段。为遵守
        「严禁擅自发明表结构」铁律，这里不新增列，仅记录告警日志，保留记录不删除。
        """
        missing = [p for p in paths if p]
        if missing:
            logger.warning(
                "检测到 %d 个影片文件已从磁盘消失（保留记录，不删除）: %s",
                len(missing),
                missing,
            )


# 全局单例：由 server.main lifespan 负责 connect / close
db = Database()


async def get_db() -> Database:
    """FastAPI 依赖：返回全局 Database 单例。"""
    return db
