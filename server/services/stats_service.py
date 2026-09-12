"""夭夭影社 · 统计聚合业务逻辑（ARCHITECTURE.md 2.5.6）。"""

from __future__ import annotations

from typing import Any

from .. import config
from ..database import Database


async def get_stats(db: Database) -> dict[str, Any]:
    """系统统计：影片总数 / 大小 / 收藏 / 已看 / 刮削进度 / 分类计数。"""
    video_row = await db.fetchone(
        "SELECT COUNT(*) AS total, "
        "       COALESCE(SUM(file_size), 0) AS total_size, "
        "       COALESCE(SUM(CASE WHEN is_favorite = 1 THEN 1 ELSE 0 END), 0) "
        "           AS favorites, "
        "       COALESCE(SUM(CASE WHEN play_count > 0 THEN 1 ELSE 0 END), 0) "
        "           AS watched, "
        "       COALESCE(SUM(CASE WHEN scrape_status = 'pending' THEN 1 ELSE 0 END), 0) "
        "           AS pending, "
        "       COALESCE(SUM(CASE WHEN scrape_status = 'matched' THEN 1 ELSE 0 END), 0) "
        "           AS matched, "
        "       COALESCE(SUM(CASE WHEN scrape_status = 'failed' THEN 1 ELSE 0 END), 0) "
        "           AS failed, "
        "       COALESCE(SUM(CASE WHEN scrape_status = 'manual' THEN 1 ELSE 0 END), 0) "
        "           AS manual "
        "FROM videos"
    ) or {}

    series_count = await db.fetchvalue("SELECT COUNT(*) FROM series")
    actors_count = await db.fetchvalue("SELECT COUNT(*) FROM actors")
    tags_count = await db.fetchvalue("SELECT COUNT(*) FROM tags")
    history_count = await db.fetchvalue("SELECT COUNT(*) FROM watch_history")

    return {
        "videos": {
            "total": int(video_row.get("total") or 0),
            "total_size": int(video_row.get("total_size") or 0),
            "favorites": int(video_row.get("favorites") or 0),
            "watched": int(video_row.get("watched") or 0),
            "pending": int(video_row.get("pending") or 0),
            "matched": int(video_row.get("matched") or 0),
            "failed": int(video_row.get("failed") or 0),
            "manual": int(video_row.get("manual") or 0),
        },
        "series": int(series_count or 0),
        "actors": int(actors_count or 0),
        "tags": int(tags_count or 0),
        "history_records": int(history_count or 0),
        "media_root": str(config.MEDIA_ROOT),
        "database_path": str(config.DB_PATH),
        "media_root_exists": config.MEDIA_ROOT.is_dir(),
    }


async def list_studios(db: Database) -> list[dict[str, Any]]:
    """制作商列表（从 videos 聚合，ARCHITECTURE.md 2.5.5）。"""
    return await db.fetchall(
        "SELECT studio AS name, COUNT(*) AS video_count "
        "FROM videos WHERE studio IS NOT NULL AND studio != '' "
        "GROUP BY studio ORDER BY video_count DESC, studio ASC"
    )
