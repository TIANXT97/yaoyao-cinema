"""夭夭影社 · JavDB 数据源（ARCHITECTURE.md 2.4.4）。

JavDB 提供评分与较完整的演职员 / 标签信息，作为 JavBus 之后的第二优先级。
同样支持 FC2 区（``fc2=True``）与代理 / UA 轮换 / 镜像兜底。
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import quote

from .base import (
    ScraperSource,
    dedupe,
    empty_result,
    extract_class_texts,
    extract_label_value,
    extract_links,
    extract_meta,
    extract_title,
    first_match,
    normalize_date,
    parse_duration,
    parse_float,
    strip_tags,
)


class JavDBScraper(ScraperSource):
    """JavDB 刮削器。"""

    name = "javdb"
    display_name = "JavDB"
    base_url = "https://javdb.com"
    mirrors = (
        "https://javdb.com",
        "https://javdb009.com",
        "https://javdb007.com",
    )
    priority = 20

    def __init__(self, fc2: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.fc2 = fc2
        if fc2:
            self.name = "javdb_fc2"
            self.display_name = "JavDB FC2"
            self.priority = 21

    # ------------------------------------------------------------------ URL
    def search_url(self, query: str) -> str:
        base = self.base_url.rstrip("/")
        if self.fc2:
            return f"{base}/search?q={quote(query)}&f=all"
        return f"{base}/search?q={quote(query)}&f=all"

    def detail_url(self, identifier: str) -> str:
        if identifier.startswith(("http://", "https://")):
            return identifier
        return f"{self.base_url.rstrip('/')}/search?q={quote(identifier.strip())}&f=all"

    # ---------------------------------------------------------------- 接口
    async def search(self, query: str) -> list[dict[str, Any]]:
        html = await self.request_text(self.search_url(query))
        return self.parse_search(html)

    async def get_detail(self, identifier: str) -> Optional[dict[str, Any]]:
        # JavDB 详情需先经搜索拿到 /v/xxxx 链接
        if identifier.startswith(("http://", "https://")):
            html = await self.request_text(identifier)
            detail = self.parse_detail(html, url=identifier)
            return detail if detail.get("title") else None

        html = await self.request_text(self.search_url(identifier))
        results = self.parse_search(html)
        if not results:
            return None
        detail_url = results[0].get("detail_url")
        if not detail_url:
            return results[0]
        detail_html = await self.request_text(detail_url)
        detail = self.parse_detail(detail_html, url=detail_url)
        return detail if detail.get("title") else results[0]

    # ---------------------------------------------------------------- 解析
    def parse_search(self, html: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        # 兼容两种常见搜索结果卡片结构
        for match in re.finditer(
            r'<a[^>]+href="(/v/[^"]+)"[^>]*>(.*?)</a>',
            html,
            re.IGNORECASE | re.DOTALL,
        ):
            href, block = match.group(1), match.group(2)
            title = strip_tags(first_match(block, r'<div[^>]+class="[^"]*video-title[^"]*"[^>]*>(.*?)</div>'))
            if not title:
                title = strip_tags(first_match(block, r'<strong[^>]*>(.*?)</strong>'))
            image = first_match(block, r"<img[^>]+(?:data-src|src)=\"([^\"]+)\"")
            if not title:
                continue
            results.append(
                {
                    "title": title,
                    "original_title": title,
                    "poster_url": self.absolute(image),
                    "detail_url": self.absolute(href),
                    "source": self.name,
                }
            )
        if results:
            return dedupe(results, key=lambda item: item["detail_url"])

        # 兜底：所有 /v/ 链接
        for href, text in extract_links(html, "/v/"):
            if not text:
                continue
            results.append(
                {
                    "title": text,
                    "original_title": text,
                    "detail_url": self.absolute(href),
                    "source": self.name,
                }
            )
        return dedupe(results, key=lambda item: item["detail_url"])

    def parse_detail(self, html: str, url: str = "") -> dict[str, Any]:
        result = empty_result(self.name)

        raw_title = strip_tags(
            first_match(html, r'<h2[^>]+class="[^"]*title[^"]*"[^>]*>(.*?)</h2>')
        )
        if not raw_title:
            raw_title = extract_meta(html, "og:title") or extract_title(html)
        raw_title = re.sub(r"\s*[\-|–]\s*JavDB.*$", "", raw_title, flags=re.I)
        result["title"] = raw_title.strip()
        result["original_title"] = raw_title.strip()

        bangou = extract_label_value(html, ["番號", "番号", "識別碼", "识别码", "品番"])
        if bangou:
            result["bangou"] = bangou

        release_date = extract_label_value(
            html, ["日期", "發行日期", "发行日期", "配信開始日", "発売日"]
        )
        if release_date:
            result["release_date"] = normalize_date(release_date)

        runtime = extract_label_value(html, ["時長", "时长", "収録時間", "長度", "长度"])
        if runtime:
            result["duration"] = parse_duration(runtime)

        director = extract_label_value(html, ["導演", "导演", "監督"])
        if director:
            result["director"] = director

        studio = extract_label_value(
            html, ["片商", "製作商", "制作商", "メーカー", "發行", "发行"]
        )
        if studio:
            result["studio"] = studio

        series = extract_label_value(html, ["系列", "シリーズ"])
        if series:
            result["series"] = series

        tags = extract_class_texts(html, ["genre", "tag"])
        if not tags:
            tags = [text for _, text in extract_links(html, "/tags?")]
        result["tags"] = dedupe([tag for tag in tags if tag])

        actors = self._parse_actors(html)
        if actors:
            result["actors"] = actors

        rating = first_match(
            html, r'<span[^>]+class="[^"]*value[^"]*"[^>]*>\s*([\d.]+)'
        ) or first_match(html, r'class="[^"]*score[^"]*"[^>]*>\s*([\d.]+)')
        if rating:
            result["rating"] = parse_float(rating)

        poster = extract_meta(html, "og:image")
        if not poster:
            poster = first_match(
                html, r'<img[^>]+class="[^"]*video-cover[^"]*"[^>]+src="([^"]+)"'
            )
        if not poster:
            poster = first_match(
                html, r'<div[^>]+class="[^"]*movie-cover[^"]*".*?<img[^>]+src="([^"]+)"'
            )
        if poster:
            result["poster_url"] = self.absolute(poster)

        backdrop = first_match(
            html,
            r'<div[^>]+class="[^"]*preview-images[^"]*".*?<a[^>]+href="([^"]+)"',
        )
        if not backdrop:
            backdrop = first_match(
                html, r'<a[^>]+class="[^"]*tile-item[^"]*"[^>]+href="([^"]+)"'
            )
        if backdrop:
            result["backdrop_url"] = self.absolute(backdrop)

        return {
            key: value
            for key, value in result.items()
            if value not in ("", None, [])
        }

    def _parse_actors(self, html: str) -> list[dict[str, str]]:
        actors: list[dict[str, str]] = []
        for match in re.finditer(
            r'<a[^>]+href="(/actors/[^"]+)"[^>]*>(.*?)</a>',
            html,
            re.IGNORECASE | re.DOTALL,
        ):
            name = strip_tags(match.group(2))
            if name:
                actors.append({"name": name, "name_ja": name, "photo_url": ""})
        return dedupe(actors, key=lambda item: item["name"])


__all__ = ["JavDBScraper"]
