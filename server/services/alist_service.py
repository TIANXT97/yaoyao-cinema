"""夭夭影社 · Alist 直链客户端与内存缓存封装。

特性：
- 严格受控的硬超时（默认 4.0s），防止网盘冷启动挂死工作线程；
- 针对云端 fs_path 的超轻量内存 TTL 缓存（默认 30s），过滤播放器首次嗅探、HEAD与频繁重试的重复换链。
"""

from __future__ import annotations

import time
from typing import Optional

import httpx

from .. import config
from ..utils.http_client import get_client
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 内存直链缓存结构：fs_path -> (raw_url, expire_timestamp)
_cache: dict[str, tuple[str, float]] = {}


def _get_cached_url(fs_path: str) -> Optional[str]:
    """读取有效缓存直链。"""
    if fs_path in _cache:
        url, expire_at = _cache[fs_path]
        if time.time() < expire_at:
            return url
        _cache.pop(fs_path, None)
    return None


def _set_cached_url(fs_path: str, raw_url: str, ttl: float = config.ALIST_CACHE_TTL) -> None:
    """写入缓存，控制容量防内存泄露。"""
    if len(_cache) > 1000:
        # 清理过期项
        now = time.time()
        expired_keys = [k for k, (_, exp) in _cache.items() if exp <= now]
        for k in expired_keys:
            _cache.pop(k, None)
        # 若仍过多，弹出最早的一批
        if len(_cache) > 800:
            for k in list(_cache.keys())[:200]:
                _cache.pop(k, None)

    _cache[fs_path] = (raw_url, time.time() + ttl)


def clear_alist_cache() -> None:
    """清理所有内存直链缓存（供单测使用）。"""
    _cache.clear()


async def fetch_alist_raw_url(fs_path: str, *, timeout: float | None = None) -> Optional[str]:
    """向 Alist 换取指定路径的真实原画直链。

    若命中本地缓存，直接返回；否则发起超时受控的 POST /api/fs/get 请求。
    超时或连接失败时抛出对应异常或返回 None。
    """
    cached = _get_cached_url(fs_path)
    if cached:
        logger.debug("命中 Alist 直链缓存: %s", fs_path)
        return cached

    req_timeout = timeout or config.ALIST_TIMEOUT
    headers: dict[str, str] = {}
    if config.ALIST_TOKEN:
        headers["Authorization"] = config.ALIST_TOKEN

    client = await get_client()
    try:
        response = await client.post(
            f"{config.ALIST_BASE_URL}/api/fs/get",
            json={"path": fs_path, "password": ""},
            headers=headers,
            timeout=req_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        raw_url = (payload.get("data") or {}).get("raw_url")
        if raw_url:
            _set_cached_url(fs_path, raw_url)
            return raw_url
    except httpx.TimeoutException as exc:
        logger.warning("Alist 直链请求超时 (%ss) path=%s: %s", req_timeout, fs_path, exc)
        raise
    except Exception as exc:
        logger.error("Alist 直链获取失败 path=%s: %s", fs_path, exc)

    return None
