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
PRIVATE_CATEGORY = "local"
_RESUME_PROGRESS_SQL = (
    "COALESCE((SELECT h.progress FROM watch_history h WHERE h.video_id = v.id "
    "ORDER BY h.watched_at DESC, h.rowid DESC LIMIT 1), 0) AS resume_progress"
)

# 二级分类导航顺序（与前端 CategoryNav 胶囊一一对应）
CATEGORY_ORDER: tuple[str, ...] = ("movie", "c_drama", "k_drama", "w_drama", "local")


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
    category: Optional[str] = None,
    group_series: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """分页 + 排序 + 筛选查询影片列表，返回 (items, total)。

    ``category`` 为二级分类过滤（movie / c_drama / k_drama / w_drama / local）；
    为空或 ``'all'`` 时默认排除私房(``local``)。``group_series=True`` 时聚合逻辑不变：
    同一剧集的分集目录同属一个分类，因此聚合卡片不会跨分类被拆散。

    ``group_series=True`` 时进入「聚合展示模式」：
    - 电影 / 未绑定系列的独立视频（``series_id IS NULL``）按单部返回；
    - 属于某剧集的视频按 ``series_id`` 聚合为一条记录，
      ``title`` 取系列名、``poster_path`` 取 ``series.poster_path``，
      并附带 ``is_series=True`` / ``episode_count``。
    """
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

    normalized_category = str(category).strip() if category else ""
    if normalized_category in ("", "all"):
        where.append("COALESCE(v.category, '') != ?")
        params.append(PRIVATE_CATEGORY)
    else:
        where.append("v.category = ?")
        params.append(normalized_category)

    where_sql = " WHERE " + " AND ".join(where)

    if group_series and not series_id:
        return await _list_videos_grouped(
            db, where_sql, params, column, direction, page, per_page
        )

    total_row = await db.fetchone(
        f"SELECT COUNT(*) AS total FROM videos v{where_sql}", tuple(params)
    )
    total = int(total_row["total"]) if total_row else 0

    offset = (page - 1) * per_page
    rows = await db.fetchall(
        f"SELECT v.*, {_RESUME_PROGRESS_SQL} FROM videos v{where_sql} "
        f"ORDER BY {column} {direction}, v.id ASC LIMIT ? OFFSET ?",
        tuple(params) + (per_page, offset),
    )
    return rows, total

async def _list_videos_grouped(
    db: Database,
    where_sql: str,
    params: list[Any],
    column: str,
    direction: str,
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], int]:
    """按系列聚合的分页查询（内部实现，供 ``list_videos`` 调用）。"""
    base_sql = (
        "WITH filtered AS (SELECT v.*, " + _RESUME_PROGRESS_SQL + " FROM videos v" + where_sql + "), "
        "ranked AS ("
        "  SELECT f.*,"
        "         CASE WHEN f.series_id IS NULL THEN 0 ELSE 1 END AS is_series,"
        "         CASE WHEN f.series_id IS NULL THEN 1"
        "              ELSE COUNT(*) OVER (PARTITION BY f.series_id) END"
        "              AS episode_count,"
        "         ROW_NUMBER() OVER ("
        "             PARTITION BY COALESCE(f.series_id, 'video:' || f.id)"
        "             ORDER BY f.file_name ASC, f.id ASC"
        "         ) AS rn"
        "  FROM filtered f"
        ") "
        "SELECT v.*, s.name AS _series_name, s.poster_path AS _series_poster "
        "FROM ranked v LEFT JOIN series s ON s.id = v.series_id "
        "WHERE v.rn = 1"
    )

    total_row = await db.fetchone(
        f"SELECT COUNT(*) AS total FROM ({base_sql})", tuple(params)
    )
    total = int(total_row["total"]) if total_row else 0

    offset = (page - 1) * per_page
    rows = await db.fetchall(
        f"{base_sql} ORDER BY {column} {direction}, v.id ASC LIMIT ? OFFSET ?",
        tuple(params) + (per_page, offset),
    )

    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        series_name = item.pop("_series_name", None)
        series_poster = item.pop("_series_poster", None)
        item["is_series"] = bool(item.get("is_series"))
        item["episode_count"] = int(item.get("episode_count") or 1)
        if item["is_series"]:
            # 以剧集名与剧集专属海报覆盖代表分集的元数据
            if series_name:
                item["title"] = series_name
            if series_poster:
                item["poster_path"] = series_poster
                item["thumb_path"] = series_poster
        items.append(item)
    return items, total


async def get_category_summary(db: Database) -> dict[str, int]:
    """各二级分类的「部数」统计（与 ``group_series=True`` 口径一致）。

    返回形如 ``{"all": 94, "movie": 29, "c_drama": 33, "k_drama": 27,
    "w_drama": 3, "local": 2}``；同一剧集的多部分集只计 1 部，隐藏条目不计入。
    """
    rows = await db.fetchall(
        "SELECT COALESCE(NULLIF(category, ''), 'other') AS category, "
        "       COUNT(DISTINCT COALESCE(series_id, id)) AS cnt "
        "FROM videos WHERE is_hidden = 0 GROUP BY category"
    )
    counts: dict[str, int] = {str(r["category"]): int(r["cnt"] or 0) for r in rows}

    total_row = await db.fetchone(
        "SELECT COUNT(DISTINCT COALESCE(series_id, id)) AS total FROM videos "
        "WHERE is_hidden = 0 AND COALESCE(category, '') != 'local'"
    )

    summary: dict[str, int] = {"all": int((total_row or {}).get("total") or 0)}
    for key in CATEGORY_ORDER:
        summary[key] = counts.pop(key, 0)
    # 兼容历史库可能残留的 other 等未知分类，保证角标总数不丢票
    summary.update({key: value for key, value in counts.items() if value})
    return summary

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
        "WHERE video_id = ? ORDER BY watched_at DESC, rowid DESC LIMIT 1",
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
