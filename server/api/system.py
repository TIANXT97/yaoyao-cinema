"""夭夭影社 · 系统 API（ARCHITECTURE.md 2.5.6）。

``GET /api/studios`` 亦归入系统 / 分类聚合，复用 stats_service。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..database import Database, get_db
from ..models import HealthResponse, SystemStats
from ..services import stats_service
from ..services.stats_service import get_stats

router = APIRouter(tags=["system"])


@router.get("/system/stats", response_model=SystemStats)
async def system_stats(
    db: Database = Depends(get_db),
) -> SystemStats:
    """系统统计（总数、大小、刮削进度）。"""
    return SystemStats(**await get_stats(db))


@router.get("/system/health", response_model=HealthResponse)
async def system_health(
    db: Database = Depends(get_db),
) -> HealthResponse:
    """健康检查。"""
    database = "connected" if db.is_connected else "disconnected"
    try:
        await db.fetchvalue("SELECT 1")
        database = "ok"
    except Exception:  # noqa: BLE001 - 健康检查需吞掉任何异常
        database = "error"
    return HealthResponse(status="ok", database=database)


@router.get("/studios")
async def list_studios(
    db: Database = Depends(get_db),
) -> list[dict[str, Any]]:
    """制作商列表（从 videos 聚合）。"""
    return await stats_service.list_studios(db)
