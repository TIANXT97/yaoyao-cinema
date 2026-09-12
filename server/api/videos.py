"""夭夭影社 · 影片 API（ARCHITECTURE.md 2.5.1）。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Database, get_db
from ..models import (
    MessageResponse,
    VideoDetail,
    VideoListResponse,
    VideoUpdate,
)
from ..services import video_service

router = APIRouter(tags=["videos"])


@router.get("/videos", response_model=VideoListResponse)
async def list_videos(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    sort: str = Query("date_added"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    search: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    tag_id: Optional[str] = Query(None),
    series_id: Optional[str] = Query(None),
    studio: Optional[str] = Query(None),
    favorite: Optional[bool] = Query(None),
    status: Optional[str] = Query(None),
    db: Database = Depends(get_db),
) -> VideoListResponse:
    """影片列表（分页、排序、筛选）。"""
    items, total = await video_service.list_videos(
        db,
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        search=search,
        actor_id=actor_id,
        tag_id=tag_id,
        series_id=series_id,
        studio=studio,
        favorite=favorite,
        status=status,
    )
    total_pages = (total + per_page - 1) // per_page if per_page else 0
    return VideoListResponse(
        items=items,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.get("/videos/{video_id}", response_model=VideoDetail)
async def get_video(
    video_id: str,
    db: Database = Depends(get_db),
) -> VideoDetail:
    """影片详情（含演员、标签、续播点）。"""
    detail = await video_service.get_video_detail(db, video_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="视频不存在")
    return VideoDetail(**detail)


@router.put("/videos/{video_id}", response_model=VideoDetail)
async def update_video(
    video_id: str,
    payload: VideoUpdate,
    db: Database = Depends(get_db),
) -> VideoDetail:
    """更新影片元数据。"""
    fields = payload.model_dump(exclude_unset=True, exclude_none=True)
    if fields.get("scrape_status") is not None:
        fields["scrape_status"] = fields["scrape_status"].value
    updated = await video_service.update_video(db, video_id, fields)
    if not updated:
        raise HTTPException(status_code=404, detail="视频不存在")
    detail = await video_service.get_video_detail(db, video_id)
    assert detail is not None
    return VideoDetail(**detail)


@router.delete("/videos/{video_id}", response_model=MessageResponse)
async def delete_video(
    video_id: str,
    db: Database = Depends(get_db),
) -> MessageResponse:
    """删除影片记录（不删除磁盘文件）。"""
    deleted = await video_service.delete_video(db, video_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="视频不存在")
    return MessageResponse(success=True, message="影片记录已删除（磁盘文件保留）")


@router.post("/videos/{video_id}/favorite", response_model=MessageResponse)
async def toggle_favorite(
    video_id: str,
    db: Database = Depends(get_db),
) -> MessageResponse:
    """切换收藏状态。"""
    value = await video_service.toggle_favorite(db, video_id)
    if value is None:
        raise HTTPException(status_code=404, detail="视频不存在")
    return MessageResponse(
        success=True, message=f"is_favorite={value}"
    )


@router.post("/videos/{video_id}/hide", response_model=MessageResponse)
async def toggle_hide(
    video_id: str,
    db: Database = Depends(get_db),
) -> MessageResponse:
    """切换隐藏状态。"""
    value = await video_service.toggle_hidden(db, video_id)
    if value is None:
        raise HTTPException(status_code=404, detail="视频不存在")
    return MessageResponse(success=True, message=f"is_hidden={value}")
