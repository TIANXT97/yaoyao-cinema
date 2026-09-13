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

def _to_completed(value: Any) -> int:
    """把任意 bool / 数值 / 字符串安全归一为 SQLite 整型 ``1`` / ``0``。

    避免 ``True`` / ``"1"`` / ``1.0`` 等类型混淆写入 watch_history.completed。
    """
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value else 0
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"1", "true", "yes", "y"} else 0
    return 1 if value else 0


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
    completed = _to_completed(progress >= COMPLETED_THRESHOLD)

    latest = await db.fetchone(
        "SELECT completed FROM watch_history WHERE video_id = ? "
        "ORDER BY watched_at DESC, rowid DESC LIMIT 1",
        (video_id,),
    )
    # 首次观看，或上次已看完后重新开始 → 播放次数 +1
    is_new_session = latest is None or _to_completed(latest.get("completed")) == 1
    new_play_count = int(video.get("play_count") or 0) + (1 if is_new_session else 0)

    # 智能防膨胀：若该视频在最近 2 小时内已有记录且未看完，直接原地更新进度，绝不疯狂插入废记录！
    recent_entry = await db.fetchone(
        "SELECT id, completed FROM watch_history WHERE video_id = ? AND watched_at >= datetime('now', '-2 hours') "
        "ORDER BY watched_at DESC, rowid DESC LIMIT 1",
        (video_id,),
    )

    if recent_entry and _to_completed(recent_entry.get("completed")) == 0:
        history_id = recent_entry["id"]
        await db.execute(
            "UPDATE watch_history SET position = ?, duration = ?, progress = ?, completed = ?, watched_at = datetime('now'), device = ? "
            "WHERE id = ?",
            (position, duration, progress, completed, device, history_id),
        )
    else:
        history_id = str(uuid4())
        await db.execute(
            "INSERT INTO watch_history "
            "(id, video_id, position, duration, progress, completed, watched_at, device) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)",
            (history_id, video_id, position, duration, progress, completed, device),
        )

    # 历史记录每部影片最多只保留最新 5 条，彻底杜绝单表无限膨胀
    await db.execute(
        "DELETE FROM watch_history WHERE video_id = ? AND id NOT IN ("
        "  SELECT id FROM watch_history WHERE video_id = ? ORDER BY watched_at DESC, rowid DESC LIMIT 5"
        ")",
        (video_id, video_id),
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
    # 聚合铁律：电视剧按 series_id 聚合（只保留最后一次观看的那一集与进度）；
    # 电影/独立视频按 video_id 聚合。彻底杜绝同一部剧多集并排刷屏！
    rows = await db.fetchall(
        "WITH ranked_history AS ("
        "    SELECT h.*, v.series_id, v.title, v.bangou, v.poster_path, v.thumb_path, "
        "           v.file_size, v.duration AS video_duration, v.is_hidden, "
        "           ROW_NUMBER() OVER ("
        "               PARTITION BY COALESCE(v.series_id, 'video:' || h.video_id) "
        "               ORDER BY h.watched_at DESC, h.rowid DESC"
        "           ) AS rn "
        "    FROM watch_history h "
        "    JOIN videos v ON v.id = h.video_id "
        "    WHERE v.is_hidden = 0"
        ") "
        "SELECT r.id, r.video_id, r.position, r.duration, r.progress, "
        "       r.completed, r.watched_at, r.device, "
        "       r.title, r.bangou, r.poster_path, r.thumb_path, "
        "       r.file_size, r.video_duration, r.is_hidden "
        "FROM ranked_history r "
        "WHERE r.rn = 1 "
        "ORDER BY r.watched_at DESC LIMIT ?",
        (limit,),
    )
    return rows


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
