"""夭夭影社 · 番号解析器（ARCHITECTURE.md 2.4.3）。

从媒体文件名中提取番号，并归一化用于去重与网络刮削。

设计要点（严格对齐 ARCHITECTURE.md 2.4.3）：

* ``PATTERNS`` 为「正则规则集（优先级从高到低）」，元素为 ``(regex, formatter)``。
* ``parse_bangou(filename)`` 返回 ``{"bangou", "bangou_norm", "type"}`` 或 ``None``。
* 归一化规则：大写、去除 ``-`` / ``_`` / 空白。

在架构给定规则的基础上，额外处理真实片名中常见的噪声：

* 分辨率 / 编码 / 版本标记（``1080P`` / ``x264`` / ``FHD`` / ``WEB-DL`` ...）
* 分卷 / 分碟后缀（``-C`` / ``-CD1`` / ``-part2`` ...）
* 发布组前缀（``[ThZu.Cc]`` / ``HD-`` ...）
* 欧美大厂日期式番号（``Brazzers.23.01.15`` ...）
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# 规则集（优先级从高到低）
# ---------------------------------------------------------------------------

PATTERNS: list[tuple[str, Callable[[re.Match[str]], str]]] = [
    # FC2-PPV 系列：FC2-PPV-1234567 / FC2PPV_1234567 / FC2-1234567
    (
        r"FC2[\s\-_]*(?:PPV[\s\-_]*)?(\d{5,7})",
        lambda m: f"FC2-PPV-{m.group(1)}",
    ),
    # 无码系列：6 位日期 + 3~4 位序号（一本道 / 加勒比：010120_001 / 010120-001）
    (
        r"(\d{6})[\-_](\d{3,4})",
        lambda m: f"{m.group(1)}_{m.group(2)}",
    ),
    # HEYZO-NNNN
    (
        r"HEYZO[\s\-_]?(\d{3,4})",
        lambda m: f"HEYZO-{m.group(1)}",
    ),
    # Tokyo-Hot / カリビアン：n1234 / k1234
    (
        r"\b([nk])[\-_]?(\d{4})\b",
        lambda m: f"{m.group(1).upper()}{m.group(2)}",
    ),
    # 欧美大厂日期式：Brazzers.23.01.15 / Vixen-2023-01-15
    (
        r"\b([A-Z]{3,12})[\s\-_.](\d{2,4})[\-_.](\d{2})[\-_.](\d{2})\b",
        lambda m: f"{m.group(1).upper()}-{m.group(2)}-{m.group(3)}-{m.group(4)}",
    ),
    # 标准番号：字母 2~10 + 可选分隔 + 数字 2~5（SSIS-001 / ABP123 / CAWD_001）
    (
        r"([A-Z]{2,10})[\-_ ]?(\d{2,5})",
        lambda m: f"{m.group(1).upper()}-{m.group(2)}",
    ),
]

# 归一化时被剥离的字符
_NORM_STRIP = re.compile(r"[-_\s]")

# 会被误判为「前缀」的噪声标记（大小写不敏感）
_NOISE_PREFIXES: frozenset[str] = frozenset(
    {
        "HD",
        "FHD",
        "UHD",
        "QHD",
        "SD",
        "WEB",
        "WEBDL",
        "WEBRIP",
        "BLURAY",
        "BDRIP",
        "HDRIP",
        "DVDRIP",
        "REMUX",
        "X",
        "H",
        "X264",
        "X265",
        "H264",
        "H265",
        "HEVC",
        "AVC",
        "AAC",
        "AC3",
        "DTS",
        "MP3",
        "MP4",
        "MKV",
        "AVI",
        "WMV",
        "MOV",
        "TS",
        "PART",
        "PT",
        "CD",
        "DVD",
        "DISC",
        "DISK",
        "VOL",
        "EP",
        "EPS",
        "SP",
        "OP",
        "ED",
        "NC",
        "PV",
        "CM",
        "MENU",
        "BONUS",
        "EXTRA",
        "SAMPLE",
        "PREVIEW",
        "TRAILER",
        "MAIN",
        "FEATURE",
        "COLOR",
        "BIT",
        "CH",
        "AUDIO",
        "VIDEO",
        "SUB",
        "SUBS",
        "CHS",
        "CHT",
        "JAP",
        "JPN",
        "ENG",
        "CHI",
        "RAW",
        "FINAL",
        "REPACK",
        "PROPER",
        "LIMITED",
        "UNRATED",
        "RATED",
        "COMPLETE",
        "MOVIE",
        "FILM",
        "XXX",
    }
)

# 无码数字格式：MMDDYY_NNN(N)
_UNCENSORED_NUMERIC = re.compile(r"^\d{6}_\d{3,4}$")
# Tokyo-Hot / カリビアン 格式：N1234 / K1234（限定恰好 4 位数字，避免误判 NHDTA-123）
_UNCENSORED_NK = re.compile(r"^[NK]\d{4}$")


def normalize_bangou(raw: str) -> str:
    """归一化番号：大写并去除 ``-`` / ``_`` / 空白。"""
    return _NORM_STRIP.sub("", str(raw).upper())


def detect_type(bangou: str) -> str:
    """根据标准番号判定类型：``censored`` / ``uncensored`` / ``fc2``。"""
    upper = str(bangou).upper()
    if "FC2" in upper:
        return "fc2"
    if (
        _UNCENSORED_NUMERIC.match(upper)
        or _UNCENSORED_NK.match(upper)
        or upper.startswith("HEYZO")
    ):
        return "uncensored"
    return "censored"


def _clean_stem(filename: str) -> str:
    """去掉扩展名与常见分卷后缀，返回大写主体。

    仅剥离带关键字的分卷标记（``-CD1`` / ``-part2``）与单字母 ``-C``
    字幕标记，避免误伤以数字结尾的正规番号（如 ``SSIS-01``）。
    """
    stem = Path(str(filename)).stem
    stem = re.sub(
        r"[\-_. ]+(?:cd|disc|disk|part|pt|vol)\s*\d{0,3}$",
        "",
        stem,
        flags=re.IGNORECASE,
    )
    stem = re.sub(r"[\-_. ]+c$", "", stem, flags=re.IGNORECASE)
    return stem.upper()


def parse_bangou(filename: str) -> dict | None:
    """从文件名中提取番号。

    参数:
        filename: 文件名或完整路径（扩展名会被忽略）。

    返回::

        {
            "bangou": "SSIS-001",          # 标准显示格式
            "bangou_norm": "SSIS001",       # 归一化（大写、去连字符）
            "type": "censored" | "uncensored" | "fc2",
        }

    无法识别时返回 ``None``。
    """
    if not filename:
        return None

    name = _clean_stem(filename)

    for pattern, formatter in PATTERNS:
        for match in re.finditer(pattern, name, re.IGNORECASE):
            prefix = (match.group(1) or "").upper()
            # 命中「标准番号」规则时过滤噪声前缀；其余规则不做前缀过滤
            if pattern == PATTERNS[-1][0] and prefix in _NOISE_PREFIXES:
                continue
            bangou = formatter(match)
            if not bangou or len(bangou) < 3:
                continue
            return {
                "bangou": bangou,
                "bangou_norm": normalize_bangou(bangou),
                "type": detect_type(bangou),
            }

    return None


__all__ = ["PATTERNS", "parse_bangou", "normalize_bangou", "detect_type"]
