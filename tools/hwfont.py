#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 字体生成（真 .ttf）

从渲染器的几何直接生成 TrueType 字体：
  · 15000 个字形，码位在私用区 PUA（U+E000 起）
  · **每个笔画都转成有面积的轮廓**——这是关键：
    笔画在 SVG 里是「线」（零面积），在字体里会消失，必须变成细长矩形/圆/多边形。
  · 用 fontTools 的 TTGlyphPen 构建 glyf 轮廓（二次贝塞尔），自己写 cmap/hmtx/name/os2

输出：
  font/GalHuiwen.ttf     字体文件（可安装）
  font/pua-map.csv       码位映射（已有）
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import hwglyph as G

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "font"
OUT.mkdir(exist_ok=True)

PUA_BASE = 0xE000
EM = 1000
PAD = 0.06
_SCALE = EM * (1 - 2 * PAD) / max(G.SIZE_W, G.SIZE_H)
_OFF_X = (EM - G.SIZE_W * _SCALE) / 2
_OFF_Y = (EM - G.SIZE_H * _SCALE) / 2

# 笔画粗细（渲染器里是 stroke-width 2.2，含圆头；字体里用实心细条近似）
STROKE = 2.2


def sx(v: float) -> float:
    return v * _SCALE + _OFF_X


def sy(v: float) -> float:
    return (G.SIZE_H - v) * _SCALE + _OFF_Y


def sw(v: float) -> float:
    return v * _SCALE


# ---------------------------------------------------------------- SVG 元素 → 轮廓
TAG_RE = re.compile(
    r"<(circle|ellipse|rect|line|polyline|polygon|path)\s*([^>]*?)\s*/?>")
ATTR_RE = re.compile(r'([a-zA-Z][a-zA-Z0-9-]*)="([^"]*)"')


def _attrs(s: str) -> dict[str, str]:
    return dict(ATTR_RE.findall(s))


def _pts(s: str) -> list[tuple[float, float]]:
    out = []
    for p in s.split():
        if "," in p:
            a, b = p.split(",")
            out.append((float(a), float(b)))
    return out



def _contour(pen, pts) -> None:
    """用 TTGlyphPen 画一个闭合多边形。"""
    if len(pts) < 3:
        return
    pen.moveTo((round(pts[0][0], 2), round(pts[0][1], 2)))
    for x, y in pts[1:]:
        pen.lineTo((round(x, 2), round(y, 2)))
    pen.closePath()


def _even_odd_trick(pen, outer, inner):
    """外圈 + 内圈**反向** = 一个环。

    TrueType 用**非零环绕**填充：只有内外圈方向相反才会挖空。
    方向相同的话内圈不挖洞，整块填实——实测症状就是「字变成黑方块」。
    """
    _contour(pen, list(reversed(outer)))
    _contour(pen, inner)


def _circle_pts(cx, cy, r, n=16):
    return [(cx + r * math.cos(2 * math.pi * k / n),
             cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _ring(cx, cy, r_out, r_in, pen, n=16):
    _even_odd_trick(pen,
                    _circle_pts(cx, cy, r_out, n),
                    _circle_pts(cx, cy, r_in, n))


def _rect_ring(x, y, w, h, t, pen):
    """空心矩形（边框）"""
    _even_odd_trick(pen,
                    [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                    [(x + t, y + t), (x + w - t, y + t),
                     (x + w - t, y + h - t), (x + t, y + h - t)])


def _bar(x1, y1, x2, y2, t, pen):
    """一条有粗细的线段 → 旋转后的矩形（四个角）"""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    px, py = -uy * t / 2, ux * t / 2
    _contour(pen, ((x1 + px, y1 + py), (x2 + px, y2 + py),
                   (x2 - px, y2 - py), (x1 - px, y1 - py)))


def _round_rect_ring(x, y, w, h, r, t, pen):
    """圆角空心矩形（边框 / 药丸）——用八边形近似"""
    def ring(rr, inset):
        k = min(rr, min(w, h) / 2)
        return [(x + inset + k, y + inset),
                (x + w - inset - k, y + inset),
                (x + w - inset, y + inset + k),
                (x + w - inset, y + h - inset - k),
                (x + w - inset - k, y + h - inset),
                (x + inset + k, y + h - inset),
                (x + inset, y + h - inset - k),
                (x + inset, y + inset + k)]
    _even_odd_trick(pen, ring(r, 0), ring(max(0.0, r - t), t))


def _stroke_path(pen, pts, thickness: float, closed: bool) -> None:
    """把一条折线「描边」成有面积的细条（字体里线没有面积，必须变成细条）。

    渲染器画边框用的是 `<polygon fill="none">` / `<polyline fill="none">`，
    那是**描边**不是填充。若误当填充，整个菱形/多边形会被填实
    （实测：菱形边框被填成 257442 的面积，占 25.7%）。
    """
    seq = list(pts) + ([pts[0]] if closed and len(pts) > 2 else [])
    for k in range(len(seq) - 1):
        _bar(seq[k][0], seq[k][1], seq[k + 1][0], seq[k + 1][1], thickness, pen)


def _ellipse_pts(cx, cy, rx, ry, n=24):
    return [(cx + rx * math.cos(2 * math.pi * k / n),
             cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)]


def element_to_pen(el_tag: str, a: dict[str, str], pen, t: float) -> None:
    """把渲染器的一个 SVG 元素转成轮廓。线 → 有面积的细条，环 → 挖空。"""

    def num(key: str, default: float | None = None) -> float:
        """读数值属性。缺了就报清楚是哪个元素缺哪个属性，别让它变成 KeyError。"""
        if key not in a:
            if default is None:
                raise ValueError(f"元素 <{el_tag}> 缺属性 {key}；实得属性 {sorted(a)}")
            return default
        return float(a[key])

    if el_tag == "circle":
        cx, cy, r = sx(num("cx")), sy(num("cy")), sw(num("r"))
        if a.get("fill") == "none":                     # 空心圆 → 环
            _ring(cx, cy, r + sw(STROKE) / 2, max(0.1, r - sw(STROKE) / 2), pen)
        else:
            # 实心点 → **实心**圆。不能做成环：点就是点，
            # 做成环在小字号下会变成一个模糊的空心圈（这个坑踩过）。
            _contour(pen, _circle_pts(cx, cy, r, 20))
    elif el_tag == "rect":
        x, y0, w, h = num("x"), num("y"), num("width"), num("height")
        rx = num("rx", 0.0)
        X, Y = sx(x), sy(y0 + h)
        W, H = sw(w), sw(h)
        tt = sw(t)
        if a.get("fill") == "none":
            if rx > 0.5:
                _round_rect_ring(X, Y, W, H, sw(rx), tt, pen)
            else:
                _rect_ring(X, Y, W, H, tt, pen)
        else:
            _contour(pen, ((X, Y), (X + W, Y), (X + W, Y + H), (X, Y + H)))
    elif el_tag == "ellipse":
        # 圆形/菱形边框那一族用 ellipse 画描边；此前整个漏掉了，会掉边框
        cx, cy = sx(num("cx")), sy(num("cy"))
        rx, ry = sw(num("rx")), sw(num("ry"))
        w = sw(num("stroke-width", STROKE)) or sw(STROKE)
        _stroke_path(pen, _ellipse_pts(cx, cy, rx, ry), w, closed=True)
    elif el_tag == "line":
        x1, y1 = sx(num("x1")), sy(num("y1"))
        x2, y2 = sx(num("x2")), sy(num("y2"))
        width = num("stroke-width", STROKE)
        _bar(x1, y1, x2, y2, sw(max(width, STROKE)), pen)
    elif el_tag in ("polyline", "polygon"):
        pts = [(sx(px), sy(py)) for px, py in _pts(a.get("points", ""))]
        w = sw(num("stroke-width", STROKE)) or sw(STROKE)
        if a.get("fill") == "none":
            # 渲染器的边框就是 fill="none" 的描边 —— 必须描边，不能填充
            _stroke_path(pen, pts, w, closed=(el_tag == "polygon"))
        elif len(pts) >= 3:
            _contour(pen, pts)
    # path 元素（少数弯弧）本轮跳过：那几式用折线近似已足够


def glyph_contours(glyph: int, class_no: int, family: int, pen,
                   with_box: bool = False) -> None:
    """把一个字形的笔画写进字体轮廓。

    **with_box 必须为 False**：`box=True` 会加上字表卡片的底色矩形，
    那是个**实心矩形**，写进字体后整个字会变成一块黑方块
    （实测：它的有向面积 +624036，占满整格，把真正的笔画全盖住）。
    字体里一个字只能有笔画，不能有卡片底色。
    """
    svg = G.glyph_svg(glyph, class_no=class_no, family=family, box=with_box)
    for m in TAG_RE.finditer(svg):
        element_to_pen(m.group(1), _attrs(m.group(2)), pen, STROKE)


# ---------------------------------------------------------------- 组装字体
def build_ttf(path: Path, chars: list[dict]) -> None:
    """只用**已定义且已分配码位**的字符建字体。

    为什么不含那 12000 个「备用字」：
      字体里的每个字形都要占一个 Unicode 码位，而 **GDI 拒收任何码位越出
      BMP（U+FFFF）的字体** —— 实测同样是 15000 个字形，
      起 U+3400（末 U+6E97，在 BMP 内）通过，起 U+E000（末 U+11A97，越界）被拒。
      BMP 内可自由使用的是私用区 U+E000–U+F8FF，共 6400 个码位，
      装不下 15000 个。而 12000 个备用字**尚未指派给任何词**，
      没有词会用到它们，进字体没有意义 —— 等它们被指派了再进。
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    use = [c for c in chars
           if c.get("codepoint") not in (None, "", "None")
           and c.get("status") == "defined"]
    use.sort(key=lambda c: int(c["codepoint"]))

    def gname(c: dict) -> str:
        return f"u{int(c['codepoint']):04X}"

    order = [".notdef"] + [gname(c) for c in use]
    fb = FontBuilder(EM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({int(c["codepoint"]): gname(c) for c in use})

    glyphs = {}
    pen = TTGlyphPen(None)
    _contour(pen, ((80, 0), (920, 0), (920, 80), (80, 80)))
    glyphs[".notdef"] = pen.glyph()

    for c in use:
        pen_g = TTGlyphPen(None)
        glyph_contours(int(c["glyph"]), int(c["class_no"]),
                       int(c.get("family", 0) or 0), pen_g)
        glyphs[gname(c)] = pen_g.glyph()

    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (EM, 0) for n in order})
    fb.setupHorizontalHeader(ascent=int(EM * 0.88), descent=-int(EM * 0.12))
    fb.setupNameTable({
        "familyName": "GalHuiwen", "styleName": "Regular",
        "uniqueFontIdentifier": "GalHuiwen-Regular-1.0",
        "fullName": "GalHuiwen Regular", "psName": "GalHuiwen-Regular",
        "version": "Version 1.0",
        "copyright": "洄文（Gal Huiwen）· 自源文字 · 字形由编号生成",
    })
    fb.setupOS2(sTypoAscender=int(EM * 0.88), sTypoDescender=-int(EM * 0.12),
                usWinAscent=int(EM * 0.88), usWinDescent=int(EM * 0.12),
                achVendID="GALH",
                # fsType=0 = 安装不受限。fontTools 默认给 4（只许预览与打印），
                # 那会让 Windows 的 AddFontResourceEx / 安装**直接拒绝**这个字体
                #（这个坑真踩过：PIL 能渲染，系统加载器却返回 0）。
                fsType=0)
    # 算出正确的 Unicode 范围位（私用区要置 PUA 那一位，否则某些加载器判定异常）
    try:
        from fontTools.ttLib.tables.O_S_2f_2 import calcUnicodeRanges
        os2 = fb.font["OS/2"]
        r1, r2, r3, r4 = calcUnicodeRanges(fb.font)
        os2.ulUnicodeRange1, os2.ulUnicodeRange2 = r1, r2
        os2.ulUnicodeRange3, os2.ulUnicodeRange4 = r3, r4
    except Exception as exc:                       # noqa: BLE001
        print(f"  （Unicode 范围位未自动计算：{exc}）")
    fb.setupPost()
    fb.save(str(path))


def main() -> None:
    chars = json.loads((ROOT / "characters.json").read_text(
        encoding="utf-8"))["characters"]
    use = [c for c in chars if c.get("status") == "defined"
           and c.get("codepoint") not in (None, "", "None")]
    print(f"准备生成字体：已定义 {len(use)} 字"
          f"（备用 {len(chars) - len(use)} 字无码位，不进字体）")
    ttf = OUT / "GalHuiwen.ttf"
    build_ttf(ttf, chars)
    print(f"→ {ttf.name}（{ttf.stat().st_size // 1024} KB）")

    # 自检：用 fontTools 读回来，验证码位与轮廓
    from fontTools.ttLib import TTFont
    f = TTFont(str(ttf))
    cmap = f.getBestCmap()
    glyf = f["glyf"]
    nonempty = sum(1 for g in f.getGlyphOrder()
                   if g in glyf and glyf[g].numberOfContours > 0)
    cps = sorted(cmap)
    print(f"  读回：字形 {len(f.getGlyphOrder())}｜码位 {len(cmap)}｜有轮廓 {nonempty}")
    print(f"  码位范围 U+{cps[0]:04X} .. U+{cps[-1]:04X}"
          f"（BMP 内：{cps[-1] <= 0xFFFF}）")

    # 更新 pua-map.csv（只有已定义字有码位）
    import csv
    with (OUT / "pua-map.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["glyph", "codepoint", "char", "status", "form", "syll",
                    "zh", "class_zh", "family"])
        for c in chars:
            cp = c.get("codepoint")
            has = cp not in (None, "", "None")
            w.writerow([c["glyph"], f"U+{int(cp):04X}" if has else "",
                        chr(int(cp)) if has else "", c["status"],
                        c.get("form", ""), c.get("syll", ""), c.get("zh", ""),
                        c.get("class_zh", ""), c.get("family", 0)])
    print(f"  pua-map.csv 已更新（{len(use)} 行有码位）")

    # 抽查几个字
    by_zh = {c.get("zh"): c for c in use}
    for zh in ("爱", "我", "你", "雨", "现实"):
        c = by_zh.get(zh)
        if c and int(c["codepoint"]) in cmap:
            g = cmap[int(c["codepoint"])]
            print(f"  {zh} U+{int(c['codepoint']):04X} → {g}，"
                  f"轮廓数 {glyf[g].numberOfContours}")


if __name__ == "__main__":
    main()
