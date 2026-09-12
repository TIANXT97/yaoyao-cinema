"""夭夭影社 · 日志配置（ARCHITECTURE.md 第 5 章 utils/logger.py）。"""

from __future__ import annotations

import logging
import sys

from .. import config

_CONFIGURED = False

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str | None = None) -> None:
    """初始化根日志器（幂等）。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved = (level or config.LOG_LEVEL).upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(resolved)
    root.addHandler(handler)

    # uvicorn 的访问日志沿用同一格式
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = [handler]
        uvicorn_logger.propagate = False

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """获取命名日志器。"""
    setup_logging()
    return logging.getLogger(name)
