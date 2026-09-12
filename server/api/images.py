"""夭夭影社 · 静态图片 API（ARCHITECTURE.md 2.5.2 /api/images/{path:path}）。

图片路径为相对于 ``MEDIA_ROOT`` 的相对路径（与 videos.poster_path 等字段一致）。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import config
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["images"])


def _resolve_media_path(relative_path: str) -> Path:
    """将相对路径安全解析到 MEDIA_ROOT 之内，阻止路径穿越。"""
    media_root = config.MEDIA_ROOT.resolve()
    candidate = (media_root / relative_path).resolve()
    if candidate != media_root and media_root not in candidate.parents:
        raise HTTPException(status_code=403, detail="非法路径")
    return candidate


@router.api_route("/images/{path:path}", methods=["GET", "HEAD"])
async def get_image(path: str) -> FileResponse:
    """伺服封面 / 头像 / 背景图等静态资源。"""
    target = _resolve_media_path(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    headers = {
        "Cache-Control": "public, max-age=86400",
        "Access-Control-Allow-Origin": "*",
    }
    return FileResponse(target, headers=headers)

@router.api_route("/poster/{video_id}", methods=["GET", "HEAD"])
async def get_video_poster(video_id: str) -> FileResponse:
    """专用极速海报直通接口：直接通过 video_id 获取海报，彻底避免 URL 编码/中文路径解析问题。"""
    from ..database import db
    video = await db.get_video(video_id)
    if not video or not video.get("poster_path"):
        raise HTTPException(status_code=404, detail="海报不存在")
    target = _resolve_media_path(video["poster_path"])
    if not target.is_file():
        raise HTTPException(status_code=404, detail="图片文件丢失")
    return FileResponse(target, headers={"Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*"})
