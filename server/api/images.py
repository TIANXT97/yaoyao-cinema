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


@router.get("/images/{path:path}")
async def get_image(path: str) -> FileResponse:
    """伺服封面 / 头像 / 背景图等静态资源。"""
    target = _resolve_media_path(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(target)
