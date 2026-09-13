"""夭夭影社 · 系列 API（ARCHITECTURE.md 2.5.5）。"""

from __future__ import annotations

import os
import re

from fastapi import APIRouter, Depends, HTTPException

from ..database import Database, get_db
from ..models import SeriesOut, VideoOut

router = APIRouter(tags=["series"])

# 分集序号识别：S01E02 / E02 / EP02 / 第02集 等
_EPISODE_PATTERNS = (
    re.compile(r"(?:S\d+)?E(?:P)?\s*0*(\d+)", re.IGNORECASE),
    re.compile(r"第\s*0*(\d+)\s*[集话話]"),
    re.compile(r"(\d+)"),
)

def _episode_sort_key(row: dict) -> tuple[int, int, str]:
    """按集数自然排序：优先解析 SxxExx / 第N集，其次文件内首个数字。"""
    raw = row.get("file_name") or row.get("title") or ""
    stem = os.path.splitext(str(raw))[0]
    for pattern in _EPISODE_PATTERNS:
        match = pattern.search(stem)
        if match:
            return (0, int(match.group(1)), stem)
    return (1, 0, stem)

@router.get("/series", response_model=list[SeriesOut])
async def list_series(
    db: Database = Depends(get_db),
) -> list[SeriesOut]:
    """系列列表（series.video_count 由触发器维护）。"""
    rows = await db.fetchall(
        "SELECT * FROM series ORDER BY video_count DESC, name ASC"
    )
    return [SeriesOut(**row) for row in rows]

@router.get("/series/{series_id}/episodes", response_model=list[VideoOut])
async def list_series_episodes(
    series_id: str,
    db: Database = Depends(get_db),
) -> list[VideoOut]:
    """剧集详情：返回该系列下按集数自然排序的全部分集。"""
    series = await db.fetchone("SELECT * FROM series WHERE id = ?", (series_id,))
    if series is None:
        raise HTTPException(status_code=404, detail="系列不存在")

    rows = await db.fetchall(
        "SELECT * FROM videos WHERE series_id = ? AND is_hidden = 0",
        (series_id,),
    )
    rows.sort(key=_episode_sort_key)
    return [VideoOut(**row) for row in rows]
