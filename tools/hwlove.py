#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「我爱你」的洄文字形渲染成一张图，并标出各自的输入键。

用真实字体文件画，不是另画一遍 —— 这样图上看到的就是输入法上屏后的样子。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FONT_PATH = ROOT / "font" / "GalHuiwen.ttf"
OUT = ROOT / "love.png"

# (中文, 归一化输入键, 候选序号, 码位, 读音)
ITEMS = [
    ("我", "yi", 6, 0xE3F5, "yî"),
    ("爱", "za", 3, 0xE14C, "zǎ"),
    ("你", "yo", 6, 0xE409, "yô"),
]

SCALE = 2                      # 2 倍图，缩放后更清晰
CELL = 260 * SCALE
PAD = 40 * SCALE
LABEL_H = 120 * SCALE
W = PAD * 2 + CELL * len(ITEMS)
H = PAD * 2 + CELL + LABEL_H + 70 * SCALE

img = Image.new("RGB", (W, H), "#ffffff")
d = ImageDraw.Draw(img)

glyph_font = ImageFont.truetype(str(FONT_PATH), int(CELL * 0.78))
try:
    ui_font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", int(30 * SCALE))
    key_font = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", int(26 * SCALE))
    small_font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", int(20 * SCALE))
except OSError:
    ui_font = key_font = small_font = ImageFont.load_default()

# 标题
title = "我爱你 · 洄文"
d.text((PAD, PAD // 2), title, font=ui_font, fill="#111111")

y0 = PAD + 40 * SCALE
for i, (zh, key, idx, cp, roman) in enumerate(ITEMS):
    x0 = PAD + i * CELL
    # 单元格
    d.rounded_rectangle([x0 + 6 * SCALE, y0 + 6 * SCALE,
                         x0 + CELL - 6 * SCALE, y0 + CELL - 6 * SCALE],
                        radius=16 * SCALE, outline="#d8d8d8", width=2 * SCALE)
    # 洄文字形（用真实字体画真实码位）
    g = chr(cp)
    bbox = d.textbbox((0, 0), g, font=glyph_font)
    gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((x0 + (CELL - gw) / 2 - bbox[0], y0 + (CELL - gh) / 2 - bbox[1]),
           g, font=glyph_font, fill="#111111")

    # 说明
    ly = y0 + CELL + 18 * SCALE
    d.text((x0 + 20 * SCALE, ly), f"{zh}  {roman}", font=ui_font, fill="#111111")
    # 这一行含中文，必须用中文字体画：Consolas 之类没有汉字，
    # 画出来是一个个空心方格（第一版就是这么出的，很难看）。
    d.text((x0 + 20 * SCALE, ly + 44 * SCALE), f"敲 {key} → 按 {idx}", font=ui_font,
           fill="#c0392b")
    d.text((x0 + 20 * SCALE, ly + 82 * SCALE), f"U+{cp:04X}", font=small_font,
           fill="#888888")

img.save(OUT)
print(f"已生成 {OUT}  ({img.width}x{img.height})")
for zh, key, idx, cp, roman in ITEMS:
    print(f"  {zh}  敲 {key} 按 {idx}   U+{cp:04X}   读 {roman}")
