"""夭夭影社 · 刮削控制 API（ARCHITECTURE.md 2.5.4）。

Phase 1 范围内仅实现文件扫描与任务状态查询；
``/scraper/scrape/{id}`` 与 ``/scraper/scrape-all`` 依赖 Phase 2 刮削引擎
（sources / pipeline / persister），此处返回 501 明确占位，不伪造实现。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..database import Database, get_db
from ..models import ScanResult
from ..scraper import scanner

router = APIRouter(tags=["scraper"])


@router.post("/scraper/scan", response_model=ScanResult)
async def trigger_scan(
    db: Database = Depends(get_db),
) -> ScanResult:
    """触发全库文件扫描。"""
    result = await scanner.scan_media_library(db)
    return ScanResult(**result)


@router.get("/scraper/status")
async def scraper_status() -> dict[str, Any]:
    """刮削 / 扫描任务状态。"""
    return scanner.get_status()


@router.post("/scraper/scrape/{video_id}")
async def scrape_one(video_id: str) -> None:
    """对单个影片执行刮削（Phase 2 实现）。"""
    raise HTTPException(
        status_code=501,
        detail="刮削引擎属于 Phase 2（scraper/pipeline.py），尚未实现",
    )


@router.post("/scraper/scrape-all")
async def scrape_all() -> None:
    """对所有 pending 影片批量刮削（Phase 2 实现）。"""
    raise HTTPException(
        status_code=501,
        detail="批量刮削属于 Phase 2（scraper/pipeline.py），尚未实现",
    )
