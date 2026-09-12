"""夭夭影社 · JavBus 数据源（ARCHITECTURE.md 2.4.4）。

JavBus 为综合信息最全的有码 / 无码刮削源，优先级最高。
支持请求代理、User-Agent 轮换与镜像兜底（见 :class:`ScraperSource`）。

本模块**不依赖** bs4 / lxml，使用正则解析 JavBus 页面结构，便于无网络环境下
直接用本地 HTML 做单元测试（``parse_search`` / ``parse_detail``）。
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import quote

from .base import (
    ScraperSource,
    collapse_ws,
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


class JavBusScraper(ScraperSource):
    """JavBus 刮削器（有码 / 无码通用，``uncensored=True`` 切换无码区）。"""

    name = "javbus"
    display_name = "JavBus"
    base_url = "https://www.javbus.com"
    mirrors = ("https://www.javbus.com", "https://javbus.com")
    priority = 10

    def __init__(self, uncensored: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.uncensored = uncensored
        if uncensored:
            self.name = "javbus_uncensored"
            self.display_name = "JavBus 无码"
            self.priority = 11

    # ------------------------------------------------------------------ URL
    def search_url(self, query: str) -> str:
        base = self.base_url.rstrip("/")
        path = "uncensored/search" if self.uncensored else "search"
        return f"{base}/{path}/{quote(query)}&type=1"

    def detail_url(self, identifier: str) -> str:
        if identifier.startswith(("http://", "https://")):
            return identifier
        base = self.base_url.rstrip("/")
        prefix = "uncensored/" if self.uncensored else ""
        return f"{base}/{prefix}{quote(identifier.strip())}"

    # ---------------------------------------------------------------- 接口
    async def search(self, query: str) -> list[dict[str, Any]]:
        html = await self.request_text(self.search_url(query))
        return self.parse_search(html)

    async def get_detail(self, identifier: str) -> Optional[dict[str, Any]]:
        html = await self.request_text(self.detail_url(identifier))
        detail = self.parse_detail(html, url=self.detail_url(identifier))
        if not detail.get("title"):
            return None
        return detail

    # ---------------------------------------------------------------- 解析
    def parse_search(self, html: str) -> list[dict[str, Any]]:
        """解析搜索结果页，返回候选列表。"""
        results: list[dict[str, Any]] = []
        pattern = re.compile(
            r'<a[^>]+class="[^"]*movie-box[^"]*"[^>]+href="([^"]+)"(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html):
            href = match.group(1)
            block = match.group(2)
            title = strip_tags(
                first_match(block, r'<div[^>]+class="[^"]*photo-info[^"]*"[^>]*>(.*?)</div>')
            ) or strip_tags(first_match(block, r"<img[^>]+alt=\"([^\"]*)\""))
            image = first_match(block, r"<img[^>]+src=\"([^\"]+)\"")
            dates = re.findall(r"<date>([^<]+)</date>", block, re.IGNORECASE)
            if not title:
                continue
            results.append(
                {
                    "title": title,
                    "original_title": title,
                    "poster_url": self.absolute(image),
                    "detail_url": self.absolute(href),
                    "release_date": dates[-1].strip() if dates else "",
                    "source": self.name,
                }
            )
        return dedupe(results, key=lambda item: item["detail_url"])

    def parse_detail(self, html: str, url: str = "") -> dict[str, Any]:
        """解析详情页，返回标准化结构（字段可能缺失）。"""
        result = empty_result(self.name)

        # 标题：优先 h3（含番号 + 演员），其次 og:title
        raw_title = strip_tags(first_match(html, r"<h3[^>]*>(.*?)</h3>"))
        if not raw_title:
            raw_title = extract_meta(html, "og:title") or extract_title(html)
        # 去掉站点后缀 / 纯站名
        raw_title = re.sub(r"\s*[\-|–]\s*JavBus.*$", "", raw_title, flags=re.I)
        result["title"] = raw_title.strip()
        result["original_title"] = raw_title.strip()

        # 识别码：标签 識別碼 / 识别码 / 品番
        bangou = extract_label_value(html, ["識別碼", "识别码", "品番", "番號", "番号"])
        if bangou:
            result["bangou"] = bangou

        # 发行日期 / 长度 / 导演 / 制作商 / 系列
        release_date = extract_label_value(
            html, ["發行日期", "发行日期", "配信開始日", "発売日", "日期"]
        )
        if release_date:
            result["release_date"] = normalize_date(release_date)

        runtime = extract_label_value(html, ["長度", "长度", "収録時間", "时长"])
        if runtime:
            result["duration"] = parse_duration(runtime)

        director = extract_label_value(html, ["導演", "导演", "監督", "監督者"])
        if director:
            result["director"] = director

        studio = extract_label_value(
            html, ["製作商", "制作商", "メーカー", "片商", "出品"]
        )
        if studio:
            result["studio"] = studio

        series = extract_label_value(html, ["系列", "シリーズ", "レーベル"])
        if series:
            result["series"] = series

        # 类别 / 标签
        tags = extract_class_texts(html, ["genre", "tag"])
        if not tags:
            genre_block = first_match(
                html,
                r"<(?:p|div)[^>]*>\s*(?:<span[^>]*>[^<]*(?:類別|类别|ジャンル)[^<]*</span>)(.*?)</(?:p|div)>",
            )
            if genre_block:
                tags = [
                    strip_tags(fragment)
                    for fragment in re.findall(r"<a[^>]*>(.*?)</a>", genre_block, re.S)
                ]
        tags = [tag for tag in tags if tag]
        result["tags"] = dedupe(tags)

        # 演员
        actors = self._parse_actors(html)
        if actors:
            result["actors"] = actors

        # 评分（JavBus 详情页通常无评分，搜索结果可能带评价数，忽略）
        rating = first_match(html, r'class="[^"]*score[^"]*"[^>]*>\s*([\d.]+)')
        if rating:
            result["rating"] = parse_float(rating)

        # 封面：og:image / bigImage / screencap 大图
        poster = extract_meta(html, "og:image")
        if not poster:
            poster = first_match(
                html,
                r'<a[^>]+class="[^"]*bigImage[^"]*"[^>]+href="([^"]+)"',
            )
        if not poster:
            poster = first_match(
                html,
                r'<a[^>]+class="[^"]*bigImage[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"',
            )
        if not poster:
            poster = first_match(
                html, r'<div[^>]+class="[^"]*screencap[^"]*".*?<img[^>]+src="([^"]+)"'
            )
        if poster:
            result["poster_url"] = self.absolute(poster)

        # 背景图：样张第一张
        backdrop = first_match(
            html,
            r'<div[^>]+(?:id|class)="[^"]*(?:sample-waterfall|sample-box)[^"]*".*?'
            r'<img[^>]+src="([^"]+)"',
        )
        if not backdrop:
            backdrop = first_match(
                html, r'<a[^>]+class="[^"]*sample-box[^"]*"[^>]+href="([^"]+)"'
            )
        if backdrop:
            result["backdrop_url"] = self.absolute(backdrop)

        return {key: value for key, value in result.items() if value not in ("", None, [])}

    def _parse_actors(self, html: str) -> list[dict[str, str]]:
        actors: list[dict[str, str]] = []
        # 新版：<div class="star-name"><a href="...">名字</a></div>
        for match in re.finditer(
            r'<div[^>]+class="[^"]*star-name[^"]*"[^>]*>(.*?)</div>',
            html,
            re.IGNORECASE | re.DOTALL,
        ):
            block = match.group(1)
            name = strip_tags(first_match(block, r"<a[^>]*>(.*?)</a>")) or strip_tags(block)
            photo = first_match(block, r"<img[^>]+src=\"([^\"]+)\"")
            if name:
                actors.append(
                    {"name": name, "name_ja": name, "photo_url": self.absolute(photo)}
                )
        if actors:
            return dedupe(actors, key=lambda item: item["name"])

        # 旧版 / 无码：演员链接 /star/ 或 /actress/
        for href, name in extract_links(html, "/star/"):
            actors.append(
                {"name": collapse_ws(name), "name_ja": collapse_ws(name), "photo_url": ""}
            )
        if actors:
            return dedupe(actors, key=lambda item: item["name"])

        for href, name in extract_links(html, "actress"):
            actors.append(
                {"name": collapse_ws(name), "name_ja": collapse_ws(name), "photo_url": ""}
            )
        return dedupe(actors, key=lambda item: item["name"])


__all__ = ["JavBusScraper"]
