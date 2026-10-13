"""夭夭影社 · 系统 API（ARCHITECTURE.md 2.5.6）。

``GET /api/studios`` 亦归入系统 / 分类聚合，复用 stats_service。
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from .. import config
from ..database import Database, get_db
from ..models import HealthResponse, SystemStats
from ..services import stats_service
from ..services.stats_service import get_stats
from ..utils.http_client import get_client

router = APIRouter(tags=["system"])

_GHFAST_PREFIX = "https://ghfast.top/"
_update_cache: dict[str, Any] | None = None
_update_cached_at: float = 0.0


@router.get("/system/stats", response_model=SystemStats)
async def system_stats(
    db: Database = Depends(get_db),
) -> SystemStats:
    """系统统计（总数、大小、刮削进度）。"""
    return SystemStats(**await get_stats(db))


@router.get("/system/health", response_model=HealthResponse)
async def system_health(
    db: Database = Depends(get_db),
) -> HealthResponse:
    """健康检查。"""
    database = "connected" if db.is_connected else "disconnected"
    try:
        await db.fetchvalue("SELECT 1")
        database = "ok"
    except Exception:  # noqa: BLE001 - 健康检查需吞掉任何异常
        database = "error"
    return HealthResponse(status="ok", database=database)


@router.get("/studios")
async def list_studios(
    db: Database = Depends(get_db),
) -> list[dict[str, Any]]:
    """制作商列表（从 videos 聚合）。"""
    return await stats_service.list_studios(db)


_GHFAST_PREFIX = "https://ghfast.top/"
_update_cache: dict[str, Any] | None = None
_update_cached_at: float = 0.0


def _normalize_release(data: dict[str, Any]) -> dict[str, Any]:
    tag_name = str(data.get("tag_name") or "")
    apk_asset: dict[str, Any] | None = None
    for asset in data.get("assets") or []:
        name = str(asset.get("name") or "")
        if name.lower().endswith(".apk"):
            download_url = str(asset.get("browser_download_url") or "")
            apk_asset = {
                "name": name,
                "size": int(asset.get("size") or 0),
                "downloadUrl": download_url,
                "acceleratedUrl": f"{_GHFAST_PREFIX}{download_url}",
            }
            break
    return {
        "tagName": tag_name,
        "versionName": tag_name[1:] if tag_name[:1].lower() == "v" else tag_name,
        "title": str(data.get("name") or tag_name),
        "body": str(data.get("body") or ""),
        "publishedAt": str(data.get("published_at") or ""),
        "apkAsset": apk_asset,
    }


@router.get("/system/check-update")
async def check_update() -> dict[str, Any]:
    """代理 GitHub 最新 Release,内存缓存 UPDATE_CACHE_TTL 秒,上游失败时回退陈旧缓存。"""
    global _update_cache, _update_cached_at

    now = time.monotonic()
    if _update_cache is not None and now - _update_cached_at < config.UPDATE_CACHE_TTL:
        return _update_cache

    url = f"https://api.github.com/repos/{config.GITHUB_REPO}/releases/latest"
    try:
        client = await get_client()
        resp = await client.get(
            url,
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10.0,
        )
        resp.raise_for_status()
        snapshot = _normalize_release(resp.json())
    except Exception as exc:  # noqa: BLE001 - 上游任何异常都回退缓存或转为 502
        if _update_cache is not None:
            return _update_cache
        raise HTTPException(status_code=502, detail=f"检查更新失败: {exc}") from exc

    _update_cache = snapshot
    _update_cached_at = now
    return snapshot