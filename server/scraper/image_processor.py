"""夭夭影社 · 图片处理（ARCHITECTURE.md 2.4.5）。

职责：

* 下载封面 / 背景图（支持 URL 与本地 NFO 图片路径）；
* 智能裁切为 **2:3 竖版海报**（保留人物主体，横向大图优先取右侧）；
* 生成 16:9 横版 backdrop 与缩略图；
* JPEG 压缩优化后落盘至 ``media/posters`` / ``media/backdrops`` / ``media/thumbs``。

所有 ``*_path`` 返回值均为相对 ``MEDIA_ROOT`` 的路径，与数据库字段约定一致。
"""

from __future__ import annotations

import asyncio
import io
import ipaddress
import socket
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import urljoin, urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError

from .. import config
from ..utils.logger import get_logger

logger = get_logger(__name__)

#: 防解压像素炸弹上限（3000万像素）
Image.MAX_IMAGE_PIXELS = 30_000_000

#: 单张图片下载硬上限（15 MB）
MAX_IMAGE_DOWNLOAD_BYTES = 15 * 1024 * 1024

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
    """把多种输入统一转为 ``PIL.Image``（自动处理 EXIF 方向）。

    对文件 / 字节输入一律先 ``load()`` 到内存副本，并用 ``with`` 关闭底层
    文件句柄，避免高并发长任务下句柄泄漏。调用方获得的图像可安全 ``close()``。
    """
    owns_image = False
    try:
        if isinstance(source, Image.Image):
            img = source
        elif isinstance(source, (bytes, bytearray)):
            with Image.open(io.BytesIO(bytes(source))) as raw:
                raw.load()
                img = raw.copy()
            owns_image = True
        elif isinstance(source, (str, Path)):
            path = Path(source)
            if not path.is_file():
                raise ImageProcessingError(f"图片文件不存在: {path}")
            with Image.open(path) as raw:
                raw.load()
                img = raw.copy()
            owns_image = True
        else:  # pragma: no cover - 类型兜底
            raise ImageProcessingError(f"不支持的图片来源: {type(source)!r}")
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageProcessingError(f"无法解析图片: {exc}") from exc

    # EXIF 方向纠正（可能返回新对象）
    transposed = ImageOps.exif_transpose(img)
    if transposed is not img:
        if owns_image:
            img.close()
        img = transposed
        owns_image = True

    # 统一为 RGB（L / P / RGBA 等一律转换）
    if img.mode != "RGB":
        converted = img.convert("RGB")
        if owns_image:
            img.close()
        img = converted
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
    converted: Optional[Image.Image] = None
    if img.mode != "RGB":
        converted = img.convert("RGB")
        img = converted
    try:
        img.save(
            target,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=progressive,
        )
    finally:
        if converted is not None:
            converted.close()
    return target


def image_to_bytes(img: Image.Image, *, quality: int = JPEG_QUALITY) -> bytes:
    """把图片编码为 JPEG 字节。"""
    buffer = io.BytesIO()
    converted: Optional[Image.Image] = None
    if img.mode != "RGB":
        converted = img.convert("RGB")
        img = converted
    try:
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
    finally:
        if converted is not None:
            converted.close()
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
    gray: Optional[Image.Image] = None
    try:
        gray = img.convert("L").resize((sample_w, sample_h))
        pixels = gray.load()

        columns = [0.0] * sample_w
        for y in range(sample_h):
            previous = pixels[0, y]
            for x in range(1, sample_w):
                current = pixels[x, y]
                columns[x] += abs(current - previous)
                previous = current
    except (OSError, ValueError):  # pragma: no cover - 极端图片
        return width - window_w
    finally:
        if gray is not None:
            gray.close()

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
    resized = poster.resize(POSTER_SIZE, Image.LANCZOS)
    if poster is not img:
        poster.close()
    try:
        target = config.POSTERS_DIR / f"{video_id}.jpg"
        save_jpeg(resized, target, quality=JPEG_QUALITY)
    finally:
        resized.close()
    return _relative(target)


def save_backdrop(img: Image.Image, video_id: str) -> tuple[str, str]:
    """保存 16:9 backdrop 与缩略图，返回 (backdrop, thumb) 相对路径。"""
    _ensure_dirs()
    backdrop = crop_backdrop(img)
    resized = backdrop.resize(BACKDROP_SIZE, Image.LANCZOS)
    if backdrop is not img:
        backdrop.close()
    try:
        backdrop_target = config.BACKDROPS_DIR / f"{video_id}.jpg"
        save_jpeg(resized, backdrop_target, quality=BACKDROP_QUALITY)

        thumb = resize_cover(resized, THUMB_SIZE)
        try:
            thumb_target = config.THUMBS_DIR / f"{video_id}.jpg"
            save_jpeg(thumb, thumb_target, quality=JPEG_QUALITY)
        finally:
            thumb.close()
    finally:
        resized.close()
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


async def _validate_safe_url(url: str) -> str:
    """校验图片下载 URL 协议与目标主机，防范 SSRF 穿透内网设备与 DNS 重绑定。

    防御矩阵：
    1. 限制协议仅允许 http / https；
    2. 兼容并拦截所有畸形/变形 IPv4（如 127.1 / 2130706433 / 0x7f.1 / 0177.0.0.1）；
    3. 拦截标准 IPv4/IPv6 私有保留段与回环网段；
    4. 对域名在线程池中异步执行 getaddrinfo 解析，核验所有 A/AAAA 记录，禁止解析到内网或保留地址。
       （避免同步 DNS 阻塞单 worker 事件循环造成切片播放停摆）
    """
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ImageProcessingError(f"不支持的图片 URL 协议: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ImageProcessingError(f"非法的图片 URL 主机: {url}")

    lower_host = hostname.lower()

    # 1. 尝试使用 socket.inet_aton 归一化解析（堵死 Linux glibc 兼容的 127.1 / 0x7f.1 / 整数十进制 IP）
    try:
        raw_bytes = socket.inet_aton(lower_host)
        ip = ipaddress.IPv4Address(raw_bytes)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ImageProcessingError(f"禁止访问内网或保留 IP: {hostname} -> {ip}")
    except (OSError, ValueError):
        pass

    # 2. 尝试标准 IPv6 / 括号 IP
    clean_host = lower_host.strip("[]")
    try:
        ip = ipaddress.ip_address(clean_host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ImageProcessingError(f"禁止访问内网或保留 IP: {hostname} -> {ip}")
    except ValueError:
        pass

    # 3. 拦截常见本地别名
    if lower_host in ("localhost", "localhost.localdomain"):
        raise ImageProcessingError(f"禁止访问本地回环主机: {hostname}")

    # 4. 真实 DNS 解析校验所有解析地址（放入线程池异步执行，防冻结事件循环）
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, lower_host, None, 0, socket.SOCK_STREAM, socket.IPPROTO_TCP
        )
        if not infos:
            raise ImageProcessingError(f"无法解析的主机: {hostname}")
        for info in infos:
            resolved_ip_str = info[4][0]
            resolved_ip = ipaddress.ip_address(resolved_ip_str)
            if (
                resolved_ip.is_private
                or resolved_ip.is_loopback
                or resolved_ip.is_link_local
                or resolved_ip.is_multicast
                or resolved_ip.is_reserved
                or resolved_ip.is_unspecified
            ):
                raise ImageProcessingError(
                    f"目标域名解析到内网/保留地址: {hostname} -> {resolved_ip}"
                )
    except socket.gaierror as exc:
        raise ImageProcessingError(f"域名解析失败: {hostname}") from exc

    return url


async def _fetch_bytes(url: str | Path, client: Any | None = None) -> bytes:
    """读取网络 URL 或本地图片文件为字节（安全逐跳校验 + 连接复用 + 15MB 尺寸熔断）。

    注意：图片下载出于 SSRF 防护红线强制使用独立的限制重定向客户端，调用方传入的 client 将被忽略。
    """
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

        # 针对图片下载建立独立的、不盲从重定向的专用下载客户端；将 client 提到重定向循环外以保留连接池复用
        max_redirects = 5
        current_url = text
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=False,
            headers={"User-Agent": "YaoyaoCinema/1.0 ImageDownloader"},
        ) as dl_client:
            for _ in range(max_redirects + 1):
                await _validate_safe_url(current_url)
                try:
                    async with dl_client.stream("GET", current_url) as response:
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                raise ImageProcessingError(f"重定向缺少 Location 头: {current_url}")
                            current_url = urljoin(current_url, location)
                            continue

                        response.raise_for_status()
                        chunks = []
                        downloaded = 0
                        async for chunk in response.aiter_bytes():
                            downloaded += len(chunk)
                            if downloaded > MAX_IMAGE_DOWNLOAD_BYTES:
                                raise ImageProcessingError(
                                    f"图片体积超出安全上限 ({MAX_IMAGE_DOWNLOAD_BYTES // (1024 * 1024)}MB): {text}"
                                )
                            chunks.append(chunk)
                        return b"".join(chunks)
                except httpx.HTTPError as exc:
                    raise ImageProcessingError(f"图片下载失败 {current_url}: {exc}") from exc

        raise ImageProcessingError(f"图片下载重定向次数过多 (>5): {text}")

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

    try:
        if suffix == "poster":
            return save_poster(img, video_id)
        if suffix == "backdrop":
            backdrop_path, _thumb = save_backdrop(img, video_id)
            return backdrop_path
        return save_original(img, video_id, suffix=suffix)
    finally:
        img.close()


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
    target = config.POSTERS_DIR / f"{video_id}.jpg"
    try:
        cropped = crop_poster(img, aspect_ratio=aspect_ratio)
        resized = cropped.resize(POSTER_SIZE, Image.LANCZOS)
        if cropped is not img:
            cropped.close()
        try:
            save_jpeg(resized, target, quality=JPEG_QUALITY)
        finally:
            resized.close()
    finally:
        img.close()
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
            try:
                backdrop_path, thumb_path = save_backdrop(img, video_id)
            finally:
                img.close()
            result["backdrop_path"] = backdrop_path
            result["thumb_path"] = thumb_path
        except ImageProcessingError as exc:
            logger.warning("背景图处理失败 %s: %s", backdrop_url, exc)
    # 有海报但无背景图时，用海报兜底生成 backdrop
    if result["backdrop_path"] is None and poster_url:
        try:
            raw = await _fetch_bytes(poster_url, client=client)
            img = open_image(raw)
            try:
                backdrop_path, thumb_path = save_backdrop(img, video_id)
            finally:
                img.close()
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
