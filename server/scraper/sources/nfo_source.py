"""夭夭影社 · 本地 NFO 数据源（ARCHITECTURE.md 2.4.5 / 2.4.6）。

职责：

* 解析 Kodi / Jellyfin / Emby 常见 ``movie.nfo`` XML 结构，
  提取标题、年份、导演、演员、标签、封面 / 背景图等；
* 输出与 :mod:`server.scraper.sources.base` 一致的标准化结构；
* 生成符合 ARCHITECTURE.md 2.4.6 规范的 NFO 文件。

本地 NFO 权威性最高：``pipeline`` 在联网刮削之前会优先调用本模块。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional
from xml.sax.saxutils import escape

from ... import config
from ...utils.logger import get_logger
from .base import ScraperSource, normalize_date, parse_duration, strip_tags

logger = get_logger(__name__)

#: NFO 中可能出现的根节点名
_NFO_ROOTS = {"movie", "episode", "tvshow", "musicvideo"}


def _local_name(tag: str) -> str:
    """去除命名空间，仅保留本地标签名。"""
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _text(element: Optional[ET.Element]) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _find(root: ET.Element, *names: str) -> Optional[ET.Element]:
    """按本地标签名（不区分大小写）查找直接子节点。"""
    wanted = {name.lower() for name in names}
    for child in root:
        if _local_name(child.tag) in wanted:
            return child
    return None


def _findall(root: ET.Element, *names: str) -> list[ET.Element]:
    wanted = {name.lower() for name in names}
    return [child for child in root if _local_name(child.tag) in wanted]


def _deep_findall(root: ET.Element, *names: str) -> list[ET.Element]:
    wanted = {name.lower() for name in names}
    return [node for node in root.iter() if _local_name(node.tag) in wanted]


def find_nfo(video_path: str | Path) -> Optional[Path]:
    """在视频同目录中查找同名 ``.nfo``（回退 ``movie.nfo``）。"""
    path = Path(video_path)
    candidate = path.with_suffix(".nfo")
    if candidate.is_file():
        return candidate
    movie_nfo = path.parent / "movie.nfo"
    if movie_nfo.is_file():
        return movie_nfo
    return None


def parse_nfo_file(nfo_path: str | Path) -> dict[str, Any]:
    """解析 NFO 文件，返回标准化结构（失败返回 ``{}``）。"""
    path = Path(nfo_path)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        logger.warning("NFO 读取失败: %s (%s)", path, exc)
        return {}
    data = parse_nfo_string(text)
    if data:
        data["nfo_path"] = str(path)
        _resolve_local_art(data, path.parent)
    return data


def parse_nfo_string(text: str) -> dict[str, Any]:
    """解析 NFO XML 字符串，返回标准化结构。"""
    if not text or not text.strip():
        return {}

    # 兼容带 BOM / 前导空白 / 非法控制字符的 NFO
    text = text.lstrip("\ufeff \t\r\n")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        logger.warning("NFO ParseError: %s", exc)
        # 兜底：剥离非法字符后重试
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        try:
            root = ET.fromstring(cleaned)
        except ET.ParseError:
            return {}

    if _local_name(root.tag) not in _NFO_ROOTS and _local_name(root.tag) != "":
        # 非标准根节点也尝试解析（宽容处理）
        pass

    data: dict[str, Any] = {"source": "nfo"}

    title = _text(_find(root, "title"))
    if title:
        data["title"] = strip_tags(title)

    original_title = _text(_find(root, "originaltitle"))
    if original_title:
        data["original_title"] = strip_tags(original_title)

    sort_title = _text(_find(root, "sorttitle"))
    if sort_title:
        data["sort_title"] = strip_tags(sort_title)

    num = _text(_find(root, "num")) or _text(_find(root, "id"))
    if num and re.search(r"[A-Za-z0-9]", num):
        data["bangou"] = strip_tags(num)

    studio = _text(_find(root, "studio"))
    if studio:
        data["studio"] = strip_tags(studio)

    director = _text(_find(root, "director"))
    if director:
        data["director"] = strip_tags(director)

    plot = _text(_find(root, "plot")) or _text(_find(root, "outline"))
    if plot:
        data["plot"] = strip_tags(plot)

    premiered = _text(_find(root, "premiered")) or _text(_find(root, "releasedate"))
    year = _text(_find(root, "year"))
    if premiered:
        data["release_date"] = normalize_date(premiered)
    elif year:
        data["release_date"] = normalize_date(f"{year}-01-01")

    runtime = _text(_find(root, "runtime"))
    if runtime:
        data["duration"] = parse_duration(runtime)

    rating = _text(_find(root, "rating"))
    if rating:
        data["rating"] = rating

    tags = [strip_tags(_text(node)) for node in _findall(root, "tag", "genre")]
    tags = [tag for tag in tags if tag]
    if tags:
        data["tags"] = tags

    series_node = _find(root, "set")
    if series_node is not None:
        series_name = _text(_find(series_node, "name")) or _text(series_node)
        if series_name:
            data["series"] = strip_tags(series_name)

    # 演员：<actor><name>..</name><thumb>..</thumb></actor>
    actors: list[dict[str, str]] = []
    for actor_node in _deep_findall(root, "actor"):
        name = _text(_find(actor_node, "name"))
        if not name:
            continue
        actors.append(
            {
                "name": strip_tags(name),
                "name_ja": strip_tags(_text(_find(actor_node, "name_ja", "originalname"))),
                "photo_url": _text(_find(actor_node, "thumb", "photo")),
            }
        )
    if actors:
        data["actors"] = actors

    # 图片：<art><poster>..</poster><fanart>..</fanart></art>
    art = _find(root, "art")
    if art is not None:
        poster = _text(_find(art, "poster"))
        fanart = _text(_find(art, "fanart"))
        if poster:
            data["poster_url"] = poster
        if fanart:
            data["backdrop_url"] = fanart

    if not data.get("poster_url"):
        poster = _text(_find(root, "poster", "cover", "thumb"))
        if poster:
            data["poster_url"] = poster
    if not data.get("backdrop_url"):
        backdrop = _text(_find(root, "fanart", "backdrop"))
        if backdrop:
            data["backdrop_url"] = backdrop
        else:
            # fanart 有时是 <fanart><thumb>..</thumb></fanart>
            fanart_node = _find(root, "fanart")
            if fanart_node is not None:
                thumb = _text(_find(fanart_node, "thumb"))
                if thumb:
                    data["backdrop_url"] = thumb

    # 保留一份字段清洗：空字符串不写入
    return {key: value for key, value in data.items() if value not in ("", None, [])}


def _resolve_local_art(data: dict[str, Any], base_dir: Path) -> None:
    """把 NFO 中的相对图片路径解析为绝对本地路径，并标注 ``*_local``。"""
    for field, local_key in (
        ("poster_url", "poster_local"),
        ("backdrop_url", "backdrop_local"),
    ):
        value = data.get(field)
        if not value or str(value).startswith(("http://", "https://", "//", "data:")):
            continue
        candidate = (base_dir / str(value)).expanduser()
        try:
            candidate = candidate.resolve()
        except OSError:
            continue
        if candidate.is_file():
            data[local_key] = str(candidate)
            data[field] = str(candidate)


class NfoSource(ScraperSource):
    """把本地 NFO 文件适配为 :class:`ScraperSource`。

    ``identifier`` 可以是：

    * ``.nfo`` 文件路径；
    * 视频文件路径（自动在同目录查找 NFO）；
    * 目录路径（查找 ``movie.nfo``）。
    """

    name = "nfo"
    display_name = "本地 NFO"
    priority = 0
    base_url = ""

    async def search(self, query: str) -> list[dict[str, Any]]:
        """本地 NFO 不支持关键词检索。"""
        return []

    async def get_detail(self, identifier: str) -> Optional[dict[str, Any]]:
        path = Path(identifier) if identifier else None
        if path is None:
            return None

        if path.is_dir():
            path = path / "movie.nfo"
        elif path.suffix.lower() != ".nfo":
            found = find_nfo(path)
            if found is None:
                return None
            path = found

        if not path.is_file():
            return None

        data = parse_nfo_file(path)
        if not data:
            return None
        data.setdefault("source", self.name)
        return data


# ---------------------------------------------------------------------------
# NFO 生成（ARCHITECTURE.md 2.4.6）
# ---------------------------------------------------------------------------


def _xml_text(value: Any) -> str:
    return escape(str(value or ""))


def build_nfo_xml(
    video: dict[str, Any],
    actors: Optional[list[dict[str, Any]]] = None,
    tags: Optional[list[Any]] = None,
    series: Optional[dict[str, Any]] = None,
) -> str:
    """依据 2.4.6 规范生成 NFO XML 文本。"""
    actors = actors or []
    series = series or {}

    title = video.get("title") or video.get("bangou") or video.get("file_name") or ""
    sort_title = video.get("sort_title") or video.get("bangou") or title

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        "<movie>",
        f"  <title>{_xml_text(title)}</title>",
    ]
    if video.get("original_title"):
        lines.append(
            f"  <originaltitle>{_xml_text(video['original_title'])}</originaltitle>"
        )
    lines.append(f"  <sorttitle>{_xml_text(sort_title)}</sorttitle>")
    if video.get("bangou"):
        lines.append(f"  <num>{_xml_text(video['bangou'])}</num>")
    if video.get("studio"):
        lines.append(f"  <studio>{_xml_text(video['studio'])}</studio>")
    if video.get("director"):
        lines.append(f"  <director>{_xml_text(video['director'])}</director>")

    release_date = normalize_date(video.get("release_date"))
    if release_date and len(release_date) >= 4:
        lines.append(f"  <year>{_xml_text(release_date[:4])}</year>")
        lines.append(f"  <premiered>{_xml_text(release_date)}</premiered>")

    if video.get("plot"):
        lines.append(f"  <plot>{_xml_text(video['plot'])}</plot>")

    duration = video.get("duration")
    if duration:
        try:
            minutes = max(1, int(round(int(duration) / 60)))
            lines.append(f"  <runtime>{minutes}</runtime>")
        except (TypeError, ValueError):
            pass

    if video.get("rating") is not None:
        lines.append(f"  <rating>{_xml_text(video['rating'])}</rating>")

    seen_tags: set[str] = set()
    for tag in tags or []:
        name = tag.get("name") if isinstance(tag, dict) else str(tag)
        if not name or name in seen_tags:
            continue
        seen_tags.add(name)
        lines.append(f"  <tag>{_xml_text(name)}</tag>")
        lines.append(f"  <genre>{_xml_text(name)}</genre>")

    for actor in actors:
        name = actor.get("name") if isinstance(actor, dict) else str(actor)
        if not name:
            continue
        lines.append("  <actor>")
        lines.append(f"    <name>{_xml_text(name)}</name>")
        photo = actor.get("photo_path") if isinstance(actor, dict) else None
        if photo:
            lines.append(f"    <thumb>{_xml_text(photo)}</thumb>")
        lines.append("  </actor>")

    if series.get("name"):
        lines.append("  <set>")
        lines.append(f"    <name>{_xml_text(series['name'])}</name>")
        lines.append("  </set>")

    if video.get("poster_path") or video.get("backdrop_path"):
        lines.append("  <art>")
        if video.get("poster_path"):
            lines.append(f"    <poster>{_xml_text(video['poster_path'])}</poster>")
        if video.get("backdrop_path"):
            lines.append(f"    <fanart>{_xml_text(video['backdrop_path'])}</fanart>")
        lines.append("  </art>")

    lines.append("</movie>")
    lines.append("")
    return "\n".join(lines)


async def write_nfo(
    video_id: str,
    database: Any,
    video: Optional[dict[str, Any]] = None,
    actors: Optional[list[dict[str, Any]]] = None,
    tags: Optional[list[dict[str, Any]]] = None,
    series: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """生成并落盘 NFO，返回 NFO 路径（失败返回 ``None``）。"""
    video = video or await database.get_video(video_id)
    if not video:
        return None

    if actors is None:
        actors = await database.fetchall(
            "SELECT a.* FROM actors a JOIN video_actors va ON va.actor_id = a.id "
            "WHERE va.video_id = ? ORDER BY a.name ASC",
            (video_id,),
        )
    if tags is None:
        tags = await database.fetchall(
            "SELECT t.* FROM tags t JOIN video_tags vt ON vt.tag_id = t.id "
            "WHERE vt.video_id = ? ORDER BY t.name ASC",
            (video_id,),
        )
    if series is None and video.get("series_id"):
        series = await database.fetchone(
            "SELECT * FROM series WHERE id = ?", (video["series_id"],)
        )

    xml_text = build_nfo_xml(video, actors=actors, tags=tags, series=series)

    config.NFO_DIR.mkdir(parents=True, exist_ok=True)
    target = config.NFO_DIR / f"{video_id}.nfo"
    written: list[str] = []
    for candidate in (target, _sibling_nfo_path(video)):
        if candidate is None:
            continue
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(xml_text, encoding="utf-8")
            written.append(str(candidate))
        except OSError as exc:
            logger.warning("NFO 写入失败: %s (%s)", candidate, exc)

    if not written:
        return None

    await database.update_video(video_id, {"nfo_path": written[0]})
    return written[0]


def _sibling_nfo_path(video: dict[str, Any]) -> Optional[Path]:
    """返回与视频文件同名的 NFO 路径（用于 Jellyfin / Emby 直接识别）。"""
    file_path = video.get("file_path")
    if not file_path:
        return None
    path = Path(file_path)
    try:
        if not path.parent.is_dir():
            return None
    except OSError:
        return None
    return path.with_suffix(".nfo")


# 兼容 ARCHITECTURE.md 中的命名
async def write_nfo_file(video_id: str, database: Any, **kwargs: Any) -> Optional[str]:
    """``write_nfo`` 的别名（架构伪代码命名）。"""
    return await write_nfo(video_id, database, **kwargs)


__all__ = [
    "NfoSource",
    "find_nfo",
    "parse_nfo_file",
    "parse_nfo_string",
    "build_nfo_xml",
    "write_nfo",
    "write_nfo_file",
]
