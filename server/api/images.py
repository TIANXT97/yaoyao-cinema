"""夭夭影社 · 静态图片 API（ARCHITECTURE.md 2.5.2 /api/images/{path:path}）。

图片路径为相对于 ``MEDIA_ROOT`` 的相对路径（与 videos.poster_path 等字段一致）。
云端 ``cloud://`` 路径则向 Alist 换取真实直链后 302 直通。
"""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from .. import config
from ..services.alist_service import fetch_alist_raw_url
from ..utils.http_client import get_client
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["images"])


def _is_cloud_path(path: str) -> bool:
    return path.startswith("cloud://")


def _cloud_fs_path(cloud_url: str) -> str:
    """从 ``cloud:///abs/path`` 还原 Alist 文件系统绝对路径。"""
    fs_path = cloud_url[len("cloud://"):]
    if not fs_path.startswith("/"):
        fs_path = "/" + fs_path
    return fs_path


async def _cloud_redirect(cloud_url: str) -> RedirectResponse:
    """向 Alist 换取云端海报真实直链，直接 302 直通。"""
    fs_path = _cloud_fs_path(cloud_url)
    try:
        raw_url = await fetch_alist_raw_url(fs_path)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="云端海报直链获取超时")
    except Exception:
        raise HTTPException(status_code=502, detail="云端海报直链获取失败")

    if not raw_url:
        raise HTTPException(status_code=502, detail="云端海报直链获取失败")
    return RedirectResponse(
        url=raw_url,
        status_code=302,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*",
        },
    )


def _resolve_media_path(relative_path: str) -> Path:
    """将相对路径安全解析到 MEDIA_ROOT 之内，阻止路径穿越。"""
    media_root = config.MEDIA_ROOT.resolve()
    candidate = (media_root / relative_path).resolve()
    if candidate != media_root and media_root not in candidate.parents:
        raise HTTPException(status_code=403, detail="非法路径")
    return candidate


@router.api_route("/images/{path:path}", methods=["GET", "HEAD"])
async def get_image(path: str):
    """伺服封面 / 头像 / 背景图等静态资源（cloud:// 直通 302）。"""
    if _is_cloud_path(path):
        return await _cloud_redirect(path)
    target = _resolve_media_path(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    headers = {
        "Cache-Control": "public, max-age=86400",
        "Access-Control-Allow-Origin": "*",
    }
    return FileResponse(target, headers=headers)


@router.api_route("/poster/{video_id}", methods=["GET", "HEAD"])
async def get_video_poster(video_id: str):
    """专用极速海报直通接口：直接通过 video_id 获取海报，彻底避免 URL 编码/中文路径解析问题。"""
    from ..database import db
    video = await db.get_video(video_id)
    if not video or not video.get("poster_path"):
        raise HTTPException(status_code=404, detail="海报不存在")
    if _is_cloud_path(video["poster_path"]):
        return await _cloud_redirect(video["poster_path"])
    target = _resolve_media_path(video["poster_path"])
    if not target.is_file():
        raise HTTPException(status_code=404, detail="图片文件丢失")
    return FileResponse(target, headers={"Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*"})
