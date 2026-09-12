"""夭夭影社 · 全局 httpx 异步客户端（ARCHITECTURE.md 第 5 章 utils/http_client.py）。

供后续刮削引擎（Phase 2）复用；在 server.main lifespan 中创建与关闭。
"""

from __future__ import annotations

import httpx

from .logger import get_logger

logger = get_logger(__name__)

_client: httpx.AsyncClient | None = None

_DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=10.0)
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


async def get_client() -> httpx.AsyncClient:
    """获取（惰性创建）全局 httpx 客户端。"""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT,
            headers=_DEFAULT_HEADERS,
            follow_redirects=True,
        )
    return _client


async def close_client() -> None:
    """关闭全局 httpx 客户端。"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
