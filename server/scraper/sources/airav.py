"""夭夭影社 · Airav 数据源（ARCHITECTURE.md 2.4.4）。

Airav 为日系 AV 资料库，页面常带 ``application/ld+json`` 结构化数据，
本适配器优先消费 JSON-LD，其次回退到 HTML 正则解析，兼容有码 / 无码 / FC2。
"""

from __future__ import annotations

import json
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


class AiravScraper(ScraperSource):
    """Airav 刮削器。"""

    name = "airav"
    display_name = "Airav"
    base_url = "https://airav.wiki"
    mirrors = ("https://airav.wiki", "https://airav.io")
    priority = 30

    # ------------------------------------------------------------------ URL
    def search_url(self, query: str) -> str:
        return f"{self.base_url.rstrip('/')}/search?q={quote(query)}"

    def detail_url(self, identifier: str) -> str:
        if identifier.startswith(("http://", "https://")):
            return identifier
        return f"{self.base_url.rstrip('/')}/search?q={quote(identifier.strip())}"

    # ---------------------------------------------------------------- 接口
    async def search(self, query: str) -> list[dict[str, Any]]:
        html = await self.request_text(self.search_url(query))
        return self.parse_search(html)

    async def get_detail(self, identifier: str) -> Optional[dict[str, Any]]:
        if identifier.startswith(("http://", "https://")):
            html = await self.request_text(identifier)
            detail = self.parse_detail(html, url=identifier)
            return detail if detail.get("title") else None

        html = await self.request_text(self.search_url(identifier))
        results = self.parse_search(html)
        if not results:
            return None
        detail_url = results[0].get("detail_url")
        if not detail_url or detail_url == self.search_url(identifier):
            return results[0]
        detail_html = await self.request_text(detail_url)
        detail = self.parse_detail(detail_html, url=detail_url)
        return detail if detail.get("title") else results[0]

    # ---------------------------------------------------------------- 解析
    def parse_search(self, html: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for href, text in extract_links(html, "/work/") + extract_links(html, "/detail/"):
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

        # 1) 优先 JSON-LD
        json_ld = self._extract_json_ld(html)
        if json_ld:
            self._apply_json_ld(result, json_ld)

        # 2) HTML 补齐
        if not result["title"]:
            raw_title = strip_tags(
                first_match(
                    html,
                    r'<h1[^>]+class="[^"]*(?:title|work__title)[^"]*"[^>]*>(.*?)</h1>',
                )
            )
            if not raw_title:
                raw_title = extract_meta(html, "og:title") or extract_title(html)
            raw_title = re.sub(r"\s*[\-|–]\s*Airav.*$", "", raw_title, flags=re.I)
            result["title"] = raw_title.strip()
            result["original_title"] = result["original_title"] or raw_title.strip()

        if not result.get("bangou"):
            bangou = extract_label_value(
                html, ["品番", "番號", "番号", "識別碼", "识别码"]
            )
            if bangou:
                result["bangou"] = bangou

        if not result.get("release_date"):
            release_date = extract_label_value(
                html, ["配信開始日", "発売日", "發行日期", "发行日期", "日期"]
            )
            if release_date:
                result["release_date"] = normalize_date(release_date)

        if not result.get("duration"):
            runtime = extract_label_value(
                html, ["収録時間", "時長", "时长", "長度", "长度"]
            )
            if runtime:
                result["duration"] = parse_duration(runtime)

        if not result.get("director"):
            director = extract_label_value(html, ["監督", "導演", "导演"])
            if director:
                result["director"] = director

        if not result.get("studio"):
            studio = extract_label_value(
                html, ["メーカー", "レーベル", "片商", "製作商", "制作商"]
            )
            if studio:
                result["studio"] = studio

        if not result.get("series"):
            series = extract_label_value(html, ["シリーズ", "系列"])
            if series:
                result["series"] = series

        if not result.get("tags"):
            tags = extract_class_texts(html, ["genre", "tag", "p-work__genre"])
            if not tags:
                tags = [text for _, text in extract_links(html, "/genre/")]
            result["tags"] = dedupe([tag for tag in tags if tag])

        if not result.get("actors"):
            actors = self._parse_actors(html)
            if actors:
                result["actors"] = actors

        if not result.get("rating"):
            rating = first_match(
                html, r'class="[^"]*(?:rating|review)[^"]*"[^>]*>\s*([\d.]+)'
            )
            if rating:
                result["rating"] = parse_float(rating)

        if not result.get("poster_url"):
            poster = extract_meta(html, "og:image")
            if not poster:
                poster = first_match(
                    html,
                    r'<img[^>]+class="[^"]*(?:cover|p-work__image|p-work__cover)[^"]*"'
                    r'[^>]+src="([^"]+)"',
                )
            if poster:
                result["poster_url"] = self.absolute(poster)

        if not result.get("backdrop_url"):
            backdrop = first_match(
                html,
                r'<div[^>]+class="[^"]*(?:sample|gallery)[^"]*".*?<img[^>]+src="([^"]+)"',
            )
            if backdrop:
                result["backdrop_url"] = self.absolute(backdrop)

        return {
            key: value
            for key, value in result.items()
            if value not in ("", None, [])
        }

    # ---------------------------------------------------------------- JSON-LD
    @staticmethod
    def _extract_json_ld(html: str) -> Optional[dict[str, Any]]:
        for match in re.finditer(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            re.IGNORECASE | re.DOTALL,
        ):
            raw = match.group(1).strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates = data if isinstance(data, list) else [data]
            for item in candidates:
                if isinstance(item, dict) and item.get("@type") in {
                    "Movie",
                    "VideoObject",
                    "CreativeWork",
                    "Product",
                }:
                    return item
            if isinstance(data, dict):
                return data
        return None

    def _apply_json_ld(self, result: dict[str, Any], data: dict[str, Any]) -> None:
        name = strip_tags(data.get("name") or data.get("headline") or "")
        if name:
            result["title"] = name
            result["original_title"] = strip_tags(
                data.get("alternateName") or data.get("name") or name
            )
        if data.get("description"):
            result["plot"] = strip_tags(data["description"])
        if data.get("datePublished"):
            result["release_date"] = normalize_date(data["datePublished"])

        director = data.get("director")
        if isinstance(director, list) and director:
            director = director[0]
        if isinstance(director, dict):
            result["director"] = strip_tags(director.get("name") or "")
        elif isinstance(director, str):
            result["director"] = strip_tags(director)

        brand = data.get("brand") or data.get("productionCompany") or data.get("publisher")
        if isinstance(brand, list) and brand:
            brand = brand[0]
        if isinstance(brand, dict):
            result["studio"] = strip_tags(brand.get("name") or "")
        elif isinstance(brand, str):
            result["studio"] = strip_tags(brand)

        if data.get("genre"):
            genres = data["genre"]
            if isinstance(genres, str):
                genres = re.split(r"[,，/]", genres)
            result["tags"] = dedupe([strip_tags(g) for g in genres if strip_tags(g)])

        actors = data.get("actor") or data.get("actors")
        if actors:
            if isinstance(actors, dict):
                actors = [actors]
            parsed: list[dict[str, str]] = []
            for actor in actors:
                if isinstance(actor, str):
                    parsed.append({"name": strip_tags(actor), "name_ja": "", "photo_url": ""})
                elif isinstance(actor, dict):
                    parsed.append(
                        {
                            "name": strip_tags(actor.get("name") or ""),
                            "name_ja": strip_tags(
                                actor.get("alternateName") or ""
                            ),
                            "photo_url": self.absolute(actor.get("image") or ""),
                        }
                    )
            result["actors"] = [a for a in parsed if a["name"]]

        rating = data.get("aggregateRating")
        if isinstance(rating, dict) and rating.get("ratingValue") is not None:
            result["rating"] = parse_float(rating["ratingValue"])

        image = data.get("image")
        if isinstance(image, list) and image:
            image = image[0]
        if isinstance(image, dict):
            image = image.get("url")
        if image:
            result["poster_url"] = self.absolute(str(image))

        if data.get("thumbnailUrl"):
            thumb = data["thumbnailUrl"]
            if isinstance(thumb, list) and thumb:
                thumb = thumb[0]
            result["backdrop_url"] = self.absolute(str(thumb))

    def _parse_actors(self, html: str) -> list[dict[str, str]]:
        actors: list[dict[str, str]] = []
        for keyword in ("/actress/", "/actor/", "/star/"):
            for href, name in extract_links(html, keyword):
                if name:
                    actors.append(
                        {"name": strip_tags(name), "name_ja": strip_tags(name), "photo_url": ""}
                    )
            if actors:
                break
        if not actors:
            for match in re.finditer(
                r'<[^>]+class="[^"]*(?:actress|actor)[^"]*"[^>]*>(.*?)</[^>]+>',
                html,
                re.IGNORECASE | re.DOTALL,
            ):
                name = strip_tags(match.group(1))
                if name:
                    actors.append({"name": name, "name_ja": name, "photo_url": ""})
        return dedupe(actors, key=lambda item: item["name"])


__all__ = ["AiravScraper"]
