#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成洄文字表（15000 字形，分页）与人读词典。

字表分页：每页 PAGE 字（默认 120 = 10 列 × 12 行），页内可读可打印。
"""
from __future__ import annotations

from pathlib import Path

import hwcharset as C
import hwglyph as G

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAGE = 120
COLS = 10


def load_chars() -> list[dict]:
    lines = (ROOT / "characters.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]


def main() -> None:
    chars = load_chars()
    n = len(chars)
    pages = (n + PAGE - 1) // PAGE
    chart_dir = ROOT / "charts"
    chart_dir.mkdir(exist_ok=True)
    for p in range(pages):
        chunk = chars[p * PAGE:(p + 1) * PAGE]
        items = [(int(c["glyph"]), c["label"], int(c["class_no"]),
                  int(c.get("family", 0) or 0)) for c in chunk]
        G.write_chart(
            items, chart_dir / f"page-{p+1:03d}.svg", cols=COLS,
            title=f"洄文 · 字表　第 {p+1} / {pages} 页",
            subtitle=f"字形编号 {chunk[0]['glyph']}–{chunk[-1]['glyph']}　"
                     f"数位(编号) + 边框(=编号 mod 3，校验) + 中央格(语义类) "
                     f"+ 四角纹(家族，{G.FAMILY_COUNT} 式，用于分开近形字)　"
                     f"〔未指派〕= 已成形待用的备用字")

    # 每类一张小字表（已定义字）
    cls_dir = chart_dir / "class"
    cls_dir.mkdir(exist_ok=True)
    byc: dict[int, list[dict]] = {}
    for c in chars:
        if c["status"] == "defined":
            byc.setdefault(int(c["class_no"]), []).append(c)
    for cls, rows in sorted(byc.items()):
        name = rows[0]["class_zh"]
        items = [(int(r["glyph"]), r["label"], int(r["class_no"]),
                  int(r.get("family", 0) or 0)) for r in rows]
        G.write_chart(items, cls_dir / f"{cls:02d}-{name}.svg", cols=8,
                      title=f"洄文 · {name}类（{len(rows)} 字）",
                      subtitle="同类共享中央格标记；编号决定数位与边框；四角纹是家族（用于分开近形字）")
    print(f"字表：{pages} 页（每页 {PAGE} 字）→ charts/page-*.svg")
    print(f"分类字表：{len(byc)} 张 → charts/class/*.svg")
    print(f"共 {n} 字：已定义 {sum(1 for c in chars if c['status']=='defined')}"
          f"｜备用 {sum(1 for c in chars if c['status']=='reserved')}")


if __name__ == "__main__":
    main()
