"""夭夭影社 · 静态图片 API(ARCHITECTURE.md 2.5.2 /api/images/{path:path})。

图片路径为相对于 ``MEDIA_ROOT`` 的相对路径(与 videos.poster_path 等字段一致)。
云端 ``cloud://`` 路径由服务端反向代理拉取 Alist 直链,首次落盘到本地缓存后直接伺服。
"""

from __future__ import annotations

import hashlib
import mimetypes
import uuid
from email.utils import formatdate
from pathlib import Path

import aiofiles
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import config
from ..services.alist_service import fetch_alist_raw_url
from ..utils.http_client import get_client
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["images"])

CACHE_DIR: Path = config.DATA_DIR / "cache" / "posters"
CLOUD_POSTER_HEADERS = {
    "Cache-Control": "public, max-age=604800, immutable",
    "Access-Control-Allow-Origin": "*",
}


def _is_cloud_path(path: str) -> bool:
    return path.startswith("cloud://")


def _cloud_fs_path(cloud_url: str) -> str:
    """从 ``cloud:///abs/path`` 还原 Alist 文件系统绝对路径。"""
    fs_path = cloud_url[len("cloud://"):]
    if not fs_path.startswith("/"):
        fs_path = "/" + fs_path
    return fs_path


def _cache_key(fs_path: str) -> str:
    return hashlib.sha256(fs_path.encode("utf-8")).hexdigest()


async def _download_cloud_poster(fs_path: str, target: Path) -> None:
    raw_url = await fetch_alist_raw_url(fs_path)
    if not raw_url:
        raise RuntimeError("Alist 未返回直链")

    client = await get_client()
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f"{target.name}.{uuid.uuid4().hex}.part")
    try:
        async with client.stream("GET", raw_url) as upstream:
            upstream.raise_for_status()
            async with aiofiles.open(partial, "wb") as handle:
                async for chunk in upstream.aiter_bytes():
                    await handle.write(chunk)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)


async def _serve_cloud_poster(cloud_url: str) -> FileResponse:
    fs_path = _cloud_fs_path(cloud_url)
    digest = _cache_key(fs_path)
    target = CACHE_DIR / digest
    if not target.is_file():
        try:
            await _download_cloud_poster(fs_path, target)
        except (httpx.HTTPError, RuntimeError) as exc:
            logger.warning("云端海报拉取失败 path=%s: %s", fs_path, exc)
            raise HTTPException(status_code=404, detail="云端海报不可用")

    return FileResponse(
        target,
        media_type=mimetypes.guess_type(fs_path)[0] or "application/octet-stream",
        headers={
            **CLOUD_POSTER_HEADERS,
            "ETag": f'"{digest}"',
            "Last-Modified": formatdate(target.stat().st_mtime, usegmt=True),
        },
    )


def _resolve_media_path(relative_path: str) -> Path:
    """将相对路径安全解析到 MEDIA_ROOT 之内,阻止路径穿越。"""
    media_root = config.MEDIA_ROOT.resolve()
    candidate = (media_root / relative_path).resolve()
    if candidate != media_root and media_root not in candidate.parents:
        raise HTTPException(status_code=403, detail="非法路径")
    return candidate


@router.api_route("/images/{path:path}", methods=["GET", "HEAD"])
async def get_image(path: str):
    """伺服封面 / 头像 / 背景图等静态资源(cloud:// 经服务端代理拉取并缓存)。"""
    if _is_cloud_path(path):
        return await _serve_cloud_poster(path)
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
    """专用极速海报直通接口:直接通过 video_id 获取海报,彻底避免 URL 编码/中文路径解析问题。"""
    from ..database import db
    video = await db.get_video(video_id)
    if not video or not video.get("poster_path"):
        raise HTTPException(status_code=404, detail="海报不存在")
    if _is_cloud_path(video["poster_path"]):
        return await _serve_cloud_poster(video["poster_path"])
    target = _resolve_media_path(video["poster_path"])
    if not target.is_file():
        raise HTTPException(status_code=404, detail="图片文件丢失")
    return FileResponse(target, headers={"Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*"})
