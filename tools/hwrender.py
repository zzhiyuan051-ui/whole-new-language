#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 图解渲染器：把关系图铺到纸面上（spec/01-script.md §7 的实现）

洄文的正体不是线性行文，而是「关系在纸面上的空间布置」。本文件把 hwlang 解析出的
关系图渲染成 SVG：
  · 结 = 圆角框，内含 字形（hwglyph 生成） + 音节 + 汉字
  · 临弓（填槽）= 实线箭，箭尾落在填槽的那个结上，线上标临位
  · 饰弓（限定）= 虚线箭，方向相反（修饰语 → 被修饰者）
  · 结际弓（子图之间）= 加粗双色线，标 先/后/因/若/虽/目的/于是
  · 模态圈 = 整图外框；义标 = 右上角印记
"""
from __future__ import annotations

from pathlib import Path

import hwglyph as G

FONT = "ui-sans-serif,-apple-system,'Segoe UI','Microsoft YaHei',sans-serif"
COL = {
    "lin": "#2f6fd0", "shi": "#2f9e6a", "jie": "#b4552d",
    "node": "#fbfaf7", "nstroke": "#c9c3b8", "ink": "#1b1b1f", "dim": "#8a857c",
}
NODE_W, NODE_H, GAP_X, GAP_Y = 150, 168, 74, 96
PAD = 46


def _layout(g, lex, order=None) -> dict[str, tuple[float, float]]:
    """按「有向深度」分层：根结在第 0 层，被临弓指向的结在下一层。

    order 显式指定要摆哪些结（渲染子图时必须给，否则会把它外部的结也摆进来）。
    """
    ids = list(g.order if order is None else order)
    depth = {nid: 0 for nid in ids}
    for _ in range(len(ids) + 2):
        changed = False
        for r in g.rels:
            if r.kind in ("lin", "shi") and r.src in depth and r.dst in depth:
                if depth[r.dst] < depth[r.src] + 1:
                    depth[r.dst] = depth[r.src] + 1
                    changed = True
        if not changed:
            break
    layers: dict[int, list[str]] = {}
    for nid in ids:
        layers.setdefault(depth[nid], []).append(nid)
    pos: dict[str, tuple[float, float]] = {}
    for d, layer in sorted(layers.items()):
        for k, nid in enumerate(layer):
            pos[nid] = (PAD + k * (NODE_W + GAP_X), PAD + d * (NODE_H + GAP_Y))
    return pos


def _arrow(x1, y1, x2, y2, color, dash="", width=2.4, shrink=6):
    import math
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    x2, y2 = x2 - ux * shrink, y2 - uy * shrink
    hx, hy = x2 - ux * 13, y2 - uy * 13
    px, py = -uy * 6.5, ux * 6.5
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{hx:.1f}" y2="{hy:.1f}" '
            f'stroke="{color}" stroke-width="{width}"{d} stroke-linecap="round"/>'
            f'<polygon points="{x2:.1f},{y2:.1f} {hx+px:.1f},{hy+py:.1f} '
            f'{hx-px:.1f},{hy-py:.1f}" fill="{color}"/>')


def _corner(a, b, w, h):
    """结的边界交点（用于从框边出发画线）。"""
    cx, cy = a[0] + w / 2, a[1] + h / 2
    tx, ty = b[0] + w / 2, b[1] + h / 2
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = (w / 2) / abs(dx) if dx else 1e9
    sy = (h / 2) / abs(dy) if dy else 1e9
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def _node_svg(n, x, y, lex=None) -> str:
    idx = n.index if n.index is not None else 0
    rec = (lex or {}).get(n.root)
    cls = int(rec["class_no"]) if rec else 0
    body = []
    body.append(f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="12" '
                f'fill="{COL["node"]}" stroke="{COL["nstroke"]}" stroke-width="1.6"/>')
    # 字形按可用空间等比缩放，保证不越出结点框
    avail = min(NODE_W - 30, NODE_H - 74)
    scale = avail / G.SIZE
    gw = G.SIZE * scale
    gx = x + (NODE_W - gw) / 2
    gy = y + 14
    voice = n.voice if n.voice in G.VOICE else "体"
    face = int(rec["family"]) if rec and str(rec.get("family", "")).strip() else 0
    glyph = G.glyph_svg(idx, voice=voice, class_no=cls, family=face, box=False)
    body.append(f'<g transform="translate({gx:.1f},{gy:.1f}) scale({scale:.4f})">'
                f'{glyph}</g>')
    lab = f'{n.syll or n.root}'
    body.append(f'<text x="{x+NODE_W/2:.1f}" y="{y+NODE_H-38}" text-anchor="middle" '
                f'font-family="{FONT}" font-size="17" font-weight="600" '
                f'fill="{COL["ink"]}">{lab}</text>')
    body.append(f'<text x="{x+NODE_W/2:.1f}" y="{y+NODE_H-16}" text-anchor="middle" '
                f'font-family="{FONT}" font-size="14" fill="{COL["ink"]}">'
                f'{n.zh or n.root}{"·" + n.voice if n.voice != "体" else ""}</text>')
    if n.is_ref:
        body.append(f'<text x="{x+NODE_W-10}" y="{y+18}" text-anchor="end" '
                    f'font-family="{FONT}" font-size="12" fill="{COL["shi"]}">回指</text>')
    return "".join(body)


def _cluster_svg(sub, x, y, lex) -> tuple[str, float, float]:
    """把一张子图画成一个嵌套框（「一张图当端点」的直观表示）。"""
    pos = _layout(sub, lex, order=sub.order)
    w = max((p[0] for p in pos.values()), default=0) + NODE_W
    h = max((p[1] for p in pos.values()), default=0) + NODE_H
    pad = 18
    body = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{w+pad*2:.1f}" height="{h+pad*2+14:.1f}" '
            f'rx="16" fill="none" stroke="{COL["jie"]}" stroke-width="2" '
            f'stroke-dasharray="8 5"/>',
            f'<text x="{x+pad:.1f}" y="{y+17:.1f}" font-family="{FONT}" font-size="12" '
            f'fill="{COL["jie"]}">子图（整体当端点）</text>']
    inner, _w, _h = render(sub, lex, nested=True)
    body.append(f'<g transform="translate({x+pad:.1f},{y+pad+14:.1f})">{inner}</g>')
    return "".join(body), w + pad * 2, h + pad * 2 + 14


def render(g, lex, title: str = "", nested: bool = False) -> tuple[str, int, int]:
    view = g.flat(keep_inner=True) if not nested else g
    ids = g.order if nested else view.order
    pos = _layout(view, lex, order=ids)
    subs = []
    if not nested:
        for r in view.rels:
            for sub in (r.src_sub, r.dst_sub):
                if sub is not None and sub not in subs:
                    subs.append(sub)
    maxx = max((pos[i][0] for i in ids if i in pos), default=0) + NODE_W + PAD
    maxy = max((pos[i][1] for i in ids if i in pos), default=0) + NODE_H + PAD + 34
    W, H = int(maxx), int(maxy)
    out = []
    if g.modal and not nested:
        out.append(f'<rect x="12" y="{34}" width="{W-24}" height="{H-46}" rx="18" '
                   f'fill="none" stroke="#c9a227" stroke-width="2.6" stroke-dasharray="9 6"/>')
    for r in view.rels:
        if r.src is None or r.dst is None or r.src not in pos or r.dst not in pos:
            continue
        a, b = pos[r.src], pos[r.dst]
        shrink = 8
        if r.kind == "lin":
            p1 = _corner(a, b, NODE_W, NODE_H)
            p2 = _corner(b, a, NODE_W, NODE_H)
            out.append(_arrow(p1[0], p1[1], p2[0], p2[1], COL["lin"], shrink=shrink))
            mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
            out.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="13" fill="#ffffff" '
                       f'stroke="{COL["lin"]}" stroke-width="1.4"/>'
                       f'<text x="{mx:.1f}" y="{my+5:.1f}" text-anchor="middle" '
                       f'font-family="{FONT}" font-size="14" fill="{COL["lin"]}">{r.role}</text>')
        elif r.kind == "shi":
            p1 = _corner(a, b, NODE_W, NODE_H)
            p2 = _corner(b, a, NODE_W, NODE_H)
            out.append(_arrow(p1[0], p1[1], p2[0], p2[1], COL["shi"], dash="7 5",
                              width=2.0, shrink=shrink))
            mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
            out.append(f'<text x="{mx:.1f}" y="{my-8:.1f}" text-anchor="middle" '
                       f'font-family="{FONT}" font-size="13" fill="{COL["shi"]}">饰</text>')
        else:
            p1 = _corner(a, b, NODE_W, NODE_H)
            p2 = _corner(b, a, NODE_W, NODE_H)
            out.append(_arrow(p1[0], p1[1], p2[0], p2[1], COL["jie"], width=3.4,
                              shrink=shrink))
            mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
            out.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="15" fill="#ffffff" '
                       f'stroke="{COL["jie"]}" stroke-width="1.6"/>'
                       f'<text x="{mx:.1f}" y="{my+5:.1f}" text-anchor="middle" '
                       f'font-family="{FONT}" font-size="13" fill="{COL["jie"]}">{r.mark}</text>')
    for nid in view.order:
        n = view.nodes[nid]
        x, y = pos[nid]
        out.append(_node_svg(n, x, y, lex))
    # 子图：画成嵌套框，摆在主图下方（「一张图当端点」的直观表示）
    cy = maxy + 8
    for sub in subs:
        block, _bw, bh = _cluster_svg(sub, PAD, cy, lex)
        out.append(block)
        cy += bh + 16
    H = int(cy + 8)
    if not nested:
        head = title or g.title or ""
        if head:
            out.append(f'<text x="{PAD}" y="24" font-family="{FONT}" font-size="16" '
                       f'fill="{COL["dim"]}">{head}</text>')
        tags = []
        if g.modal:
            tags.append(f'模态 {g.modal}')
        if g.evidence:
            tags.append(f'义标 {g.evidence}')
        if tags:
            out.append(f'<text x="{W-PAD}" y="24" text-anchor="end" font-family="{FONT}" '
                       f'font-size="15" fill="{COL["jie"]}">{"　".join(tags)}</text>')
    return "".join(out), W, H


def document(graphs, lex, title: str = "", subtitle: str = "") -> str:
    """把多张图竖排成一份文档。"""
    parts, W, y = [], 0, 92 if title else 24
    if title:
        parts.append(f'<text x="34" y="42" font-family="{FONT}" font-size="26" '
                     f'font-weight="600" fill="{COL["ink"]}">{title}</text>')
        parts.append(f'<text x="34" y="68" font-family="{FONT}" font-size="14" '
                     f'fill="{COL["dim"]}">{subtitle}</text>')
    for g in graphs:
        body, w, h = render(g, lex)
        parts.append(f'<g transform="translate(24,{y})">{body}</g>')
        W = max(W, w + 48)
        y += h + 40
    return G.svg_doc("".join(parts), W, y + 24, bg="#ffffff")


def main():
    import argparse
    import hwlang as L
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="把 .hw 关系图渲染成 SVG")
    ap.add_argument("src")
    ap.add_argument("-o", "--out")
    ap.add_argument("--title", default="")
    ap.add_argument("--subtitle", default="")
    a = ap.parse_args()
    src = Path(a.src)
    text = src.read_text(encoding="utf-8")
    lex = L.load_lexicon(here.parent / "lexicon.tsv")
    graphs = L.parse_document(text)
    out = Path(a.out) if a.out else src.with_suffix(".svg")
    problems = 0
    for gi, g in enumerate(graphs, 1):
        L.attach(g, lex)
        L.fill_roles(g, lex)
        errs = L.validate(g, lex)
        head = f"{src.name} · 第 {gi} 图" + (f"「{g.title}」" if g.title else "")
        print(f"[{head}] 结 {len(g.nodes)}｜弓 {len(g.rels)}｜"
              f"{'校验通过' if not errs else str(len(errs)) + ' 项问题'}")
        for e in errs:
            print("   -", e)
        problems += len(errs)
    out.write_text(document(graphs, lex, a.title or src.stem, a.subtitle),
                   encoding="utf-8")
    print(f"→ {out}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
