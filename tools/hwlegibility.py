#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 字形辨识度实测

问题：字形只由 3 种边框 × 20 种中央标记 = 60 种骨架，
再加 8 个数位（每位 0/1/2/3，对应空/点/横/环）。
若两个词在**同一个骨架上**、且只在少数几个位上不同，人眼就难分。

本工具量化三件事：
  1. 同骨架的词有多少（每个骨架平均挤几个词）
  2. 每对词之间的「笔画距离」（有多少个位的取值不同、以及笔画数之差）
  3. 距离 ≤2 与 ≤3 的近形词，每个词平均摊到几个
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import hwglyph as G

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
USED = G.USED


def load() -> list[dict]:
    lines = (ROOT / "lexicon.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]


def digits(i: int) -> tuple[int, ...]:
    return tuple((i // G.WEIGHT[p]) % 4 for p in USED)


def skeleton(i: int, cls: int) -> tuple[int, int]:
    return (i % 3, cls % G.MARK_COUNT)


def dist(a: tuple[int, ...], b: tuple[int, ...]) -> tuple[int, int]:
    """返回（几个位的取值不同, 笔画数之差）"""
    diff = sum(1 for x, y in zip(a, b) if x != y)
    strokes = abs(sum(1 for x in a if x) - sum(1 for x in b if x))
    return diff, strokes


def main() -> None:
    rows = load()
    fam = {}
    fam_tsv = ROOT / "characters.tsv"
    if fam_tsv.exists():
        ls = fam_tsv.read_text(encoding="utf-8").splitlines()
        hd = ls[0].split("\t")
        for l in ls[1:]:
            d = dict(zip(hd, l.split("\t")))
            if d.get("status") == "defined":
                fam[int(d["glyph"])] = int(d["family"])
    glyphs = [(int(r["glyph"]), int(r["class_no"]), r["zh"], r["form"]) for r in rows]

    # 1) 骨架分布
    by_sk: dict[tuple[int, int], list] = defaultdict(list)
    for g in glyphs:
        by_sk[skeleton(g[0], g[1])].append(g)
    sizes = [len(v) for v in by_sk.values()]
    print(f"词数 {len(glyphs)}｜实际用到的骨架 {len(by_sk)} 种"
          f"（边框 3 × 标记 {G.MARK_COUNT} = {3 * G.MARK_COUNT}）")
    print(f"每个骨架挤的词：最多 {max(sizes)}｜平均 {sum(sizes) / len(sizes):.1f}")
    if fam:
        print(f"家族纹 {G.FAMILY_COUNT} 式｜加入后「骨架 × 家族」"
              f"＝ {3 * G.MARK_COUNT * G.FAMILY_COUNT} 种可辨外形")

    # 2) 近形统计：分「同骨架全部比」与「同骨架且同家族」两档
    def scan(same_family_only: bool) -> tuple[int, int]:
        p2 = p3 = 0
        no2: Counter[str] = Counter()
        for sk, grp in by_sk.items():
            if len(grp) < 2:
                continue
            ds = {g[0]: digits(g[0]) for g in grp}
            for a, b in combinations(grp, 2):
                if same_family_only and fam and fam.get(a[0]) != fam.get(b[0]):
                    continue          # 家族不同 → 四角纹一眼可分，不算近形
                d, s = dist(ds[a[0]], ds[b[0]])
                if d <= 2 and s <= 2:
                    p2 += 1
                    no2[a[2]] += 1
                    no2[b[2]] += 1
                if d <= 3 and s <= 3:
                    p3 += 1
        return p2, p3

    n = len(glyphs)
    p2a, p3a = scan(False)
    print()
    print("【修复前】同骨架内两两相比（不看家族纹）")
    print(f"  相差 ≤2：{p2a} 对 → 每词平均摊到 {2 * p2a / n:.1f} 个")
    print(f"  相差 ≤3：{p3a} 对 → 每词平均摊到 {2 * p3a / n:.1f} 个")
    if fam:
        p2b, p3b = scan(True)
        print()
        print("【修复后】只有**同骨架且同家族**才算近形（四角纹相同的才会混）")
        print(f"  相差 ≤2：{p2b} 对 → 每词平均摊到 {2 * p2b / n:.1f} 个"
              f"　（降至 {2 * p2b / max(p2a, 1) * 100:.0f}%）")
        print(f"  相差 ≤3：{p3b} 对 → 每词平均摊到 {2 * p3b / n:.1f} 个"
              f"　（降至 {2 * p3b / max(p3a, 1) * 100:.0f}%）")

    # 核心抽象词单独看
    focus = ["现实", "果", "同", "真", "必然", "状态", "实体", "本质"]
    print()
    print("核心抽象词（用户点名的那几个）：")
    print("  词　　字形　　边框 标记 家族　数位")
    for r in glyphs:
        if r[2] in focus:
            d = digits(r[0])
            print(f"  {r[2]:<4} {r[0]:>5}　  {r[0] % 3}　  {r[1] % G.MARK_COUNT:>2}　 "
                  f"{fam.get(r[0], 0)}　 {''.join(map(str, d))}")


if __name__ == "__main__":
    sys.exit(main())
