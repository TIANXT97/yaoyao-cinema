"""夭夭影社 · 标签 API（ARCHITECTURE.md 2.5.5）。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from ..database import Database, get_db

router = APIRouter(tags=["tags"])


@router.get("/tags")
async def list_tags(
    category: Optional[str] = Query(None),
    db: Database = Depends(get_db),
) -> list[dict[str, Any]]:
    """标签列表（带影片计数）。"""
    sql = (
        "SELECT t.*, "
        "       (SELECT COUNT(*) FROM video_tags vt WHERE vt.tag_id = t.id) "
        "           AS video_count "
        "FROM tags t"
    )
    params: list[Any] = []
    if category:
        sql += " WHERE t.category = ?"
        params.append(category)
    sql += " ORDER BY video_count DESC, t.name ASC"
    return await db.fetchall(sql, tuple(params))
