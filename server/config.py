"""夭夭影社 · 服务端配置管理。

对齐 docs/ARCHITECTURE.md：
- 第 2.1 节 技术栈与监听端口 9900
- 第 2.3 节 分块流常量（CHUNK_SIZE / MIME_MAP）
- 第 5 章 完整工程目录树中的路径定义

所有路径以 NAS 项目根 ``/vol1/1000/vibe-projects/yaoyao-cinema`` 为基准，
并允许通过环境变量覆盖，便于 Docker 容器化部署与本地开发。
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    """读取环境变量中的路径，未设置时回退默认值。"""
    raw = os.getenv(name)
    if raw:
        return Path(raw).expanduser()
    return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# —— 项目根（ARCHITECTURE.md 部署宿主存储根） ——
PROJECT_ROOT: Path = _env_path(
    "YAOYAO_ROOT", Path("/vol1/1000/vibe-projects/yaoyao-cinema")
)

# —— 运行时数据目录（ARCHITECTURE.md 第 5 章 data/） ——
DATA_DIR: Path = _env_path("YAOYAO_DATA_DIR", PROJECT_ROOT / "data")
DB_PATH: Path = _env_path("YAOYAO_DB_PATH", DATA_DIR / "yaoyao.db")

# —— 媒体文件存储根（ARCHITECTURE.md 第 5 章 media/） ——
MEDIA_ROOT: Path = _env_path("YAOYAO_MEDIA_ROOT", PROJECT_ROOT / "media")
VIDEOS_DIR: Path = MEDIA_ROOT / "videos"
POSTERS_DIR: Path = MEDIA_ROOT / "posters"
THUMBS_DIR: Path = MEDIA_ROOT / "thumbs"
BACKDROPS_DIR: Path = MEDIA_ROOT / "backdrops"
ACTORS_DIR: Path = MEDIA_ROOT / "actors"
NFO_DIR: Path = MEDIA_ROOT / "nfo"

# —— 前端构建产物（由 FastAPI 静态伺服，ARCHITECTURE.md 第 1 章「单文件部署」） ——
FRONTEND_DIST: Path = _env_path(
    "YAOYAO_FRONTEND_DIST", PROJECT_ROOT / "frontend" / "dist"
)

# —— 服务监听（ARCHITECTURE.md 2.1：端口 9900，绑定 0.0.0.0） ——
HOST: str = os.getenv("YAOYAO_HOST", "0.0.0.0")
PORT: int = _env_int("YAOYAO_PORT", 9900)

# —— 日志级别 ——
LOG_LEVEL: str = os.getenv("YAOYAO_LOG_LEVEL", "INFO").upper()

# —— 分块流常量（ARCHITECTURE.md 2.3.1） ——
CHUNK_SIZE: int = 2 * 1024 * 1024  # 2 MB

# ATS: 视频容器后缀 → MIME 类型（ARCHITECTURE.md 2.3.1 MIME_MAP，逐字对齐）
MIME_MAP: dict[str, str] = {
    ".mp4": "video/mp4",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    ".ts": "video/mp2t",
    ".wmv": "video/x-ms-wmv",
}

# 扫描器支持的视频后缀（ARCHITECTURE.md 2.4.2 VIDEO_EXTS，逐字对齐）
VIDEO_EXTS: set[str] = {
    ".mp4",
    ".mkv",
    ".avi",
    ".webm",
    ".ts",
    ".wmv",
    ".mov",
    ".rmvb",
}

# —— 分页约束（ARCHITECTURE.md 2.5.1） ——
DEFAULT_PER_PAGE: int = 30
MAX_PER_PAGE: int = 100

# —— CORS（ARCHITECTURE.md 2.3.3：Safari PWA / Capacitor 跨域播放） ——
CORS_ALLOW_ORIGINS: list[str] = ["*"]


def ensure_directories() -> None:
    """确保运行时目录存在（DB 目录 + 媒体子目录）。"""
    for directory in (
        DATA_DIR,
        MEDIA_ROOT,
        VIDEOS_DIR,
        POSTERS_DIR,
        THUMBS_DIR,
        BACKDROPS_DIR,
        ACTORS_DIR,
        NFO_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

# —— Alist 云端直链聚合集成 ——
ALIST_ENABLE: bool = os.getenv("ALIST_ENABLE", "true").lower() in ("true", "1", "yes")
ALIST_BASE_URL: str = os.getenv("ALIST_BASE_URL", "http://192.168.31.235:5244").rstrip("/")
ALIST_TOKEN: str = os.getenv("ALIST_TOKEN", "")
