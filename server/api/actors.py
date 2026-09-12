"""夭夭影社 · 演员 API（ARCHITECTURE.md 2.5.5）。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Database, get_db
from ..models import ActorDetail, ActorOut
from ..services import video_service

router = APIRouter(tags=["actors"])


@router.get("/actors", response_model=list[ActorOut])
async def list_actors(
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Database = Depends(get_db),
) -> list[ActorOut]:
    """演员列表（带影片计数）。"""
    if search:
        like = f"%{search.strip()}%"
        rows = await db.fetchall(
            "SELECT * FROM actors WHERE name LIKE ? OR name_ja LIKE ? "
            "ORDER BY video_count DESC, name ASC LIMIT ? OFFSET ?",
            (like, like, limit, offset),
        )
    else:
        rows = await db.fetchall(
            "SELECT * FROM actors ORDER BY video_count DESC, name ASC "
            "LIMIT ? OFFSET ?",
            (limit, offset),
        )
    return [ActorOut(**row) for row in rows]


@router.get("/actors/{actor_id}", response_model=ActorDetail)
async def get_actor(
    actor_id: str,
    db: Database = Depends(get_db),
) -> ActorDetail:
    """演员详情 + 作品列表。"""
    actor = await db.fetchone("SELECT * FROM actors WHERE id = ?", (actor_id,))
    if actor is None:
        raise HTTPException(status_code=404, detail="演员不存在")

    videos = await db.fetchall(
        "SELECT v.* FROM videos v "
        "JOIN video_actors va ON va.video_id = v.id "
        "WHERE va.actor_id = ? AND v.is_hidden = 0 "
        "ORDER BY v.date_added DESC",
        (actor_id,),
    )
    detail = dict(actor)
    detail["videos"] = videos
    return ActorDetail(**detail)
