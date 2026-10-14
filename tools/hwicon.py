#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给洄文输入法生成 Windows 图标（.ico）。

用「爱」的字形做图标——它是这门语言最常见的示范词。
多尺寸打包（16/24/32/48/64/128/256），Windows 会按场合自己挑。
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "font" / "GalHuiwen.ttf"
OUT = ROOT / "font" / "GalHuiwen.ico"
CP = 0xE2CC          # 爱


def tile(px: int, transparent: bool = True) -> Image.Image:
    """把字形画在一块圆角底板上。

    小尺寸要加粗：洄文字是细笔画，16/24 px 下会细到看不见。
    用 PIL 的文字描边（stroke_width）按比例加粗，小图标才立得住。
    """
    ss = 4                                    # 超采样，边缘更干净
    S = px * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(S * 0.06)
    r = int(S * 0.20)
    d.rounded_rectangle((pad, pad, S - pad, S - pad), radius=r,
                        fill=(251, 250, 247, 255), outline=(216, 212, 204, 255),
                        width=max(1, int(S * 0.012)))
    f = ImageFont.truetype(str(FONT), int(S * 0.74))
    # 加粗量：小尺寸相对更粗（px=16 时约 1.2 物理像素）
    stroke = max(1, round(S * 0.016)) if px <= 64 else max(1, round(S * 0.008))
    d.text((S // 2, int(S * 0.52)), chr(CP), font=f, fill=(27, 27, 31, 255),
           anchor="mm", stroke_width=stroke, stroke_fill=(27, 27, 31, 255))
    return img.resize((px, px), Image.LANCZOS)


def main() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base = tile(256)
    base.save(OUT, format="ICO",
              sizes=[(s, s) for s in sizes])
    print(f"图标 → {OUT}（{OUT.stat().st_size // 1024} KB，"
          f"尺寸 {', '.join(str(s) for s in sizes)}）")

    preview = ROOT / "ime" / "_icon_preview.png"
    strip = Image.new("RGBA", (256 * len(sizes) + 20 * (len(sizes) - 1), 256),
                      (255, 255, 255, 0))
    for k, s in enumerate(sizes):
        strip.paste(tile(s), (k * (256 + 20), 0), tile(s))
    strip.save(preview)
    print(f"预览 → {preview}")


if __name__ == "__main__":
    main()
