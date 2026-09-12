"""夭夭影社 · 观看历史业务逻辑（ARCHITECTURE.md 2.2.7 / 2.5.3）。"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from ..database import Database

# 进度达到该比例视为「已看完」
COMPLETED_THRESHOLD = 0.9


def _compute_progress(position: int, duration: int) -> float:
    if duration and duration > 0:
        return max(0.0, min(1.0, position / duration))
    return 0.0


async def report_progress(
    db: Database,
    *,
    video_id: str,
    position: int = 0,
    duration: int = 0,
    device: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """写入一条观看历史，并同步 videos.play_count / last_played。

    返回新写入的历史记录；影片不存在时返回 ``None``。
    """
    video = await db.get_video(video_id)
    if video is None:
        return None

    # 统一全流程毫秒：前端 position / duration 均为毫秒；
    # videos.duration 为秒，仅在回退时显式换算，禁止直接混用
    position = max(0, int(position or 0))
    duration = max(0, int(duration or 0))
    if duration <= 0:
        video_seconds = int(video.get("duration") or 0)
        duration = max(0, video_seconds * 1000)
    progress = _compute_progress(position, duration)
    completed = 1 if progress >= COMPLETED_THRESHOLD else 0

    latest = await db.fetchone(
        "SELECT completed FROM watch_history WHERE video_id = ? "
        "ORDER BY watched_at DESC, rowid DESC LIMIT 1",
        (video_id,),
    )
    # 首次观看，或上次已看完后重新开始 → 播放次数 +1
    is_new_session = latest is None or int(latest.get("completed") or 0) == 1
    new_play_count = int(video.get("play_count") or 0) + (1 if is_new_session else 0)

    history_id = str(uuid4())
    await db.execute(
        "INSERT INTO watch_history "
        "(id, video_id, position, duration, progress, completed, watched_at, device) "
        "VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)",
        (history_id, video_id, position, duration, progress, completed, device),
    )
    await db.update_video(
        video_id,
        {"play_count": new_play_count, "last_played": _utcnow()},
    )

    return await db.fetchone(
        "SELECT * FROM watch_history WHERE id = ?", (history_id,)
    )


async def get_resume_point(
    db: Database, video_id: str
) -> Optional[dict[str, Any]]:
    """最新一条历史即为续播点（ARCHITECTURE.md 2.2.7 注释）。"""
    return await db.fetchone(
        "SELECT * FROM watch_history WHERE video_id = ? "
        "ORDER BY watched_at DESC, rowid DESC LIMIT 1",
        (video_id,),
    )


async def get_recent(
    db: Database, *, limit: int = 20
) -> list[dict[str, Any]]:
    """最近观看列表（每部影片取最新一条历史，附带影片摘要）。"""
    limit = max(1, min(int(limit or 20), 100))
    # watched_at 精度仅到秒，同秒多写会命中多条；用窗口函数按 video_id
    # 取最新一条（rowid 兜底），彻底消除重复
    rows = await db.fetchall(
        "SELECT r.id, r.video_id, r.position, r.duration, r.progress, "
        "       r.completed, r.watched_at, r.device, "
        "       v.title, v.bangou, v.poster_path, v.thumb_path, "
        "       v.file_size, v.duration AS video_duration, v.is_hidden "
        "FROM ("
        "    SELECT h.*, "
        "           ROW_NUMBER() OVER ("
        "               PARTITION BY h.video_id "
        "               ORDER BY h.watched_at DESC, h.rowid DESC"
        "           ) AS rn "
        "    FROM watch_history h"
        ") r "
        "JOIN videos v ON v.id = r.video_id "
        "WHERE r.rn = 1 AND v.is_hidden = 0 "
        "ORDER BY r.watched_at DESC LIMIT ?",
        (limit,),
    )
    return rows


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
