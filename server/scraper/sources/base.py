"""夭夭影社 · 刮削数据源基类（ARCHITECTURE.md 2.4.4）。

定义所有网络 / 本地刮削源的统一接口与**标准化数据结构**，供
``pipeline.ScraperPipeline`` 级联调用。

标准化结果结构（与 ARCHITECTURE.md 2.4.4 逐字对齐）::

    {
        "title": str,
        "original_title": str,
        "release_date": str,       # YYYY-MM-DD
        "studio": str,
        "director": str,
        "actors": [{"name": str, "name_ja": str, "photo_url": str}],
        "tags": [str],
        "plot": str,
        "rating": float,
        "series": str,
        "poster_url": str,         # 封面 URL（或本地路径）
        "backdrop_url": str,       # 背景图 URL（或本地路径）
        "source": str,             # 来源标识
    }

本模块只依赖标准库与项目内 ``utils``，不引入 bs4 / lxml 等额外依赖，
内置一套轻量 HTTP 文本抓取与正则解析工具，确保在任何部署环境可用。
"""

from __future__ import annotations

import abc
import json
import random
import re
from html import unescape
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from ...utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 标准化数据结构
# ---------------------------------------------------------------------------

RESULT_FIELDS: tuple[str, ...] = (
    "title",
    "original_title",
    "release_date",
    "studio",
    "director",
    "actors",
    "tags",
    "plot",
    "rating",
    "series",
    "poster_url",
    "backdrop_url",
    "source",
)

ACTOR_FIELDS: tuple[str, ...] = ("name", "name_ja", "photo_url")

#: 常见浏览器 UA 池（User-Agent 轮换，降低反爬命中率）
USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 "
    "Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) "
    "Gecko/20100101 Firefox/122.0",
)


class ScraperError(RuntimeError):
    """刮削源通用异常。"""

def mirror_url(url: str, mirror: str) -> str:
    """用镜像站替换原站的 scheme + netloc，保留 path / query / fragment。

    旧实现 ``urljoin(mirror, url.split("//", 1)[-1])`` 会把原站 host 误拼进
    路径（如 ``https://mirror/javbus.com/xxx``），导致反爬兜底全部失败。
    """
    source = urlsplit(url)
    candidate = mirror if "://" in mirror else f"//{mirror.lstrip('/')}"
    target = urlsplit(candidate)
    netloc = target.netloc or target.path
    scheme = target.scheme or source.scheme or "https"
    return urlunsplit((scheme, netloc, source.path, source.query, source.fragment))


class ScraperSource(abc.ABC):
    """刮削数据源抽象基类。

    子类必须实现：

    * :meth:`search` —— 关键词检索，返回候选结果列表；
    * :meth:`get_detail` —— 依据番号 / 详情页标识抓取完整标准化结构。

    基类提供 :meth:`fetch` 作为「先详情、后检索」的统一入口，``pipeline``
    只依赖该方法。
    """

    #: 来源唯一标识（写入 scraper_cache.source / videos.scrape_source）
    name: str = "base"
    #: 展示名
    display_name: str = "Base"
    #: 基础站点（子类覆盖）
    base_url: str = ""
    #: 备用镜像（反爬兜底）
    mirrors: tuple[str, ...] = ()
    #: 该源是否偏好无码内容（pipeline 分类型调度）
    uncensored: bool = False
    #: 该源是否面向 FC2
    fc2: bool = False
    #: 权重，数值越小优先级越高
    priority: int = 100
    #: 单次请求超时（秒）
    timeout: float = 15.0
    #: 是否启用
    enabled: bool = True

    def __init__(
        self,
        *,
        client: Any | None = None,
        proxy: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._client = client
        self.proxy = proxy
        if timeout is not None:
            self.timeout = timeout

    # ------------------------------------------------------------------ 接口
    @abc.abstractmethod
    async def search(self, query: str) -> list[dict[str, Any]]:
        """按关键词检索，返回候选结果列表（每项为标准化结构子集）。"""

    @abc.abstractmethod
    async def get_detail(self, identifier: str) -> Optional[dict[str, Any]]:
        """按番号 / URL / 文件路径获取完整标准化结构。"""

    # ------------------------------------------------------------ 统一入口
    async def fetch(
        self, bangou: str, bangou_norm: str | None = None
    ) -> Optional[dict[str, Any]]:
        """统一抓取入口：优先按番号直取详情，失败再回退到检索。

        ``pipeline`` 级联调用本方法，命中即返回**已归一化**的标准化结构。
        """
        if not self.enabled:
            return None

        candidates: list[str] = []
        if bangou:
            candidates.append(bangou)
        norm = bangou_norm or bangou
        if norm and norm not in candidates:
            candidates.append(norm)

        for identifier in candidates:
            try:
                detail = await self.get_detail(identifier)
            except (ScraperError, ValueError) as exc:  # 单源解析失败不阻断
                logger.debug("[%s] get_detail(%s) 失败: %s", self.name, identifier, exc)
                detail = None
            if detail:
                return normalize_result(detail, source=self.name)

        # 回退：检索后取第一条
        for query in candidates:
            try:
                results = await self.search(query)
            except (ScraperError, ValueError) as exc:
                logger.debug("[%s] search(%s) 失败: %s", self.name, query, exc)
                continue
            if results:
                return normalize_result(results[0], source=self.name)
        return None

    # ---------------------------------------------------------------- HTTP
    async def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        from ...utils.http_client import get_client  # 延迟导入，避免环依赖

        return await get_client()

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if extra:
            headers.update(extra)
        return headers

    async def request_text(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        encoding: str | None = None,
    ) -> str:
        """发起 GET 请求并返回文本；失败时抛出 :class:`ScraperError`。"""
        response = await self._request(
            url, params=params, headers=headers, binary=False
        )
        if encoding:
            response.encoding = encoding
        return response.text

    async def request_bytes(
        self, url: str, *, headers: dict[str, str] | None = None
    ) -> bytes:
        """发起 GET 请求并返回二进制内容。"""
        response = await self._request(url, headers=headers, binary=True)
        return response.content

    async def request_json(
        self, url: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        text = await self.request_text(url, params=params)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ScraperError(f"JSON 解析失败: {url}") from exc

    async def _request(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        binary: bool = False,
    ) -> Any:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - 依赖缺失
            raise ScraperError("httpx 未安装，无法进行网络刮削") from exc

        client = await self._get_client()
        request_kwargs: dict[str, Any] = {
            "params": params,
            "headers": self._headers(headers),
        }
        if self.proxy:
            request_kwargs["proxy"] = self.proxy
        try:
            response = await client.get(url, **request_kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            # 反爬兜底：尝试镜像站点（自动剔除已发生故障的原请求 host）
            parsed_origin = urlsplit(url)
            for mirror in self.mirrors:
                parsed_mirror = urlsplit(mirror if "://" in mirror else f"//{mirror.lstrip('/')}")
                if (parsed_mirror.netloc or parsed_mirror.path) == parsed_origin.netloc:
                    continue
                alt = mirror_url(url, mirror)
                try:
                    response = await client.get(alt, **request_kwargs)
                    response.raise_for_status()
                    return response
                except httpx.HTTPError:
                    continue
            raise ScraperError(f"请求失败 {url}: {exc}") from exc

    # -------------------------------------------------------------- 工具方法
    def absolute(self, url: str | None) -> str:
        """把相对 URL 补全为绝对 URL。"""
        if not url:
            return ""
        url = unescape(url.strip())
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http://") or url.startswith("https://"):
            return url
        base = self.base_url or (self.mirrors[0] if self.mirrors else "")
        return urljoin(base.rstrip("/") + "/", url.lstrip("/")) if base else url

    def search_url(self, query: str) -> str:
        """默认检索 URL（子类可覆盖）。"""
        return f"{self.base_url.rstrip('/')}/search/{quote(query)}"

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<{type(self).__name__} name={self.name!r} priority={self.priority}>"


# ---------------------------------------------------------------------------
# 结果归一化
# ---------------------------------------------------------------------------


def empty_result(source: str = "") -> dict[str, Any]:
    """返回字段齐全的空标准化结构。"""
    return {
        "title": "",
        "original_title": "",
        "release_date": "",
        "studio": "",
        "director": "",
        "actors": [],
        "tags": [],
        "plot": "",
        "rating": None,
        "series": "",
        "poster_url": "",
        "backdrop_url": "",
        "source": source,
    }


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        value = " ".join(str(v) for v in value)
    return collapse_ws(str(value))


def _clean_actors(actors: Any) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    if not actors:
        return cleaned
    if isinstance(actors, (str, dict)):
        actors = [actors]
    for actor in actors:
        if isinstance(actor, str):
            name = collapse_ws(actor)
            if name:
                cleaned.append({"name": name, "name_ja": "", "photo_url": ""})
            continue
        if not isinstance(actor, dict):
            continue
        name = _clean_str(actor.get("name") or actor.get("name_ja"))
        name_ja = _clean_str(actor.get("name_ja"))
        photo = _clean_str(
            actor.get("photo_url")
            or actor.get("thumb")
            or actor.get("photo_path")
            or actor.get("image")
        )
        if name or name_ja:
            cleaned.append(
                {"name": name or name_ja, "name_ja": name_ja, "photo_url": photo}
            )
    return dedupe(cleaned, key=lambda a: (a["name"], a["name_ja"]))


def _clean_tags(tags: Any) -> list[str]:
    if not tags:
        return []
    if isinstance(tags, str):
        parts = re.split(r"[,，/、|]+", tags)
    else:
        parts = list(tags)
    return dedupe([t for t in (_clean_str(t) for t in parts) if t])


def _clean_rating(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        rating = float(value)
    except (TypeError, ValueError):
        match = re.search(r"\d+(?:\.\d+)?", str(value))
        if not match:
            return None
        rating = float(match.group(0))
    if rating > 10:  # 百分制 → 十分制
        rating = rating / 10.0
    return round(max(0.0, min(10.0, rating)), 2)


def normalize_result(data: dict[str, Any], source: str = "") -> dict[str, Any]:
    """把任意来源的原始结果裁剪 / 补齐为标准化结构。"""
    result = empty_result(source=source or _clean_str(data.get("source")))
    if not isinstance(data, dict):
        return result
    for field in RESULT_FIELDS:
        if field in data and data[field] is not None:
            result[field] = data[field]
    result["title"] = _clean_str(result.get("title"))
    result["original_title"] = _clean_str(result.get("original_title"))
    result["release_date"] = normalize_date(result.get("release_date"))
    result["studio"] = _clean_str(result.get("studio"))
    result["director"] = _clean_str(result.get("director"))
    result["plot"] = _clean_str(result.get("plot"))
    result["series"] = _clean_str(result.get("series"))
    result["poster_url"] = _clean_str(result.get("poster_url"))
    result["backdrop_url"] = _clean_str(result.get("backdrop_url"))
    result["source"] = _clean_str(result.get("source")) or source
    result["actors"] = _clean_actors(result.get("actors"))
    result["tags"] = _clean_tags(result.get("tags"))
    result["rating"] = _clean_rating(result.get("rating"))
    # 透传非标准字段（本地 NFO 的本地路径等），不覆盖标准字段
    for key, value in data.items():
        if key not in result and value is not None:
            result[key] = value
    return result


def dedupe(items: Iterable[Any], key: Any = None) -> list[Any]:
    """保序去重。"""
    seen: set[Any] = set()
    output: list[Any] = []
    for item in items:
        marker = key(item) if key else item
        if marker in seen:
            continue
        seen.add(marker)
        output.append(item)
    return output


# ---------------------------------------------------------------------------
# 轻量 HTML / 文本解析工具（无第三方依赖）
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def collapse_ws(text: Any) -> str:
    """折叠所有连续空白（含全角空格）。"""
    if text is None:
        return ""
    return _WS_RE.sub(" ", str(text).replace("\u3000", " ")).strip()


def strip_tags(fragment: str) -> str:
    """去除 HTML 标签并反转义实体。"""
    if not fragment:
        return ""
    return collapse_ws(unescape(_TAG_RE.sub(" ", fragment)))


def first_match(
    text: str, pattern: str, group: int = 1, flags: int = re.IGNORECASE | re.DOTALL
) -> str:
    """返回首个捕获组（无匹配返回空串）。"""
    if not text:
        return ""
    match = re.search(pattern, text, flags)
    if not match:
        return ""
    try:
        return match.group(group) or ""
    except IndexError:  # pragma: no cover - 分组越界
        return ""


def find_all_matches(
    text: str, pattern: str, group: int = 1, flags: int = re.IGNORECASE | re.DOTALL
) -> list[str]:
    """返回所有捕获组。"""
    if not text:
        return []
    output: list[str] = []
    for match in re.finditer(pattern, text, flags):
        try:
            value = match.group(group)
        except IndexError:  # pragma: no cover
            continue
        if value:
            output.append(value)
    return output


def extract_meta(html: str, name: str) -> str:
    """提取 ``<meta property=name content=...>`` 或 ``name=`` 的 content。"""
    pattern = (
        r"<meta[^>]+(?:property|name)\s*=\s*[\"']"
        + re.escape(name)
        + r"[\"'][^>]*content\s*=\s*[\"']([^\"']*)[\"']"
    )
    value = first_match(html, pattern)
    if value:
        return unescape(collapse_ws(value))
    pattern_rev = (
        r"<meta[^>]+content\s*=\s*[\"']([^\"']*)[\"'][^>]*"
        r"(?:property|name)\s*=\s*[\"']" + re.escape(name) + r"[\"']"
    )
    return unescape(collapse_ws(first_match(html, pattern_rev)))


def extract_title(html: str) -> str:
    """提取页面标题：优先 og:title，其次 ``<title>``。"""
    return extract_meta(html, "og:title") or strip_tags(
        first_match(html, r"<title[^>]*>(.*?)</title>")
    )


def extract_label_value(html: str, labels: Sequence[str]) -> str:
    """提取「标签: 值」结构。

    同时兼容两种常见写法::

        <span class="header">識別碼:</span> SSIS-001
        <span class="label">日期:</span> <a href="...">2021-01-19</a>
        发行日期: 2021-01-19
    """
    for label in labels:
        escaped = re.escape(label)
        pattern = (
            r">\s*" + escaped + r"\s*[:：]?\s*</[^>]+>\s*"
            r"(?:<a[^>]*>)?\s*([^<>]+)"
        )
        value = first_match(html, pattern)
        if value:
            return collapse_ws(unescape(value))
        pattern_text = escaped + r"\s*[:：]\s*([^\n<>]+)"
        value = first_match(html, pattern_text, flags=re.IGNORECASE)
        if value:
            return collapse_ws(unescape(value))
    return ""


def extract_class_texts(html: str, class_keywords: Sequence[str]) -> list[str]:
    """提取 class 含关键词的元素内部文本（用于标签 / 类别）。"""
    values: list[str] = []
    for keyword in class_keywords:
        pattern = (
            r"<[a-z0-9]+[^>]*class\s*=\s*[\"'][^\"']*"
            + re.escape(keyword)
            + r"[^\"']*[\"'][^>]*>(.*?)</[a-z0-9]+>"
        )
        for fragment in find_all_matches(html, pattern, group=1):
            text = strip_tags(fragment)
            if text:
                values.append(text)
    return dedupe(values)


def extract_attr(html: str, pattern: str, attr: str) -> str:
    """在匹配到的片段里继续提取指定属性值。"""
    fragment = first_match(html, pattern, group=0)
    if not fragment:
        return ""
    return first_match(fragment, rf"{re.escape(attr)}\s*=\s*[\"']([^\"']+)[\"']")


def extract_links(
    html: str, href_contains: str, text_group: int = 1
) -> list[tuple[str, str]]:
    """提取 ``href`` 包含关键词的链接，返回 ``[(href, text), ...]``。"""
    pattern = (
        r"<a[^>]+href\s*=\s*[\"']([^\"']*"
        + re.escape(href_contains)
        + r"[^\"']*)[\"'][^>]*>(.*?)</a>"
    )
    links: list[tuple[str, str]] = []
    for match in re.finditer(pattern, html, re.IGNORECASE | re.DOTALL):
        href = unescape(match.group(1)).strip()
        text = strip_tags(match.group(2))
        if text:
            links.append((href, text))
    return dedupe(links, key=lambda pair: (pair[0], pair[1]))


_DATE_PATTERNS: tuple[str, ...] = (
    r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})",
    r"(\d{4})(\d{2})(\d{2})",
)


def normalize_date(value: Any) -> str:
    """把常见日期格式统一为 ``YYYY-MM-DD``（无法识别返回原值）。"""
    if value is None or value == "":
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    text = str(value).strip()
    match = re.search(_DATE_PATTERNS[0], text)
    if match:
        year, month, day = (int(match.group(i)) for i in (1, 2, 3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    match = re.search(_DATE_PATTERNS[1], text)
    if match:
        year, month, day = (int(match.group(i)) for i in (1, 2, 3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    return text


def parse_int(value: Any, default: int = 0) -> int:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else default


def parse_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(match.group(0)) if match else default


def parse_duration(value: Any) -> int:
    """把 ``120分鐘`` / ``01:30:00`` / ``90`` 解析为秒。"""
    text = str(value or "")
    match = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", text)
    if match:
        hours, minutes, seconds = (int(match.group(i)) for i in (1, 2, 3))
        return hours * 3600 + minutes * 60 + seconds
    minutes = parse_int(text, default=0)
    return minutes * 60 if minutes else 0


__all__ = [
    "RESULT_FIELDS",
    "ACTOR_FIELDS",
    "USER_AGENTS",
    "ScraperError",
    "ScraperSource",
    "mirror_url",
    "empty_result",
    "normalize_result",
    "normalize_date",
    "collapse_ws",
    "strip_tags",
    "first_match",
    "find_all_matches",
    "extract_meta",
    "extract_title",
    "extract_label_value",
    "extract_class_texts",
    "extract_attr",
    "extract_links",
    "parse_int",
    "parse_float",
    "parse_duration",
    "dedupe",
]
