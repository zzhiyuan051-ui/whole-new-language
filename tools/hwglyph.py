#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 字形生成器（spec/01-script.md 的可执行实现）

字形 = f(编号 i)。本文件是那条函数的唯一实现，字表由它渲染，不手抄。

几何事实（与规范一致）：
  九宫扩展为 **4×5 格**；中央格留给「语义类标记」；其余 8 格为数字位（位1..位8）。
  位1/位2 用双笔以压重心；位9..位12 本轮留空（未来扩充）。
  边框 = i mod 3（可心算的校验，因 4^k ≡ 1 (mod 3)）。
"""
from __future__ import annotations

from pathlib import Path

CELL = 54                        # 格宽
COLS, ROWS = 4, 5                # 4 列 × 5 行
MARGIN = 13                      # 图外留白
PAD_X = MARGIN
PAD_Y = MARGIN
GRID_W = CELL * COLS
GRID_H = CELL * ROWS
SIZE_W = GRID_W + PAD_X * 2
SIZE_H = GRID_H + PAD_Y * 2
SIZE = SIZE_W                # 兼容旧调用：方块边长
INK = CELL * 0.34            # 单笔画最大外伸（保证不越格）

CENTER = (2, 2)              # 中央格（列, 行）——语义类标记
CX = PAD_X + CENTER[0] * CELL + CELL / 2
CY = PAD_Y + CENTER[1] * CELL + CELL / 2
HALF_W = GRID_W / 2
HALF_H = GRID_H / 2

# 位 → 格坐标（列, 行）。顺序：位1 最重，位8 最轻；与第一版前 6 位顺序一致。
POS = {
    1: (0, 0),   # 左上
    2: (1, 0),   # 上中左
    3: (3, 0),   # 右上
    4: (3, 4),   # 右下
    5: (2, 4),   # 下中
    6: (0, 4),   # 左下
    7: (1, 1),   # 上中右（第一次启用）
    8: (3, 2),   # 右中（第一次启用）
    9: (0, 2),   # 左中（预留）
    10: (1, 3),  # 下中左（预留）
    11: (2, 0),  # 上中（预留）
    12: (2, 3),  # 中下（预留）
}
USED = [1, 2, 3, 4, 5, 6, 7, 8]
WEIGHT = {p: 4 ** (8 - k) for k, p in enumerate(USED, start=1)}
GLYPH_SPACE = 4 ** len(USED)     # 65536

BORDER_BY_CHECK = {0: "square", 1: "circle", 2: "diamond"}

# 20 个语义类，各有专属的中央标记（互不相同的形）
CLASS_MARKS = [
    "dot", "ddot", "tdot", "qdot", "ring", "dring", "pill", "chev",
    "wye", "tri3", "bar", "xdot", "ydot", "cdot", "odot", "udot",
    "tribar", "trichev", "diag", "sqdot",
]
CLASS_ZH = [
    "本体", "数量", "空间", "时间", "运动", "身体", "心灵", "社会", "经济", "信息",
    "美感", "伦理", "情感", "自然", "数理", "技术", "饮食", "服饰", "建筑", "交通",
    "医药", "法政", "军事", "农事", "器用", "游艺", "天候", "禽兽", "草木", "形质",
    "物质", "天文", "地理", "乐律", "色采", "烹调", "纺织", "金工", "思辨", "礼俗",
]
CLASS_COUNT = len(CLASS_ZH)
MARK_COUNT = len(CLASS_MARKS)        # 20 个视觉标记，40 类各有一号（标记循环使用）

# ---------------------------------------------------------------- 家族纹（辨识度维度）
# 后加的**第四个视觉维度**：用四角的**预留格**（位9–位12）画一个「粗轮廓」。
# 为什么加：实测 3000 个词挤在 3 边框 × 20 标记 = 60 种骨架上，
# 同骨架内相差 ≤2 笔的近形词每词平均摊到 4.4 个，核心抽象词最难分。
# 边框与标记都已固定，唯一还能自由使用的就是这四个预留格。
FAMILY_COUNT = 8
FAMILY_ZH = ["空角", "点角", "双点角", "环角", "横角", "方角", "叉角", "角角"]
CORNER_CELLS = [9, 10, 11, 12]       # 字格四角的四个预留位


def _ornament(kind: str, x: float, y: float) -> str:
    """在某个预留格里画家族纹的一个部件。

    尺寸必须留在本格内（四角格是 54 见方的格子，格心距字形边框只有半格），
    否则会戳出框外、也会干扰旁边的数位笔画。
    """
    s = CELL * 0.16                 # 部件半径（约 8.6，留足余量）
    if kind == "dot":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{s*0.52:.1f}"/>'
    if kind == "ddot":
        return (f'<circle cx="{x-s*0.52:.1f}" cy="{y:.1f}" r="{s*0.40:.1f}"/>'
                f'<circle cx="{x+s*0.52:.1f}" cy="{y:.1f}" r="{s*0.40:.1f}"/>')
    if kind == "ring":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{s*0.78:.1f}" fill="none"/>'
    if kind == "bar":
        return (f'<line x1="{x-s*0.80:.1f}" y1="{y:.1f}" x2="{x+s*0.80:.1f}" y2="{y:.1f}" '
                f'stroke-width="2.6"/>')
    if kind == "sq":
        return (f'<rect x="{x-s*0.62:.1f}" y="{y-s*0.62:.1f}" width="{s*1.24:.1f}" '
                f'height="{s*1.24:.1f}" fill="none"/>')
    if kind == "x":
        return (f'<line x1="{x-s*0.60:.1f}" y1="{y-s*0.60:.1f}" '
                f'x2="{x+s*0.60:.1f}" y2="{y+s*0.60:.1f}"/>'
                f'<line x1="{x-s*0.60:.1f}" y1="{y+s*0.60:.1f}" '
                f'x2="{x+s*0.60:.1f}" y2="{y-s*0.60:.1f}"/>')
    if kind == "tri":
        return (f'<polygon points="{x},{y-s*0.68:.1f} {x-s*0.62:.1f},{y+s*0.40:.1f} '
                f'{x+s*0.62:.1f},{y+s*0.40:.1f}" fill="none"/>')
    return ""


FAMILY_ORNAMENT = ["", "dot", "ddot", "ring", "bar", "sq", "x", "tri"]


def family_elems(family: int) -> str:
    """家族纹：画在四角的预留格上（位9–位12）。"""
    kind = FAMILY_ORNAMENT[family % FAMILY_COUNT]
    if not kind:
        return ""
    out = []
    for p in CORNER_CELLS:
        gx, gy = POS[p]
        out.append(_ornament(kind, PAD_X + gx * CELL + CELL / 2,
                             PAD_Y + gy * CELL + CELL / 2))
    return "".join(out)


def cell_center(p: int) -> tuple[float, float]:
    gx, gy = POS[p]
    return PAD_X + gx * CELL + CELL / 2, PAD_Y + gy * CELL + CELL / 2


def digit_elems(value: int, pos: int, x: float, y: float) -> str:
    """把一个数字位的取值画成笔画。硬约束：笔画落在本格内。"""
    if value == 0:
        return ""
    double = pos in (1, 2)
    corner = pos in (1, 3, 4, 6)
    d = INK
    out = []
    if value == 1:                                   # 点
        if double:
            r = d * 0.19
            out.append(f'<circle cx="{x-d*0.30:.1f}" cy="{y:.1f}" r="{r:.1f}"/>')
            out.append(f'<circle cx="{x+d*0.30:.1f}" cy="{y:.1f}" r="{r:.1f}"/>')
        else:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{d*0.22:.1f}"/>')
    elif value == 2:                                 # 横（角位作斜）
        if corner:
            out.append(f'<line x1="{x-d*0.86:.1f}" y1="{y-d*0.55:.1f}" '
                       f'x2="{x+d*0.86:.1f}" y2="{y+d*0.55:.1f}"/>')
            if double:
                out.append(f'<line x1="{x-d*0.86:.1f}" y1="{y-d*0.05:.1f}" '
                           f'x2="{x+d*0.86:.1f}" y2="{y+d*1.05:.1f}"/>')
        else:
            out.append(f'<line x1="{x-d:.1f}" y1="{y:.1f}" '
                       f'x2="{x+d:.1f}" y2="{y:.1f}"/>')
            if double:
                out.append(f'<line x1="{x-d:.1f}" y1="{y-d*0.46:.1f}" '
                           f'x2="{x+d:.1f}" y2="{y-d*0.46:.1f}"/>')
    elif value == 3:                                 # 环
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{d*0.80:.1f}" fill="none"/>')
        if double:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{d*0.38:.1f}" fill="none"/>')
    return "".join(out)


def inner_elems(kind: str) -> str:
    """中央格的语义类标记（20 式），尺寸按格宽推导。"""
    u = CELL * 0.5
    o = []
    if kind == "dot":
        o.append(f'<circle cx="{CX}" cy="{CY}" r="{u*0.18:.1f}"/>')
    elif kind == "ddot":
        o.append(f'<circle cx="{CX-u*0.26:.1f}" cy="{CY}" r="{u*0.15:.1f}"/>')
        o.append(f'<circle cx="{CX+u*0.26:.1f}" cy="{CY}" r="{u*0.15:.1f}"/>')
    elif kind == "tdot":
        for dx, dy in ((0, -u*0.30), (-u*0.28, u*0.22), (u*0.28, u*0.22)):
            o.append(f'<circle cx="{CX+dx:.1f}" cy="{CY+dy:.1f}" r="{u*0.14:.1f}"/>')
    elif kind == "qdot":
        for dx, dy in ((-u*0.24, -u*0.24), (u*0.24, -u*0.24),
                       (-u*0.24, u*0.24), (u*0.24, u*0.24)):
            o.append(f'<circle cx="{CX+dx:.1f}" cy="{CY+dy:.1f}" r="{u*0.13:.1f}"/>')
    elif kind == "ring":
        o.append(f'<circle cx="{CX}" cy="{CY}" r="{u*0.40:.1f}" fill="none"/>')
    elif kind == "dring":
        o.append(f'<circle cx="{CX}" cy="{CY}" r="{u*0.48:.1f}" fill="none"/>')
        o.append(f'<circle cx="{CX}" cy="{CY}" r="{u*0.22:.1f}" fill="none"/>')
    elif kind == "pill":
        o.append(f'<rect x="{CX-u*0.50:.1f}" y="{CY-u*0.24:.1f}" width="{u:.1f}" '
                 f'height="{u*0.48:.1f}" rx="{u*0.24:.1f}" fill="none"/>')
    elif kind == "chev":
        o.append(f'<polyline points="{CX-u*0.46:.1f},{CY+u*0.24:.1f} {CX},'
                 f'{CY-u*0.30:.1f} {CX+u*0.46:.1f},{CY+u*0.24:.1f}" fill="none"/>')
    elif kind == "wye":
        for ax, ay in ((CX, CY-u*0.48), (CX-u*0.42, CY+u*0.28), (CX+u*0.42, CY+u*0.28)):
            o.append(f'<line x1="{CX}" y1="{CY}" x2="{ax:.1f}" y2="{ay:.1f}"/>')
    elif kind == "tri3":
        o.append(f'<polygon points="{CX},{CY-u*0.48:.1f} {CX-u*0.44:.1f},'
                 f'{CY+u*0.28:.1f} {CX+u*0.44:.1f},{CY+u*0.28:.1f}" fill="none"/>')
    elif kind == "bar":
        o.append(f'<line x1="{CX-u*0.52:.1f}" y1="{CY}" x2="{CX+u*0.52:.1f}" y2="{CY}" '
                 f'stroke-width="3.2"/>')
    elif kind == "xdot":
        o.append(f'<line x1="{CX-u*0.38:.1f}" y1="{CY-u*0.38:.1f}" x2="{CX+u*0.38:.1f}" '
                 f'y2="{CY+u*0.38:.1f}"/>')
        o.append(f'<line x1="{CX-u*0.38:.1f}" y1="{CY+u*0.38:.1f}" x2="{CX+u*0.38:.1f}" '
                 f'y2="{CY-u*0.38:.1f}"/>')
    elif kind == "ydot":
        o.append(f'<line x1="{CX-u*0.42:.1f}" y1="{CY-u*0.42:.1f}" x2="{CX}" '
                 f'y2="{CY+u*0.10:.1f}"/>')
        o.append(f'<line x1="{CX+u*0.42:.1f}" y1="{CY-u*0.42:.1f}" x2="{CX}" '
                 f'y2="{CY+u*0.10:.1f}"/>')
        o.append(f'<line x1="{CX}" y1="{CY+u*0.10:.1f}" x2="{CX}" y2="{CY+u*0.48:.1f}"/>')
    elif kind == "cdot":
        o.append(f'<path d="M {CX-u*0.50:.1f},{CY} a {u*0.25:.1f},{u*0.25:.1f} 0 0 1 '
                 f'{u*0.50:.1f},0 a {u*0.25:.1f},{u*0.25:.1f} 0 0 1 {u*0.50:.1f},0" fill="none"/>')
    elif kind == "odot":
        o.append(f'<circle cx="{CX}" cy="{CY}" r="{u*0.46:.1f}" fill="none"/>')
        o.append(f'<circle cx="{CX-u*0.23:.1f}" cy="{CY}" r="{u*0.11:.1f}"/>')
        o.append(f'<circle cx="{CX+u*0.23:.1f}" cy="{CY}" r="{u*0.11:.1f}"/>')
    elif kind == "udot":
        o.append(f'<path d="M {CX-u*0.42:.1f},{CY+u*0.30:.1f} a {u*0.42:.1f},{u*0.42:.1f} '
                 f'0 0 1 {u*0.84:.1f},0" fill="none"/>')
        o.append(f'<circle cx="{CX}" cy="{CY+u*0.30:.1f}" r="{u*0.15:.1f}"/>')
    elif kind == "tribar":
        for k in (-1, 0, 1):
            o.append(f'<line x1="{CX-u*0.48:.1f}" y1="{CY+k*u*0.26:.1f}" '
                     f'x2="{CX+u*0.48:.1f}" y2="{CY+k*u*0.26:.1f}"/>')
    elif kind == "trichev":
        for k, sc in ((0, 1.0), (1, 0.62)):
            dy = CY + (k - 0.5) * u * 0.55
            o.append(f'<polyline points="{CX-u*0.46*sc:.1f},{dy+u*0.16:.1f} {CX},'
                     f'{dy-u*0.20:.1f} {CX+u*0.46*sc:.1f},{dy+u*0.16:.1f}" fill="none"/>')
    elif kind == "diag":
        o.append(f'<line x1="{CX-u*0.44:.1f}" y1="{CY-u*0.34:.1f}" x2="{CX+u*0.18:.1f}" '
                 f'y2="{CY+u*0.16:.1f}"/>')
        o.append(f'<line x1="{CX-u*0.18:.1f}" y1="{CY-u*0.16:.1f}" x2="{CX+u*0.44:.1f}" '
                 f'y2="{CY+u*0.34:.1f}"/>')
    elif kind == "sqdot":
        o.append(f'<rect x="{CX-u*0.40:.1f}" y="{CY-u*0.40:.1f}" width="{u*0.80:.1f}" '
                 f'height="{u*0.80:.1f}" fill="none"/>')
        o.append(f'<circle cx="{CX}" cy="{CY}" r="{u*0.13:.1f}"/>')
    return "".join(o)


def border_elems(kind: str) -> str:
    x0, y0 = CX - HALF_W, CY - HALF_H
    x1, y1 = CX + HALF_W, CY + HALF_H
    if kind == "square":
        return (f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{GRID_W:.1f}" '
                f'height="{GRID_H:.1f}" rx="4" fill="none"/>')
    if kind == "circle":
        return f'<ellipse cx="{CX}" cy="{CY}" rx="{HALF_W:.1f}" ry="{HALF_H:.1f}" fill="none"/>'
    if kind == "diamond":
        return (f'<polygon points="{CX},{y0:.1f} {x1:.1f},{CY} {CX},{y1:.1f} '
                f'{x0:.1f},{CY}" fill="none"/>')
    raise ValueError(kind)


VOICE = {
    "体": None,
    "貌": ("top", "dot"),
    "用": ("bottom", "bar"),
    "度": ("right", "ddot"),
    "场": ("left", "bar"),
}


def voice_elems(voice: str) -> str:
    v = VOICE.get(voice)
    if not v:
        return ""
    where, _how = v
    lo, hi = MARGIN * 0.28, MARGIN * 0.90
    if where == "top":
        return f'<circle cx="{CX}" cy="{lo:.1f}" r="{MARGIN*0.20:.1f}"/>'
    if where == "bottom":
        return f'<line x1="{CX}" y1="{SIZE_H-MARGIN:.1f}" x2="{CX}" y2="{SIZE_H-lo:.1f}"/>'
    if where == "right":
        return (f'<circle cx="{SIZE_W-MARGIN*0.50:.1f}" cy="{CY-MARGIN*0.30:.1f}" '
                f'r="{MARGIN*0.19:.1f}"/>'
                f'<circle cx="{SIZE_W-MARGIN*0.50:.1f}" cy="{CY+MARGIN*0.30:.1f}" '
                f'r="{MARGIN*0.19:.1f}"/>')
    if where == "left":
        return f'<line x1="{lo:.1f}" y1="{CY}" x2="{hi:.1f}" y2="{CY}"/>'
    return ""


def glyph_svg(index: int, voice: str = "体", class_no: int | None = None,
              family: int = 0, box: bool = True, label: str | None = None,
              color: str = "#1b1b1f") -> str:
    """生成一个字形的 SVG 片段。

    index    = 字形编号 i（0..65535）：决定 8 个数位与边框校验纹 i mod 3
    class_no = 语义类号（决定中央格标记）；省略时取 i mod 20
    family   = 家族号（0..7，决定四角预留格上的**粗轮廓纹**）；默认 0 = 不画
    """
    ck = index % 3
    cls = (index % MARK_COUNT) if class_no is None else class_no
    parts = []
    if box:
        parts.append(f'<rect x="1" y="1" width="{SIZE_W-2}" height="{SIZE_H-2}" rx="7" '
                     f'fill="#fbfaf7" stroke="#d8d4cc"/>')
    body = []
    for p in USED:
        val = (index // WEIGHT[p]) % 4
        gx, gy = POS[p]
        body.append(digit_elems(val, p, PAD_X + gx * CELL + CELL / 2,
                                PAD_Y + gy * CELL + CELL / 2))
    stroke = (f'fill="{color}" stroke="{color}" stroke-width="2.2" stroke-linecap="round"')
    parts.append(f'<g {stroke}>{"".join(body)}</g>')
    parts.append(f'<g {stroke}>{border_elems(BORDER_BY_CHECK[ck])}</g>')
    parts.append(f'<g {stroke}>{inner_elems(CLASS_MARKS[cls % MARK_COUNT])}</g>')
    fe = family_elems(family)
    if fe:
        # 只覆盖 stroke-width，不重复写其它属性（重复属性会让 SVG 解析中断）
        parts.append(f'<g stroke-width="1.7">{fe}</g>')
    vm = voice_elems(voice)
    if vm:
        parts.append(f'<g {stroke}>{vm}</g>')
    if label:
        parts.append(f'<text x="{SIZE_W/2}" y="{SIZE_H-2}" text-anchor="middle" '
                     f'font-family="ui-sans-serif,sans-serif" font-size="12" '
                     f'fill="#8a857c">{label}</text>')
    return "".join(parts)


def svg_doc(inner: str, w: int, h: int, bg: str = "#ffffff") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}"><rect width="{w}" height="{h}" fill="{bg}"/>'
            f'{inner}</svg>')


def write_chart(items, out: Path, cols: int = 16, title: str = "", subtitle: str = ""):
    """字表：items 为 (index, label, class_no[, family]) 元组序列。"""
    norm = []
    for it in items:
        if len(it) >= 4:
            norm.append((it[0], it[1], it[2], it[3]))
        elif len(it) == 3:
            norm.append((it[0], it[1], it[2], 0))
        else:
            norm.append((it[0], it[1], it[0] % MARK_COUNT, 0))
    n = len(norm)
    rows = (n + cols - 1) // cols
    top = 74 if title else 6
    cw, ch = SIZE_W + 6, SIZE_H + 22
    inner = []
    if title:
        inner.append(f'<text x="18" y="34" font-family="ui-sans-serif,sans-serif" '
                     f'font-size="25" font-weight="600" fill="#1b1b1f">{title}</text>')
        inner.append(f'<text x="18" y="58" font-family="ui-sans-serif,sans-serif" '
                     f'font-size="14" fill="#7d786f">{subtitle}</text>')
    for k, (idx, lab, cls, fam) in enumerate(norm):
        r, c = divmod(k, cols)
        inner.append(f'<g transform="translate({c*cw+3},{r*ch+top})">'
                     f'{glyph_svg(idx, class_no=cls, family=fam, label=lab)}</g>')
    out.write_text(svg_doc("".join(inner), cols * cw + 6, rows * ch + top + 10),
                   encoding="utf-8")
    return out


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    out = here / "glyph_preview.svg"
    write_chart([(i, str(i), i % MARK_COUNT) for i in range(24)], out, cols=6,
                title="洄文 · 字形预览",
                subtitle=f"字形空间 4^{len(USED)} = {GLYPH_SPACE}｜边框 = 编号 mod 3")
    print("wrote", out, f"| 字形空间 {GLYPH_SPACE} | 语义类 {CLASS_COUNT} | 标记 {MARK_COUNT}")
