"""夭夭影社 · 系列 API（ARCHITECTURE.md 2.5.5）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..database import Database, get_db
from ..models import SeriesOut

router = APIRouter(tags=["series"])


@router.get("/series", response_model=list[SeriesOut])
async def list_series(
    db: Database = Depends(get_db),
) -> list[SeriesOut]:
    """系列列表（series.video_count 由触发器维护）。"""
    rows = await db.fetchall(
        "SELECT * FROM series ORDER BY video_count DESC, name ASC"
    )
    return [SeriesOut(**row) for row in rows]
