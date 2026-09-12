"""夭夭影社 · 刮削流水线调度（ARCHITECTURE.md 2.4.4 / 2.4.5）。

核心数据流::

    本地 NFO 优先
        -> 提取番号（bangou_parser）
        -> 级联网络源抓取（sources）
        -> 缓存入库 scraper_cache
        -> 关联 actors / tags / series
        -> 下载并智能裁切海报 / 背景图
        -> 更新 video 状态为 matched

对外主要入口：

* :meth:`ScraperPipeline.scrape` —— 纯抓取（带缓存），返回标准化结构；
* :meth:`ScraperPipeline.scrape_video` —— 单片端到端刮削 + 持久化；
* :meth:`ScraperPipeline.scrape_all` —— 批量刮削 pending / failed 影片。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from ..database import Database
from ..database import db as default_db
from ..utils.logger import get_logger
from . import image_processor
from .bangou_parser import normalize_bangou, parse_bangou
from .sources import NfoSource, ScraperSource, build_sources, get_sources, normalize_result
from .sources.nfo_source import find_nfo, parse_nfo_file, write_nfo

logger = get_logger(__name__)

DEFAULT_SOURCE_TIMEOUT = 15.0
DEFAULT_CACHE_TTL_DAYS = 30
DEFAULT_STATUSES: tuple[str, ...] = ("pending", "failed")

# 批量任务状态（供 GET /api/scraper/status 读取）
_status: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "total": 0,
    "processed": 0,
    "matched": 0,
    "failed": 0,
    "last_video_id": None,
    "last_result": None,
}

# 批量刮削互斥锁：防止后台任务与同步调用并发重入
_scrape_lock = asyncio.Lock()


def get_status() -> dict[str, Any]:
    """返回当前刮削任务状态快照。"""
    return dict(_status)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def is_expired(cache: dict[str, Any]) -> bool:
    """判断 scraper_cache 记录是否过期。"""
    expires_at = cache.get("expires_at")
    if not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(str(expires_at).replace(" ", "T"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed < datetime.now(timezone.utc)


# 兼容伪代码命名
is_cache_expired = is_expired


class ScraperPipeline:
    """多源刮削流水线管理器。"""

    def __init__(
        self,
        database: Optional[Database] = None,
        sources: Optional[dict[str, list[ScraperSource]]] = None,
        nfo_source: Optional[NfoSource] = None,
        *,
        proxy: str | None = None,
        client: Any | None = None,
        source_timeout: float = DEFAULT_SOURCE_TIMEOUT,
        cache_ttl_days: int = DEFAULT_CACHE_TTL_DAYS,
    ) -> None:
        self.db = database or default_db
        self.sources: dict[str, list[ScraperSource]] = (
            sources if sources is not None else build_sources(proxy=proxy, client=client)
        )
        self.nfo_source = nfo_source or NfoSource()
        self.source_timeout = source_timeout
        self.cache_ttl_days = cache_ttl_days

    # ------------------------------------------------------------------ 抓取
    async def scrape(
        self, bangou: str, bangou_norm: str, btype: str
    ) -> Optional[dict[str, Any]]:
        """按优先级遍历数据源，命中缓存直接返回（ARCHITECTURE.md 2.4.4）。"""
        bangou_norm = normalize_bangou(bangou_norm or bangou)

        cached = await self.db.get_scraper_cache(bangou_norm)
        if cached and not is_expired(cached):
            try:
                result = json.loads(cached["raw_json"])
                if isinstance(result, dict):
                    result.setdefault("source", cached.get("source") or "")
                    return normalize_result(result, source=result.get("source") or "")
            except (json.JSONDecodeError, TypeError):
                logger.warning("刮削缓存损坏，忽略: %s", bangou_norm)

        source_list = get_sources(btype or "censored", self.sources)
        for source in source_list:
            try:
                result = await asyncio.wait_for(
                    source.fetch(bangou, bangou_norm), timeout=self.source_timeout
                )
            except asyncio.TimeoutError:
                logger.warning("[%s] %s 刮削超时", source.name, bangou)
                continue
            except Exception as exc:  # noqa: BLE001 - 单源失败继续下一个
                logger.warning("[%s] %s 刮削失败: %s", source.name, bangou, exc)
                continue

            if not result:
                continue

            normalized = normalize_result(result, source=source.name)
            await self.db.upsert_scraper_cache(
                bangou_norm=bangou_norm,
                source=source.name,
                raw_json=json.dumps(normalized, ensure_ascii=False),
                ttl_days=self.cache_ttl_days,
            )
            return normalized

        return None

    # -------------------------------------------------------------- 本地 NFO
    async def load_local_nfo(self, video: dict[str, Any]) -> Optional[dict[str, Any]]:
        """读取影片本地 NFO（若有），返回标准化结构。"""
        candidate: Optional[Path] = None
        nfo_path = video.get("nfo_path")
        if nfo_path and Path(nfo_path).is_file():
            candidate = Path(nfo_path)
        elif video.get("file_path"):
            candidate = find_nfo(video["file_path"])
        if candidate is None:
            return None

        data = parse_nfo_file(candidate)
        if not data:
            return None
        data.setdefault("source", self.nfo_source.name)
        return normalize_result(data, source=self.nfo_source.name)

    # ------------------------------------------------------------ 单片端到端
    async def scrape_video(
        self, video_id: str, *, force: bool = False
    ) -> dict[str, Any]:
        """单片端到端刮削：NFO 优先 → 番号 → 网络 → 持久化。"""
        video = await self.db.get_video(video_id)
        if video is None:
            return {"success": False, "video_id": video_id, "error": "视频不存在"}

        # 1) 番号解析（缺失时从文件名提取并回填）
        bangou = video.get("bangou")
        bangou_norm = video.get("bangou_norm")
        btype = "censored"
        if not bangou or not bangou_norm:
            parsed = parse_bangou(video.get("file_name") or video.get("file_path") or "")
            if parsed:
                bangou = parsed["bangou"]
                bangou_norm = parsed["bangou_norm"]
                btype = parsed["type"]
                await self.db.update_video(
                    video_id, {"bangou": bangou, "bangou_norm": bangou_norm}
                )
        elif bangou:
            parsed = parse_bangou(bangou)
            if parsed:
                btype = parsed["type"]

        # 2) 本地 NFO 优先
        result = await self.load_local_nfo(video)
        source = self.nfo_source.name if result else ""

        # 3) 网络级联刮削
        if result is None:
            if not bangou or not bangou_norm:
                await self.db.update_video(video_id, {"scrape_status": "failed"})
                return {
                    "success": False,
                    "video_id": video_id,
                    "error": "无法从文件名识别番号",
                }
            result = await self.scrape(bangou, bangou_norm, btype)

        if result is None:
            await self.db.update_video(video_id, {"scrape_status": "failed"})
            return {
                "success": False,
                "video_id": video_id,
                "bangou": bangou,
                "error": "所有数据源均未命中",
            }

        source = source or result.get("source") or ""
        # NFO 命中但缺番号时，用 NFO num 回填
        if result.get("bangou") and (not bangou or not bangou_norm):
            bangou = result["bangou"]
            bangou_norm = normalize_bangou(bangou)

        # 4) 持久化
        applied = await self.persist_scrape_result(video_id, result)
        return {
            "success": True,
            "video_id": video_id,
            "bangou": bangou,
            "bangou_norm": bangou_norm,
            "source": source,
            "title": applied.get("title"),
            "poster_path": applied.get("poster_path"),
            "backdrop_path": applied.get("backdrop_path"),
            "actor_count": applied.get("actor_count", 0),
            "tag_count": applied.get("tag_count", 0),
            "series": applied.get("series"),
        }

    # ---------------------------------------------------------------- 持久化
    async def persist_scrape_result(
        self, video_id: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        """把标准化刮削结果持久化到数据库并处理图片 / NFO。"""
        video = await self.db.get_video(video_id)
        if video is None:
            raise ValueError(f"视频不存在: {video_id}")

        result = normalize_result(result, source=result.get("source") or "")

        # 1) 图片：优先本地 NFO 图，其次网络 URL
        poster_source = result.get("poster_local") or result.get("poster_url")
        backdrop_source = result.get("backdrop_local") or result.get("backdrop_url")
        images = await image_processor.download_and_process(
            video_id,
            poster_url=poster_source,
            backdrop_url=backdrop_source,
        )

        # 2) ~ 5) 多表写入（演员 / 标签 / 系列 / 影片元数据 / 关联）
        # 用显式事务包裹：任一环节抛错则整体回滚，杜绝脏数据半成品。
        actor_ids: list[str] = []
        tag_ids: list[str] = []
        series_name = result.get("series")
        async with self.db.transaction():
            # 2) 演员
            for actor_data in result.get("actors", []):
                try:
                    actor = await self.db.get_or_create_actor(actor_data)
                    actor_ids.append(actor["id"])
                except (ValueError, KeyError) as exc:
                    logger.warning("演员写入失败: %s (%s)", actor_data, exc)

            # 3) 标签
            for tag_name in result.get("tags", []):
                try:
                    tag = await self.db.get_or_create_tag(tag_name)
                    tag_ids.append(tag["id"])
                except (ValueError, KeyError) as exc:
                    logger.warning("标签写入失败: %s (%s)", tag_name, exc)

            # 4) 系列
            series_id = None
            if series_name:
                try:
                    series = await self.db.get_or_create_series(series_name)
                    series_id = series["id"]
                except (ValueError, KeyError) as exc:
                    logger.warning("系列写入失败: %s (%s)", series_name, exc)

            # 5) 更新 videos 表（只写非空字段，避免覆盖已有信息）
            fields: dict[str, Any] = {
                "scrape_status": "matched",
                "scrape_source": result.get("source") or video.get("scrape_source"),
                "scrape_time": datetime.now(timezone.utc).isoformat(),
            }
            for key in (
                "title",
                "original_title",
                "release_date",
                "studio",
                "director",
                "plot",
            ):
                value = result.get(key)
                if value:
                    fields[key] = value
            if result.get("rating") is not None:
                fields["rating"] = result["rating"]
            if not fields.get("title") and result.get("bangou"):
                fields["title"] = result["bangou"]
            if result.get("bangou"):
                fields["sort_title"] = result["bangou"]
                if not video.get("bangou"):
                    fields["bangou"] = result["bangou"]
                    fields["bangou_norm"] = normalize_bangou(result["bangou"])
            if series_id:
                fields["series_id"] = series_id
            for key in ("poster_path", "backdrop_path", "thumb_path"):
                if images.get(key):
                    fields[key] = images[key]

            await self.db.update_video(video_id, fields)
            await self.db.set_video_actors(video_id, actor_ids)
            await self.db.set_video_tags(video_id, tag_ids)

        # 6) 写回 NFO
        try:
            await write_nfo(video_id, self.db)
        except Exception as exc:  # noqa: BLE001 - NFO 失败不影响刮削成功
            logger.warning("NFO 写回失败 video=%s: %s", video_id, exc)

        return {
            **fields,
            "actor_count": len(actor_ids),
            "tag_count": len(tag_ids),
            "series": series_name,
        }

    # ---------------------------------------------------------------- 批量
    async def scrape_all(
        self,
        *,
        statuses: Iterable[str] = DEFAULT_STATUSES,
        limit: Optional[int] = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """批量刮削指定状态的影片。

        互斥锁保证同一时刻只有一个批量任务，重复触发直接返回当前状态。
        """
        if _scrape_lock.locked() or _status["running"]:
            logger.warning("已有刮削任务在运行，忽略本次触发")
            return get_status()

        async with _scrape_lock:
            return await self._scrape_all_locked(
                statuses=statuses, limit=limit, force=force
            )

    async def _scrape_all_locked(
        self,
        *,
        statuses: Iterable[str],
        limit: Optional[int],
        force: bool,
    ) -> dict[str, Any]:
        """批量刮削主体（调用方需已持有 ``_scrape_lock``）。"""
        statuses = tuple(statuses)
        videos = await self.db.get_videos_by_status(statuses, limit=limit)

        _status.update(
            running=True,
            started_at=_now(),
            finished_at=None,
            total=len(videos),
            processed=0,
            matched=0,
            failed=0,
            last_video_id=None,
        )

        matched = 0
        failed = 0
        try:
            for video in videos:
                result = await self.scrape_video(video["id"], force=force)
                if result.get("success"):
                    matched += 1
                else:
                    failed += 1
                _status.update(
                    processed=matched + failed,
                    matched=matched,
                    failed=failed,
                    last_video_id=video["id"],
                )
            summary = {
                "total": len(videos),
                "processed": matched + failed,
                "matched": matched,
                "failed": failed,
                "started_at": _status["started_at"],
                "finished_at": _now(),
            }
            _status.update(last_result=summary)
            return summary
        finally:
            _status["running"] = False
            _status["finished_at"] = _now()


# ---------------------------------------------------------------------------
# 全局单例与便捷函数
# ---------------------------------------------------------------------------

pipeline = ScraperPipeline()


async def scrape_video(
    video_id: str, database: Optional[Database] = None, *, force: bool = False
) -> dict[str, Any]:
    """便捷入口：对单个影片执行端到端刮削。"""
    engine = pipeline if database is None else ScraperPipeline(database=database)
    return await engine.scrape_video(video_id, force=force)


async def scrape_all(
    database: Optional[Database] = None,
    *,
    statuses: Iterable[str] = DEFAULT_STATUSES,
    limit: Optional[int] = None,
    force: bool = False,
) -> dict[str, Any]:
    """便捷入口：批量刮削。"""
    engine = pipeline if database is None else ScraperPipeline(database=database)
    return await engine.scrape_all(statuses=statuses, limit=limit, force=force)


__all__ = [
    "ScraperPipeline",
    "is_expired",
    "is_cache_expired",
    "get_status",
    "pipeline",
    "scrape_video",
    "scrape_all",
]
