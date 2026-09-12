"""夭夭影社 · 媒体文件扫描器（ARCHITECTURE.md 2.4.2）。

深度遍历 ``MEDIA_ROOT``，发现新视频文件 → ffprobe 探测 → 注册进 videos 表；
已存在（``file_path`` 匹配）跳过；文件消失仅告警保留记录。

注意：``videos`` 表在 2.2.1 中 **没有** missing 标记字段，故遵循铁律不新增列，
消失文件交由 ``Database.mark_missing`` 记录日志，不改变数据库结构。
"""

from __future__ import annotations

import asyncio
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .. import config
from ..database import Database
from ..database import db as default_db
from ..utils.ffprobe import ffprobe_async
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 扫描任务状态（供 GET /api/scraper/status 读取）
_status: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "last_result": None,
}


# 扫描互斥锁：防止并发触发导致状态竞争与重复入库
_scan_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _empty_result(**overrides: Any) -> dict[str, Any]:
    """返回字段齐全的扫描结果，保证 ``ScanResult`` 校验永不失败。"""
    result: dict[str, Any] = {
        "discovered": 0,
        "added": 0,
        "skipped": 0,
        "missing": 0,
        "media_root": str(config.MEDIA_ROOT),
        "started_at": None,
        "finished_at": None,
    }
    result.update(overrides)
    return result


def get_status() -> dict[str, Any]:
    """返回当前扫描任务状态。"""
    return dict(_status)



def find_local_artwork(video_path: Path) -> dict[str, str]:
    """在视频同目录下查找本地现成的海报和封面图。
    
    支持优先级：
    1. poster.jpg / poster.png
    2. cover.jpg / cover.png
    3. folder.jpg / folder.png
    4. <stem>-poster.jpg
    5. <stem>.jpg / <stem>.png
    """
    parent = video_path.parent
    stem = video_path.stem

    candidates = [
        parent / "poster.jpg",
        parent / "poster.png",
        parent / f"{stem}-poster.jpg",
        parent / f"{stem}-poster.png",
        parent / "cover.jpg",
        parent / "cover.png",
        parent / "folder.jpg",
        parent / "folder.png",
        parent / f"{stem}.jpg",
        parent / f"{stem}.png",
    ]

    art: dict[str, str] = {}
    media_root = config.MEDIA_ROOT.resolve()

    def to_rel(p: Path) -> str:
        try:
            return str(p.resolve().relative_to(media_root))
        except ValueError:
            return str(p)

    for cand in candidates:
        if cand.is_file():
            rel_str = to_rel(cand)
            art["poster_path"] = rel_str
            art["thumb_path"] = rel_str
            break

    backdrop_candidates = [
        parent / "backdrop.jpg",
        parent / "fanart.jpg",
        parent / f"{stem}-fanart.jpg",
        parent / f"{stem}-backdrop.jpg",
        parent / "cover.jpg",
    ]
    for cand in backdrop_candidates:
        if cand.is_file():
            art["backdrop_path"] = to_rel(cand)
            break

    return art

def find_nfo(video_path: Path) -> Optional[Path]:
    """在同目录查找与视频同名的 ``.nfo``（回退 ``movie.nfo``）。"""
    candidate = video_path.with_suffix(".nfo")
    if candidate.is_file():
        return candidate
    movie_nfo = video_path.parent / "movie.nfo"
    if movie_nfo.is_file():
        return movie_nfo
    return None


def _text(node: Optional[ET.Element]) -> Optional[str]:
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _normalize_bangou(raw: str) -> str:
    return re.sub(r"[-_\s]", "", raw.upper())


def parse_nfo(nfo_path: Path) -> dict[str, Any]:
    """解析 NFO，仅提取 videos 表已定义的字段。

    （完整 NFO 处理属于 Phase 2 ``scraper/nfo_handler.py``，此处提供最小可用实现。）
    """
    try:
        root = ET.parse(nfo_path).getroot()
    except (ET.ParseError, OSError) as exc:
        logger.warning("NFO 解析失败: %s (%s)", nfo_path, exc)
        return {}

    data: dict[str, Any] = {}

    def set_if(key: str, tag: str) -> None:
        value = _text(root.find(tag))
        if value is not None:
            data[key] = value

    set_if("title", "title")
    set_if("original_title", "originaltitle")
    set_if("sort_title", "sorttitle")
    set_if("studio", "studio")
    set_if("director", "director")
    set_if("plot", "plot")

    bangou = _text(root.find("num"))
    if bangou:
        data["bangou"] = bangou
        data["bangou_norm"] = _normalize_bangou(bangou)

    premiered = _text(root.find("premiered"))
    if premiered:
        data["release_date"] = premiered
    else:
        year = _text(root.find("year"))
        if year:
            data["release_date"] = f"{year}-01-01"

    runtime = _text(root.find("runtime"))
    if runtime:
        try:
            data["duration"] = int(float(runtime)) * 60  # NFO runtime 单位为分钟
        except ValueError:
            pass

    rating = _text(root.find("rating"))
    if rating:
        try:
            data["rating"] = float(rating)
        except ValueError:
            pass

    return data


async def _build_record(video_path: Path) -> dict[str, Any]:
    """为一部新发现的影片构建 videos 记录。"""
    try:
        file_size = video_path.stat().st_size
    except OSError:
        file_size = 0

    probe = await ffprobe_async(video_path)
    suffix = video_path.suffix.lower()
    record: dict[str, Any] = {
        "id": str(uuid4()),
        "title": video_path.stem,
        "file_path": str(video_path),
        "file_name": video_path.name,
        "file_size": file_size,
        "duration": probe.get("duration", 0),
        "resolution": probe.get("resolution"),
        "video_codec": probe.get("video_codec"),
        "audio_codec": probe.get("audio_codec"),
        "container": suffix.lstrip("."),
        "bitrate": probe.get("bitrate"),
        "scrape_status": "pending",
    }

    # 扫描并绑定本地已有的 poster / cover / backdrop
    local_art = find_local_artwork(video_path)
    record.update(local_art)

    nfo_file = find_nfo(video_path)
    if nfo_file is not None:
        nfo_data = parse_nfo(nfo_file)
        record.update(nfo_data)
        record["scrape_status"] = "matched"
        record["nfo_path"] = str(nfo_file)

    return record


async def scan_media_library(
    database: Optional[Database] = None,
) -> dict[str, Any]:
    """扫描媒体库，返回汇总结果。

    通过模块级互斥锁保证同一时刻仅有一个扫描在跑；重复触发时立即返回
    一份**字段齐全**的当前 / 上次结果，避免 ``ScanResult`` 校验 500。
    """
    database = database or default_db

    # asyncio 单线程：locked() 与 async with 之间无 await，判定是原子的
    if _scan_lock.locked() or _status["running"]:
        logger.warning("已有扫描任务在运行，忽略本次触发")
        last = _status.get("last_result") or {}
        return _empty_result(
            started_at=_status.get("started_at"),
            finished_at=_status.get("finished_at"),
            **{
                key: last[key]
                for key in ("discovered", "added", "skipped", "missing", "media_root")
                if key in last
            },
        )

    async with _scan_lock:
        return await _scan_locked(database)


async def _scan_locked(database: Database) -> dict[str, Any]:
    """真正的扫描主体（调用方需已持有 ``_scan_lock``）。"""
    started_at = _now()
    _status.update(running=True, started_at=started_at, finished_at=None)

    discovered: set[str] = set()
    added = 0
    skipped = 0
    result: Optional[dict[str, Any]] = None

    try:
        existing = await database.get_all_video_paths()

        if not config.MEDIA_ROOT.is_dir():
            logger.warning("媒体目录不存在: %s", config.MEDIA_ROOT)
        else:
            for root, _dirs, files in os.walk(config.MEDIA_ROOT):
                for fname in files:
                    if Path(fname).suffix.lower() not in config.VIDEO_EXTS:
                        continue
                    full_path = str(Path(root) / fname)
                    discovered.add(full_path)

                    if full_path in existing:
                        # 重新探测本地海报，并规范化更新相对路径
                        cur_vid = await database.get_video_by_path(full_path)
                        if cur_vid:
                            art = find_local_artwork(Path(full_path))
                            if art.get("poster_path") and (cur_vid.get("poster_path") != art["poster_path"] or str(cur_vid.get("poster_path")).startswith("/")):
                                await database.update_video(cur_vid["id"], art)
                                logger.info("规范化本地海报路径 %s: %s", full_path, art["poster_path"])
                        skipped += 1
                        continue

                    try:
                        record = await _build_record(Path(full_path))
                        await database.insert_video(record)
                        added += 1
                    except Exception as exc:  # noqa: BLE001 - 单个文件失败不阻断整体扫描
                        logger.error("注册影片失败 %s: %s", full_path, exc)

        missing = existing - discovered
        if missing:
            await database.mark_missing(sorted(missing))

        result = _empty_result(
            discovered=len(discovered),
            added=added,
            skipped=skipped,
            missing=len(missing),
            started_at=started_at,
            finished_at=_now(),
        )
        logger.info(
            "扫描完成: 发现 %d, 新增 %d, 跳过 %d, 消失 %d",
            result["discovered"],
            result["added"],
            result["skipped"],
            result["missing"],
        )
        return result
    finally:
        _status.update(
            running=False,
            finished_at=_now(),
            last_result=result if result is not None else _status.get("last_result"),
        )
