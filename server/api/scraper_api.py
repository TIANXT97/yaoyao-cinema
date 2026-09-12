"""夭夭影社 · 刮削控制 API（ARCHITECTURE.md 2.4 / 2.5.4）。

提供：

* ``POST /scraper/scan``       触发全库文件扫描；
* ``POST /scraper/scrape/{id}``单片刮削（NFO 优先 → 网络级联 → 持久化）；
* ``POST /scraper/scrape-all`` 批量自动刮削任务；
* ``GET  /scraper/status``     扫描 / 刮削任务状态。
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Database, get_db
from ..models import ScanResult
from ..scraper import pipeline, scanner

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
    return {
        **scanner.get_status(),
        "pipeline": pipeline.get_status(),
    }

@router.post("/scraper/scrape/{video_id}")
async def scrape_one(
    video_id: str,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    """对单个影片执行刮削。"""
    video = await db.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="视频不存在")

    result = await pipeline.scrape_video(video_id)
    if not result.get("success"):
        # 刮削未命中并非服务错误，返回 200 + success=false 供前端提示
        return result
    return result

@router.post("/scraper/scrape-all")
async def scrape_all(
    sync: bool = Query(False, description="是否同步等待全部完成"),
    statuses: str = Query("pending,failed", description="逗号分隔的待刮状态"),
    limit: int | None = Query(None, ge=1, description="最多处理数量"),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    """对所有 pending / failed 影片批量刮削。

    默认以**后台任务**方式执行并立即返回状态；``sync=true`` 时同步等待完成
    （适合小批量 / 自动化脚本）。
    """
    status_list = tuple(s.strip() for s in statuses.split(",") if s.strip())

    if pipeline.get_status().get("running"):
        return {"started": False, "reason": "已有刮削任务在运行", **pipeline.get_status()}

    if sync:
        summary = await pipeline.scrape_all(statuses=status_list, limit=limit)
        return {"started": True, "sync": True, **summary}

    asyncio.create_task(pipeline.scrape_all(statuses=status_list, limit=limit))
    # 让事件循环调度一次，确保状态已置为 running
    await asyncio.sleep(0)
    return {"started": True, "sync": False, **pipeline.get_status()}
