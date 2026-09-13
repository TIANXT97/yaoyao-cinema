"""夭夭影社 · 静态图片 API（ARCHITECTURE.md 2.5.2 /api/images/{path:path}）。

图片路径为相对于 ``MEDIA_ROOT`` 的相对路径（与 videos.poster_path 等字段一致）。
支持本地海报（FileResponse）与云端海报（通过 Alist 直通 RedirectResponse(302)）。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from .. import config
from ..utils.http_client import get_client
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


async def _get_cloud_poster_redirect(cloud_path: str) -> RedirectResponse:
    """处理以 cloud:// 开头的云端海报，向 Alist 请求直链并返回 302 重定向。"""
    virtual_path = cloud_path[len("cloud://"):]
    headers = {}
    if config.ALIST_TOKEN:
        headers["Authorization"] = config.ALIST_TOKEN
    try:
        client = await get_client()
        response = await client.post(
            f"{config.ALIST_BASE_URL}/api/fs/get",
            json={"path": virtual_path, "password": ""},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        raw_url = (payload.get("data") or {}).get("raw_url")
        if raw_url:
            return RedirectResponse(
                url=raw_url,
                status_code=302,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*",
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("获取云端海报直链失败 %s: %s", virtual_path, exc)
    raise HTTPException(status_code=404, detail="云端海报获取失败")


@router.api_route("/images/{path:path}", methods=["GET", "HEAD"], response_model=None)
async def get_image(path: str) -> FileResponse | RedirectResponse:
    """伺服封面 / 头像 / 背景图等静态资源。"""
    if path.startswith("cloud://"):
        return await _get_cloud_poster_redirect(path)

    target = _resolve_media_path(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    headers = {
        "Cache-Control": "public, max-age=86400",
        "Access-Control-Allow-Origin": "*",
    }
    return FileResponse(target, headers=headers)


@router.api_route("/poster/{video_id}", methods=["GET", "HEAD"], response_model=None)
async def get_video_poster(video_id: str) -> FileResponse | RedirectResponse:
    """专用极速海报直通接口：直接通过 video_id 获取海报，彻底避免 URL 编码/中文路径解析问题。"""
    from ..database import db

    video = await db.get_video(video_id)
    if not video or not video.get("poster_path"):
        raise HTTPException(status_code=404, detail="海报不存在")

    poster_path = str(video["poster_path"])
    if poster_path.startswith("cloud://"):
        return await _get_cloud_poster_redirect(poster_path)

    target = _resolve_media_path(poster_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="图片文件丢失")
    return FileResponse(
        target,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*",
        },
    )
