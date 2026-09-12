"""夭夭影社 · ffprobe 异步封装（ARCHITECTURE.md 2.4.2）。

以子进程方式调用系统 ``ffprobe``（ffmpeg 套件），提取影片元信息：
时长 / 分辨率 / 视频编码 / 音频编码 / 码率。
ffprobe 缺失或探测失败时返回空字典，绝不抛异常阻断扫描。
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from .logger import get_logger

logger = get_logger(__name__)

_FFPROBE_TIMEOUT = 30.0


async def ffprobe_async(file_path: str | Path) -> dict[str, Any]:
    """异步探测媒体文件。

    返回::

        {
            "duration": int,        # 秒
            "resolution": str,      # "1920x1080"
            "video_codec": str,     # "hevc" / "h264"
            "audio_codec": str,     # "aac" / "opus"
            "bitrate": int,         # bps
        }

    失败时返回 ``{}``。
    """
    path = Path(file_path)
    if not path.is_file():
        logger.warning("ffprobe: 文件不存在 %s", path)
        return {}

    if shutil.which("ffprobe") is None:
        logger.warning("ffprobe 未安装，跳过媒体探测: %s", path)
        return {}

    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=_FFPROBE_TIMEOUT
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.warning("ffprobe 超时: %s", path)
            return {}
    except OSError as exc:  # 无法启动子进程
        logger.warning("ffprobe 启动失败: %s (%s)", path, exc)
        return {}

    if process.returncode != 0:
        logger.warning(
            "ffprobe 返回非零退出码 %s: %s", process.returncode, path
        )
        return {}

    try:
        payload = json.loads(stdout.decode("utf-8", errors="replace") or "{}")
    except json.JSONDecodeError:
        logger.warning("ffprobe 输出无法解析为 JSON: %s", path)
        return {}

    return _parse_probe(payload)


def _parse_probe(payload: dict[str, Any]) -> dict[str, Any]:
    """把 ffprobe JSON 归一化为扫描器需要的字段。"""
    result: dict[str, Any] = {}

    fmt = payload.get("format") or {}
    streams = payload.get("streams") or []

    video_stream = next(
        (s for s in streams if s.get("codec_type") == "video"), None
    )
    audio_stream = next(
        (s for s in streams if s.get("codec_type") == "audio"), None
    )

    # 时长（优先 format.duration，其次 video stream）
    duration_raw = fmt.get("duration")
    if duration_raw is None and video_stream is not None:
        duration_raw = video_stream.get("duration")
    if duration_raw is not None:
        try:
            result["duration"] = int(float(duration_raw))
        except (TypeError, ValueError):
            result["duration"] = 0
    else:
        result["duration"] = 0

    # 分辨率
    if video_stream is not None:
        width = video_stream.get("width")
        height = video_stream.get("height")
        if width and height:
            result["resolution"] = f"{width}x{height}"
        result["video_codec"] = video_stream.get("codec_name")

    # 音频编码
    if audio_stream is not None:
        result["audio_codec"] = audio_stream.get("codec_name")

    # 码率（优先 format.bit_rate，其次 video stream）
    bitrate_raw = fmt.get("bit_rate")
    if bitrate_raw is None and video_stream is not None:
        bitrate_raw = video_stream.get("bit_rate")
    if bitrate_raw is not None:
        try:
            result["bitrate"] = int(float(bitrate_raw))
        except (TypeError, ValueError):
            result["bitrate"] = None
    else:
        result["bitrate"] = None

    return result
