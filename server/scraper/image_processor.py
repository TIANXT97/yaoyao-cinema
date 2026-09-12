"""夭夭影社 · 图片处理（ARCHITECTURE.md 2.4.5）。

职责：

* 下载封面 / 背景图（支持 URL 与本地 NFO 图片路径）；
* 智能裁切为 **2:3 竖版海报**（保留人物主体，横向大图优先取右侧）；
* 生成 16:9 横版 backdrop 与缩略图；
* JPEG 压缩优化后落盘至 ``media/posters`` / ``media/backdrops`` / ``media/thumbs``。

所有 ``*_path`` 返回值均为相对 ``MEDIA_ROOT`` 的路径，与数据库字段约定一致。
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional, Union

from PIL import Image, ImageOps, UnidentifiedImageError

from .. import config
from ..utils.logger import get_logger

logger = get_logger(__name__)

ImageSource = Union[str, Path, bytes, bytearray, Image.Image]

#: 海报标准尺寸（2:3）
POSTER_SIZE: tuple[int, int] = (400, 600)
#: 背景图标准尺寸（16:9）
BACKDROP_SIZE: tuple[int, int] = (1280, 720)
#: 缩略图标准尺寸（16:9）
THUMB_SIZE: tuple[int, int] = (320, 180)
#: JPEG 质量
JPEG_QUALITY = 90
BACKDROP_QUALITY = 88

POSTER_RATIO = 2 / 3
BACKDROP_RATIO = 16 / 9


class ImageProcessingError(RuntimeError):
    """图片下载 / 处理失败。"""


# ---------------------------------------------------------------------------
# 路径工具
# ---------------------------------------------------------------------------


def _relative(path: Path) -> str:
    """把绝对路径转为相对 ``MEDIA_ROOT`` 的路径（不在其内则原样返回）。"""
    try:
        return str(path.resolve().relative_to(config.MEDIA_ROOT.resolve()))
    except (ValueError, OSError):
        return str(path)


def _ensure_dirs() -> None:
    for directory in (
        config.POSTERS_DIR,
        config.BACKDROPS_DIR,
        config.THUMBS_DIR,
        config.ACTORS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 打开 / 保存
# ---------------------------------------------------------------------------


def open_image(source: ImageSource) -> Image.Image:
    """把多种输入统一转为 ``PIL.Image``（自动处理 EXIF 方向）。"""
    try:
        if isinstance(source, Image.Image):
            img = source
        elif isinstance(source, (bytes, bytearray)):
            img = Image.open(io.BytesIO(bytes(source)))
        elif isinstance(source, (str, Path)):
            path = Path(source)
            if not path.is_file():
                raise ImageProcessingError(f"图片文件不存在: {path}")
            img = Image.open(path)
        else:  # pragma: no cover - 类型兜底
            raise ImageProcessingError(f"不支持的图片来源: {type(source)!r}")
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageProcessingError(f"无法解析图片: {exc}") from exc

    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")
    return img


def save_jpeg(
    img: Image.Image,
    target: Path,
    *,
    quality: int = JPEG_QUALITY,
    progressive: bool = True,
) -> Path:
    """以 JPEG 保存（自动转 RGB、目录、优化）。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(
        target,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=progressive,
    )
    return target


def image_to_bytes(img: Image.Image, *, quality: int = JPEG_QUALITY) -> bytes:
    """把图片编码为 JPEG 字节。"""
    buffer = io.BytesIO()
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# 裁切算法
# ---------------------------------------------------------------------------


def _saliency_left(img: Image.Image, window_w: int) -> int:
    """基于列方向梯度能量的显著性裁切，返回裁切左边界。

    人物通常位于画面右侧且对比度高，这里按「列能量最大 + 平局取右」
    选择裁切窗口，既保留主体又符合日式封面惯例。
    """
    width, height = img.size
    if window_w >= width:
        return 0

    sample_w = 64
    sample_h = 64
    try:
        gray = img.convert("L").resize((sample_w, sample_h))
        pixels = gray.load()
    except (OSError, ValueError):  # pragma: no cover - 极端图片
        return width - window_w

    columns = [0.0] * sample_w
    for y in range(sample_h):
        previous = pixels[0, y]
        for x in range(1, sample_w):
            current = pixels[x, y]
            columns[x] += abs(current - previous)
            previous = current

    win = max(1, round(window_w / width * sample_w))
    best_score = -1.0
    best_x = sample_w - win
    for x0 in range(0, sample_w - win + 1):
        score = sum(columns[x0 : x0 + win])
        if score >= best_score:  # 平局取右
            best_score = score
            best_x = x0
    # 映射回原图坐标并按边界收敛
    left = round(best_x / sample_w * width)
    return max(0, min(left, width - window_w))


def crop_to_ratio(
    img: Image.Image,
    target_ratio: float,
    *,
    smart: bool = True,
    prefer: str = "auto",
) -> Image.Image:
    """把图片裁切为目标宽高比。

    * 横向图（比目标更宽）→ 裁宽度，``smart=True`` 用显著性选窗，否则取右侧；
    * 纵向图（比目标更窄）→ 裁高度，居中裁切。
    """
    if target_ratio <= 0:
        raise ValueError("target_ratio 必须为正数")

    width, height = img.size
    current_ratio = width / height
    if abs(current_ratio - target_ratio) < 0.02:
        return img

    if current_ratio > target_ratio:
        new_w = int(round(height * target_ratio))
        new_w = max(1, min(width, new_w))
        if prefer == "right":
            left = width - new_w
        elif prefer == "center" or not smart:
            left = (width - new_w) // 2
        else:
            left = _saliency_left(img, new_w)
        return img.crop((left, 0, left + new_w, height))

    new_h = int(round(width / target_ratio))
    new_h = max(1, min(height, new_h))
    top = (height - new_h) // 2
    return img.crop((0, top, width, top + new_h))


def crop_poster(
    img: Image.Image, aspect_ratio: tuple[int, int] = (2, 3)
) -> Image.Image:
    """裁切为 2:3 竖版海报。"""
    ratio = aspect_ratio[0] / aspect_ratio[1]
    return crop_to_ratio(img, ratio, smart=True)


def crop_backdrop(img: Image.Image) -> Image.Image:
    """裁切为 16:9 横版背景图。"""
    return crop_to_ratio(img, BACKDROP_RATIO, smart=True, prefer="center")


def resize_cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """先按比例缩放再居中裁切到精确尺寸。"""
    return ImageOps.fit(img, size, method=Image.LANCZOS, centering=(0.5, 0.5))


# ---------------------------------------------------------------------------
# 落盘
# ---------------------------------------------------------------------------


def save_poster(img: Image.Image, video_id: str) -> str:
    """把图片处理为 400x600 海报并保存，返回相对 MEDIA_ROOT 路径。"""
    _ensure_dirs()
    poster = crop_poster(img)
    poster = poster.resize(POSTER_SIZE, Image.LANCZOS)
    target = config.POSTERS_DIR / f"{video_id}.jpg"
    save_jpeg(poster, target, quality=JPEG_QUALITY)
    return _relative(target)


def save_backdrop(img: Image.Image, video_id: str) -> tuple[str, str]:
    """保存 16:9 backdrop 与缩略图，返回 (backdrop, thumb) 相对路径。"""
    _ensure_dirs()
    backdrop = crop_backdrop(img)
    backdrop = backdrop.resize(BACKDROP_SIZE, Image.LANCZOS)
    backdrop_target = config.BACKDROPS_DIR / f"{video_id}.jpg"
    save_jpeg(backdrop, backdrop_target, quality=BACKDROP_QUALITY)

    thumb = resize_cover(backdrop, THUMB_SIZE)
    thumb_target = config.THUMBS_DIR / f"{video_id}.jpg"
    save_jpeg(thumb, thumb_target, quality=JPEG_QUALITY)
    return _relative(backdrop_target), _relative(thumb_target)


def save_original(img: Image.Image, video_id: str, suffix: str = "raw") -> str:
    """保存原始（压缩）图片，用于兜底 / 调试。"""
    _ensure_dirs()
    target = config.BACKDROPS_DIR / f"{video_id}_{suffix}.jpg"
    save_jpeg(img, target, quality=JPEG_QUALITY)
    return _relative(target)


# ---------------------------------------------------------------------------
# 下载
# ---------------------------------------------------------------------------


async def _fetch_bytes(url: str | Path, client: Any | None = None) -> bytes:
    """读取网络 URL 或本地图片文件为字节。"""
    if isinstance(url, Path):
        return url.read_bytes()
    text = str(url)
    if text.startswith(("http://", "https://", "//")):
        if text.startswith("//"):
            text = "https:" + text
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise ImageProcessingError("httpx 未安装，无法下载图片") from exc
        if client is None:
            from ..utils.http_client import get_client

            client = await get_client()
        try:
            response = await client.get(text)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ImageProcessingError(f"图片下载失败 {text}: {exc}") from exc
        return response.content

    path = Path(text)
    if path.is_file():
        return path.read_bytes()
    raise ImageProcessingError(f"图片来源不存在: {text}")


async def download_image(
    url: str | Path,
    video_id: str,
    suffix: str = "backdrop",
    *,
    client: Any | None = None,
) -> Optional[str]:
    """下载图片并按 ``suffix`` 处理保存。

    * ``suffix="poster"``   → 2:3 海报，返回相对路径；
    * ``suffix="backdrop"`` → 16:9 backdrop，返回相对路径；
    * 其他 suffix           → 原图压缩保存。
    """
    try:
        raw = await _fetch_bytes(url, client=client)
        img = open_image(raw)
    except ImageProcessingError as exc:
        logger.warning("图片处理失败 %s: %s", url, exc)
        return None

    if suffix == "poster":
        return save_poster(img, video_id)
    if suffix == "backdrop":
        backdrop_path, _thumb = save_backdrop(img, video_id)
        return backdrop_path
    return save_original(img, video_id, suffix=suffix)


async def download_and_crop_poster(
    url: str | Path,
    video_id: str,
    aspect_ratio: tuple[int, int] = (2, 3),
    *,
    client: Any | None = None,
) -> Optional[str]:
    """下载封面并智能裁切为 2:3 竖版海报（ARCHITECTURE.md 2.4.5）。"""
    try:
        raw = await _fetch_bytes(url, client=client)
        img = open_image(raw)
    except ImageProcessingError as exc:
        logger.warning("海报下载 / 解析失败 %s: %s", url, exc)
        return None

    _ensure_dirs()
    poster = crop_poster(img, aspect_ratio=aspect_ratio)
    poster = poster.resize(POSTER_SIZE, Image.LANCZOS)
    target = config.POSTERS_DIR / f"{video_id}.jpg"
    save_jpeg(poster, target, quality=JPEG_QUALITY)
    return _relative(target)


async def download_and_process(
    video_id: str,
    *,
    poster_url: str | Path | None = None,
    backdrop_url: str | Path | None = None,
    client: Any | None = None,
) -> dict[str, Optional[str]]:
    """一次性下载并处理 poster + backdrop，返回字段字典。"""
    result: dict[str, Optional[str]] = {
        "poster_path": None,
        "backdrop_path": None,
        "thumb_path": None,
    }
    if poster_url:
        result["poster_path"] = await download_and_crop_poster(
            poster_url, video_id, client=client
        )
    if backdrop_url:
        try:
            raw = await _fetch_bytes(backdrop_url, client=client)
            img = open_image(raw)
            backdrop_path, thumb_path = save_backdrop(img, video_id)
            result["backdrop_path"] = backdrop_path
            result["thumb_path"] = thumb_path
        except ImageProcessingError as exc:
            logger.warning("背景图处理失败 %s: %s", backdrop_url, exc)
    # 有海报但无背景图时，用海报兜底生成 backdrop
    if result["backdrop_path"] is None and poster_url:
        try:
            raw = await _fetch_bytes(poster_url, client=client)
            img = open_image(raw)
            backdrop_path, thumb_path = save_backdrop(img, video_id)
            result["backdrop_path"] = backdrop_path
            result["thumb_path"] = thumb_path
        except ImageProcessingError:
            pass
    return result


__all__ = [
    "ImageProcessingError",
    "POSTER_SIZE",
    "BACKDROP_SIZE",
    "THUMB_SIZE",
    "open_image",
    "save_jpeg",
    "image_to_bytes",
    "crop_to_ratio",
    "crop_poster",
    "crop_backdrop",
    "resize_cover",
    "save_poster",
    "save_backdrop",
    "save_original",
    "download_image",
    "download_and_crop_poster",
    "download_and_process",
]
