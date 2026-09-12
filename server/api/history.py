"""夭夭影社 · 观看历史 API（ARCHITECTURE.md 2.5.3）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Database, get_db
from ..models import MessageResponse, WatchHistoryCreate
from ..services import history_service

router = APIRouter(tags=["history"])


@router.post("/history", response_model=MessageResponse)
async def report_history(
    payload: WatchHistoryCreate,
    db: Database = Depends(get_db),
) -> MessageResponse:
    """上报播放进度。"""
    record = await history_service.report_progress(
        db,
        video_id=payload.video_id,
        position=payload.position,
        duration=payload.duration,
        device=payload.device,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="视频不存在")
    return MessageResponse(success=True, message=record["id"])


@router.get("/history/recent")
async def recent_history(
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_db),
) -> list[dict[str, Any]]:
    """最近观看（续播列表）。"""
    return await history_service.get_recent(db, limit=limit)


@router.get("/history/{video_id}")
async def get_video_history(
    video_id: str,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    """获取某影片的续播点。"""
    record = await history_service.get_resume_point(db, video_id)
    if record is None:
        raise HTTPException(status_code=404, detail="暂无观看记录")
    return record
