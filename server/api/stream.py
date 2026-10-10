"""夭夭影社 · HTTP 206 Partial Content 分块流。

严格对齐 docs/ARCHITECTURE.md 第 2.3 节：

* 绝对零转码，仅做文件字节 Range 切片
* 默认分块 2 MB（``config.CHUNK_SIZE``）
* 支持 ``bytes=0-`` / ``bytes=1000-1999`` / ``bytes=-500``
* 206 响应携带 ``Content-Range`` 与 CORS 暴露头，兼容 Safari PWA / ExoPlayer
* 支持 HEAD 预探测（curl -I / 监测工具），返回与 GET 相同的元信息头
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse

from .. import config
from ..database import Database, get_db
from ..utils.http_client import get_client
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["stream"])


def parse_range(range_header: str, file_size: int) -> tuple[int, int]:
    """解析 ``Range: bytes=start-end``，返回闭区间 ``(start, end)``。

    支持三种形式（ARCHITECTURE.md 2.3.2）：

    * ``bytes=0-``        → 从 0 到文件末
    * ``bytes=1000-1999`` → 精确范围
    * ``bytes=-500``      → 最后 500 字节

    越界或非法时抛出 ``HTTPException(416)``。
    """
    spec = range_header.strip()
    if spec.lower().startswith("bytes="):
        spec = spec[6:]
    spec = spec.strip()

    if not spec:
        raise HTTPException(status_code=416, detail="Range Not Satisfiable")

    try:
        if spec.startswith("-"):
            # 倒数 N 字节
            suffix_length = int(spec[1:])
            if suffix_length <= 0:
                raise ValueError
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
        elif spec.endswith("-"):
            # 从 start 到末尾
            start = int(spec[:-1])
            end = file_size - 1
        else:
            parts = spec.split("-")
            if len(parts) != 2:
                raise ValueError
            start = int(parts[0])
            end = int(parts[1])
    except (TypeError, ValueError):
        raise HTTPException(status_code=416, detail="Range Not Satisfiable")

    # 边界保护
    start = max(0, start)
    end = min(end, file_size - 1)

    if start > end or file_size <= 0:
        raise HTTPException(status_code=416, detail="Range Not Satisfiable")

    return start, end


async def file_iterator(
    path: Path, start: int, end: int
) -> AsyncIterator[bytes]:
    """异步文件分块读取生成器（ARCHITECTURE.md 2.3.2）。"""
    async with aiofiles.open(path, "rb") as handle:
        await handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk_size = min(config.CHUNK_SIZE, remaining)
            chunk = await handle.read(chunk_size)
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.head("/stream/{video_id}", include_in_schema=False)
async def stream_head(
    video_id: str,
    db: Database = Depends(get_db),
) -> Response:
    """HEAD 预探测：返回与 GET 相同的元信息头，方便 curl -I / 监测工具。"""
    video = await db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    # 云端视频：HEAD 直接给 302 占位,前端/探测工具仅关心可访问性
    if video.get("storage_type") == "cloud" or video.get("cloud_fs_path"):
        return Response(
            status_code=302,
            headers={
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": "*",
            },
        )

    file_path = Path(video["file_path"])
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    file_size = file_path.stat().st_size
    content_type = config.MIME_MAP.get(
        file_path.suffix.lower(), "application/octet-stream"
    )
    return Response(
        status_code=200,
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Content-Range, Content-Length",
        },
    )


@router.get("/stream/{video_id}")
async def stream_video(
    video_id: str,
    request: Request,
    db: Database = Depends(get_db),
):
    """视频流伺服：云端 302 直链，本地 HTTP 206 分块。"""
    video = await db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    # —— 云端媒体：向 Alist 换取真实原画直链后 302 重定向 ——
    if video.get("storage_type") == "cloud" or video.get("cloud_fs_path"):
        cloud_fs_path = video.get("cloud_fs_path")
        raw_url: str | None = None
        if cloud_fs_path:
            headers = {}
            if config.ALIST_TOKEN:
                headers["Authorization"] = config.ALIST_TOKEN
            try:
                client = await get_client()
                response = await client.post(
                    f"{config.ALIST_BASE_URL}/api/fs/get",
                    json={"path": cloud_fs_path, "password": ""},
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
                raw_url = (payload.get("data") or {}).get("raw_url")
            except Exception as exc:  # noqa: BLE001 - 统一降级为 502
                logger.error("Alist 直链获取失败 %s: %s", cloud_fs_path, exc)
        if not raw_url:
            raise HTTPException(status_code=502, detail="云端直链获取失败")
        return RedirectResponse(
            url=raw_url,
            status_code=302,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    file_path = Path(video["file_path"])
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    file_size = file_path.stat().st_size
    content_type = config.MIME_MAP.get(
        file_path.suffix.lower(), "application/octet-stream"
    )

    range_header = request.headers.get("range")

    if not range_header:
        # 无 Range → 完整文件（首次探测 / 下载），仍以分块流发送
        return StreamingResponse(
            file_iterator(file_path, 0, file_size - 1),
            status_code=200,
            media_type=content_type,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Range",
                "Access-Control-Expose-Headers": "Content-Range, Content-Length",
            },
        )

    try:
        start, end = parse_range(range_header, file_size)
    except HTTPException as exc:
        exc.headers = {"Content-Range": f"bytes */{file_size}"}
        raise

    content_length = end - start + 1

    return StreamingResponse(
        file_iterator(file_path, start, end),
        status_code=206,
        media_type=content_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
            # CORS 头（跨域播放需要）
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Range",
            "Access-Control-Expose-Headers": "Content-Range, Content-Length",
        },
    )

