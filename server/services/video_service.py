"""夭夭影社 · 影片业务逻辑（ARCHITECTURE.md 2.5.1）。

只负责查询拼装，不含任何 HTTP 语义。
"""

from __future__ import annotations

from typing import Any, Optional

from .. import config
from ..database import Database

# ARCHITECTURE.md 2.5.1 允许的排序字段白名单
SORTABLE_COLUMNS: dict[str, str] = {
    "date_added": "v.date_added",
    "release_date": "v.release_date",
    "title": "v.title",
    "rating": "v.rating",
    "play_count": "v.play_count",
    "last_played": "v.last_played",
    "file_size": "v.file_size",
}

_RESUME_COMPLETED_THRESHOLD = 0.9


def _clamp_pagination(page: int, per_page: int) -> tuple[int, int]:
    page = max(1, int(page or 1))
    per_page = int(per_page or config.DEFAULT_PER_PAGE)
    per_page = max(1, min(per_page, config.MAX_PER_PAGE))
    return page, per_page


def _normalize_sort(sort: str, order: str) -> tuple[str, str]:
    column = SORTABLE_COLUMNS.get(sort, SORTABLE_COLUMNS["date_added"])
    direction = "ASC" if str(order).lower() == "asc" else "DESC"
    return column, direction


async def list_videos(
    db: Database,
    *,
    page: int = 1,
    per_page: int = config.DEFAULT_PER_PAGE,
    sort: str = "date_added",
    order: str = "desc",
    search: Optional[str] = None,
    actor_id: Optional[str] = None,
    tag_id: Optional[str] = None,
    series_id: Optional[str] = None,
    studio: Optional[str] = None,
    favorite: Optional[bool] = None,
    status: Optional[str] = None,
) -> tuple[list[dict[str, Any]], int]:
    """分页 + 排序 + 筛选查询影片列表，返回 (items, total)。"""
    page, per_page = _clamp_pagination(page, per_page)
    column, direction = _normalize_sort(sort, order)

    where: list[str] = ["v.is_hidden = 0"]
    params: list[Any] = []

    if search:
        like = f"%{search.strip()}%"
        where.append(
            "(v.title LIKE ? OR v.original_title LIKE ? OR v.bangou LIKE ? "
            "OR v.bangou_norm LIKE ? OR EXISTS ("
            "  SELECT 1 FROM video_actors va JOIN actors a ON a.id = va.actor_id"
            "  WHERE va.video_id = v.id AND a.name LIKE ?))"
        )
        params.extend([like, like, like, like, like])

    if actor_id:
        where.append(
            "EXISTS (SELECT 1 FROM video_actors va WHERE va.video_id = v.id "
            "AND va.actor_id = ?)"
        )
        params.append(actor_id)

    if tag_id:
        where.append(
            "EXISTS (SELECT 1 FROM video_tags vt WHERE vt.video_id = v.id "
            "AND vt.tag_id = ?)"
        )
        params.append(tag_id)

    if series_id:
        where.append("v.series_id = ?")
        params.append(series_id)

    if studio:
        where.append("v.studio = ?")
        params.append(studio)

    if favorite is not None:
        where.append("v.is_favorite = ?")
        params.append(1 if favorite else 0)

    if status:
        where.append("v.scrape_status = ?")
        params.append(status)

    where_sql = " WHERE " + " AND ".join(where)

    total_row = await db.fetchone(
        f"SELECT COUNT(*) AS total FROM videos v{where_sql}", tuple(params)
    )
    total = int(total_row["total"]) if total_row else 0

    offset = (page - 1) * per_page
    rows = await db.fetchall(
        f"SELECT v.* FROM videos v{where_sql} "
        f"ORDER BY {column} {direction}, v.id ASC LIMIT ? OFFSET ?",
        tuple(params) + (per_page, offset),
    )
    return rows, total


async def get_video_detail(
    db: Database, video_id: str
) -> Optional[dict[str, Any]]:
    """影片详情：主记录 + 演员 + 标签 + 系列 + 最新续播点。"""
    video = await db.get_video(video_id)
    if video is None:
        return None

    actors = await db.fetchall(
        "SELECT a.* FROM actors a "
        "JOIN video_actors va ON va.actor_id = a.id "
        "WHERE va.video_id = ? ORDER BY a.name ASC",
        (video_id,),
    )
    tags = await db.fetchall(
        "SELECT t.* FROM tags t "
        "JOIN video_tags vt ON vt.tag_id = t.id "
        "WHERE vt.video_id = ? ORDER BY t.name ASC",
        (video_id,),
    )
    series = None
    if video.get("series_id"):
        series = await db.fetchone(
            "SELECT * FROM series WHERE id = ?", (video["series_id"],)
        )

    resume = await db.fetchone(
        "SELECT position, duration, progress FROM watch_history "
        "WHERE video_id = ? ORDER BY watched_at DESC LIMIT 1",
        (video_id,),
    )

    detail = dict(video)
    detail["actors"] = actors
    detail["tags"] = tags
    detail["series"] = series
    detail["resume_position"] = int(resume["position"]) if resume else 0
    detail["resume_progress"] = float(resume["progress"]) if resume else 0.0
    return detail


async def update_video(
    db: Database, video_id: str, fields: dict[str, Any]
) -> bool:
    """更新影片元数据；返回是否存在该记录。"""
    video = await db.get_video(video_id)
    if video is None:
        return False
    cleaned = {k: v for k, v in fields.items() if v is not None}
    if cleaned:
        await db.update_video(video_id, cleaned)
    return True


async def delete_video(db: Database, video_id: str) -> bool:
    """删除影片记录（不删除磁盘文件）。关联表由外键级联删除。"""
    video = await db.get_video(video_id)
    if video is None:
        return False
    await db.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    return True


async def toggle_favorite(db: Database, video_id: str) -> Optional[int]:
    """切换收藏状态，返回新的 is_favorite 值。"""
    video = await db.get_video(video_id)
    if video is None:
        return None
    new_value = 0 if int(video.get("is_favorite") or 0) else 1
    await db.update_video(video_id, {"is_favorite": new_value})
    return new_value


async def toggle_hidden(db: Database, video_id: str) -> Optional[int]:
    """切换隐藏状态，返回新的 is_hidden 值。"""
    video = await db.get_video(video_id)
    if video is None:
        return None
    new_value = 0 if int(video.get("is_hidden") or 0) else 1
    await db.update_video(video_id, {"is_hidden": new_value})
    return new_value
