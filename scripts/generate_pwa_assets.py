#!/usr/bin/env python3
"""夭夭影社 · PWA 静态资源生成器。

对齐 docs/ARCHITECTURE.md 第 3.3 节与 Phase 5 任务：
- 生成 PWA 各尺寸图标（192 / 512 / maskable-512 / apple-touch）
- 生成 iOS 常见机型启动屏（防止冷启动白屏闪烁）

设计语言：东方纯白极简通透。
- 纯白底 + 极细分割线圆环
- 品牌金 #D4A574 播放三角
- 墨点 #1A1A1A 收束

用法::

    python3 scripts/generate_pwa_assets.py

依赖：Pillow（服务端 requirements.txt 已声明）。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

# —— 路径 ——
ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
ICONS_DIR = PUBLIC / "icons"
SPLASH_DIR = PUBLIC / "splash"
ANDROID_RES = ROOT / "android" / "app" / "src" / "main" / "res"

# Android 启动图标密度 → 尺寸
LAUNCHER_SIZES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}
ADAPTIVE_FOREGROUND_SIZES = {
    "mdpi": 108,
    "hdpi": 162,
    "xhdpi": 216,
    "xxhdpi": 324,
    "xxxhdpi": 432,
}

# —— 设计 Token（对齐 frontend/src/style.css） ——
WHITE = (255, 255, 255, 255)
LINE = (235, 235, 235, 255)
RING = (242, 242, 242, 255)
GOLD = (212, 165, 116, 255)
INK = (26, 26, 26, 255)

SS = 4  # 超采样倍数，保证边缘平滑


def _render_icon(px: int, *, full_bleed: bool = False, circular: bool = False) -> Image.Image:
    """渲染单枚应用图标。

    :param px: 输出边长（像素）
    :param full_bleed: 是否全幅出血（maskable 用，四角不透明、无描边）
    :param circular: 是否圆形裁切（安卓 legacy 圆形图标）
    """
    size = px * SS
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def s(value: float) -> float:
        """把 512 基准坐标映射到当前画布。"""
        return value / 512 * size

    if circular:
        draw.ellipse([0, 0, size - 1, size - 1], fill=WHITE)
    elif full_bleed:
        draw.rectangle([0, 0, size - 1, size - 1], fill=WHITE)
    else:
        draw.rounded_rectangle(
            [0, 0, size - 1, size - 1], radius=s(112), fill=WHITE
        )
        # 极细外描边
        draw.rounded_rectangle(
            [s(16), s(16), s(496), s(496)],
            radius=s(96),
            outline=LINE,
            width=max(1, round(s(2))),
        )

    # 通透圆环
    draw.ellipse(
        [s(106), s(106), s(406), s(406)],
        outline=RING,
        width=max(1, round(s(2))),
    )

    # 品牌金播放三角（视觉重心居中）
    draw.polygon(
        [(s(218), s(176)), (s(346), s(256)), (s(218), s(336))],
        fill=GOLD,
    )

    # 墨点收束
    draw.ellipse([s(167), s(247), s(185), s(265)], fill=INK)

    return img.resize((px, px), Image.LANCZOS)


def _render_adaptive_foreground(px: int) -> Image.Image:
    """渲染安卓自适应图标前景（透明底，图形收束于安全区）。"""
    size = px * SS
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = size / 2
    scale = 0.60 * size / 512

    def s(value: float) -> float:
        return center + (value - 256) * scale

    draw.ellipse(
        [s(106), s(106), s(406), s(406)],
        outline=RING,
        width=max(1, round(2 * scale)),
    )
    draw.polygon(
        [(s(218), s(176)), (s(346), s(256)), (s(218), s(336))],
        fill=GOLD,
    )
    draw.ellipse([s(167), s(247), s(185), s(265)], fill=INK)
    return img.resize((px, px), Image.LANCZOS)


def _render_splash(width: int, height: int, icon_px: int) -> Image.Image:
    """渲染纯白启动屏 + 居中图标。"""
    img = Image.new("RGB", (width, height), WHITE[:3])
    icon = _render_icon(icon_px)
    x = (width - icon_px) // 2
    y = int(height * 0.40)
    img.paste(icon, (x, y), icon)
    return img


# 苹果常见机型启动屏（宽 x 高）
SPLASH_SIZES: list[tuple[int, int]] = [
    (1170, 2532),  # iPhone 12 / 13 / 14
    (1179, 2556),  # iPhone 15 / 16
    (1284, 2778),  # iPhone 12 / 13 Pro Max
    (1290, 2796),  # iPhone 14 / 15 Pro Max
    (1125, 2436),  # iPhone X / XS / 11 Pro
    (828, 1792),   # iPhone XR / 11
    (750, 1334),   # iPhone 8
    (1536, 2048),  # iPad mini / Air
    (1668, 2388),  # iPad Pro 11"
    (2048, 2732),  # iPad Pro 12.9"
]


def _generate_android_icons() -> int:
    """生成安卓 legacy + 自适应图标（对齐同一套品牌图形）。"""
    if not ANDROID_RES.is_dir():
        return 0

    generated = 0
    for density, launcher_px in LAUNCHER_SIZES.items():
        directory = ANDROID_RES / f"mipmap-{density}"
        directory.mkdir(parents=True, exist_ok=True)
        _render_icon(launcher_px).save(directory / "ic_launcher.png")
        _render_icon(launcher_px, circular=True).save(
            directory / "ic_launcher_round.png"
        )
        _render_adaptive_foreground(
            ADAPTIVE_FOREGROUND_SIZES[density]
        ).save(directory / "ic_launcher_foreground.png")
        generated += 3
    return generated


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    SPLASH_DIR.mkdir(parents=True, exist_ok=True)

    # —— PWA 图标 ——
    _render_icon(192).save(ICONS_DIR / "icon-192.png")
    _render_icon(512).save(ICONS_DIR / "icon-512.png")
    _render_icon(512, full_bleed=True).save(ICONS_DIR / "icon-maskable-512.png")
    _render_icon(180).save(ICONS_DIR / "apple-touch-icon.png")
    _render_icon(32).save(ICONS_DIR / "favicon-32.png")

    # —— iOS 启动屏 ——
    for width, height in SPLASH_SIZES:
        icon_px = int(min(width, height) * 0.22)
        _render_splash(width, height, icon_px).save(
            SPLASH_DIR / f"splash-{width}x{height}.png"
        )

    print(f"✓ 图标已生成 → {ICONS_DIR}")
    print(f"✓ 启动屏 {len(SPLASH_SIZES)} 张已生成 → {SPLASH_DIR}")

    android_count = _generate_android_icons()
    if android_count:
        print(f"✓ 安卓图标 {android_count} 张已生成 → {ANDROID_RES}")


if __name__ == "__main__":
    main()
