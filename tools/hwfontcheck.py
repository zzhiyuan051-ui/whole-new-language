#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字体保真度批量校验：抽 300 个字形，量「墨迹占格比例」。

洄文字形是细笔画（点阵笔画），占格比例应在个位数百分比。
若某个字形占格超过 20%，说明它的某个元素被误填成了实心块。
这个判据不靠肉眼、也不靠两条通路的像素对齐，能直接扫出问题字形。
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hwglyph as G

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "font" / "GalHuiwen.ttf"
SIZE = 128

chars = json.loads((ROOT / "characters.json").read_text(encoding="utf-8"))["characters"]
sample = [c for c in chars if c["status"] == "defined"][::10]      # 每 10 个取 1 个

font = ImageFont.truetype(str(FONT), int(SIZE * 0.94))
img = Image.new("L", (SIZE, SIZE), 255)
d = ImageDraw.Draw(img)

bad = []
ratios = []
for c in sample:
    gid = int(c["glyph"])
    img.paste(255, (0, 0, SIZE, SIZE))
    d.text((SIZE // 2, SIZE // 2), chr(0xE000 + gid), font=font,
           fill=0, anchor="mm")
    ink = sum(1 for p in img.getdata() if p < 128)
    r = ink / (SIZE * SIZE)
    ratios.append(r)
    if r > 0.20:
        bad.append((gid, c.get("zh"), r))

ratios.sort()
n = len(ratios)
print(f"抽样 {n} 个字形（每 10 个取 1）")
print(f"  占格比例：最小 {ratios[0]:.1%}｜中位 {ratios[n // 2]:.1%}｜"
      f"最大 {ratios[-1]:.1%}｜均值 {sum(ratios) / n:.1%}")
print(f"  超过 20%（疑似被填实）的字形：{len(bad)} 个")
for gid, zh, r in bad[:10]:
    print(f"     字形 {gid}（{zh}）占格 {r:.1%}")

if not bad:
    print("→ 全部字形都是细笔画，字体轮廓保真")

# 出一张 8×8 的样张，直接看
grid = 8
tile = 200
canvas = Image.new("RGB", (tile * grid, tile * grid), "white")
dd = ImageDraw.Draw(canvas)
big = ImageFont.truetype(str(FONT), int(tile * 0.9))
lbl = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
picked = [c for c in chars if c["status"] == "defined"][:grid * grid]
for k, c in enumerate(picked):
    r, col = divmod(k, grid)
    dd.text((col * tile + tile // 2, r * tile + tile // 2), chr(0xE000 + int(c["glyph"])),
            font=big, fill="black", anchor="mm")
    dd.text((col * tile + tile // 2, r * tile + tile - 22), str(c.get("zh", "")),
            font=lbl, fill="#888", anchor="ma")
canvas.save(ROOT / "ime" / "_font_grid.png")
print(f"→ 样张 ime/_font_grid.png（{grid}×{grid} = {len(picked)} 字）")
