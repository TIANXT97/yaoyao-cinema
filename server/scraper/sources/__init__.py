"""夭夭影社 · 刮削数据源适配器（ARCHITECTURE.md 2.4.4）。

按番号类型组织数据源优先级（与架构文档一致）::

    有码 censored : javbus → javdb → airav
    无码 uncensored: javbus_uncensored → javdb → airav
    FC2           : javdb_fc2 → airav

``build_sources()`` 返回 ``{btype: [ScraperSource, ...]}``，供
:class:`server.scraper.pipeline.ScraperPipeline` 级联调用。
"""

from __future__ import annotations

from typing import Any

from .airav import AiravScraper
from .base import (
    ACTOR_FIELDS,
    RESULT_FIELDS,
    ScraperError,
    ScraperSource,
    empty_result,
    normalize_result,
)
from .javbus import JavBusScraper
from .javdb import JavDBScraper
from .nfo_source import NfoSource

__all__ = [
    "ACTOR_FIELDS",
    "RESULT_FIELDS",
    "ScraperError",
    "ScraperSource",
    "JavBusScraper",
    "JavDBScraper",
    "AiravScraper",
    "NfoSource",
    "empty_result",
    "normalize_result",
    "build_sources",
    "get_sources",
]


def build_sources(
    *, proxy: str | None = None, client: Any | None = None
) -> dict[str, list[ScraperSource]]:
    """构建默认数据源注册表（按类型分组、已按优先级排序）。"""
    common: dict[str, Any] = {"proxy": proxy, "client": client}
    return {
        "censored": [
            JavBusScraper(**common),
            JavDBScraper(**common),
            AiravScraper(**common),
        ],
        "uncensored": [
            JavBusScraper(uncensored=True, **common),
            JavDBScraper(**common),
            AiravScraper(**common),
        ],
        "fc2": [
            JavDBScraper(fc2=True, **common),
            AiravScraper(**common),
            JavBusScraper(**common),
        ],
    }


def get_sources(
    btype: str,
    registry: dict[str, list[ScraperSource]] | None = None,
) -> list[ScraperSource]:
    """按类型返回数据源列表（未知类型回退有码）。"""
    registry = registry or build_sources()
    return registry.get(btype) or registry.get("censored", [])
