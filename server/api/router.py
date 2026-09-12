"""夭夭影社 · 总路由注册（ARCHITECTURE.md 第 5 章 api/router.py）。"""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    actors,
    history,
    images,
    scraper_api,
    series,
    stream,
    system,
    tags,
    videos,
)

api_router = APIRouter()

api_router.include_router(videos.router)
api_router.include_router(stream.router)
api_router.include_router(images.router)
api_router.include_router(history.router)
api_router.include_router(actors.router)
api_router.include_router(tags.router)
api_router.include_router(series.router)
api_router.include_router(scraper_api.router)
api_router.include_router(system.router)

__all__ = ["api_router"]
