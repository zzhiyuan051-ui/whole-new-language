#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 词表查重与修补提案（只报告，不改文件）

对每个草稿 tsV 逐场 + 跨场检查 中文词/英文词 重复，并打印行号与同场的邻居，
便于精准替换而不是盲改。
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import syllabary as S

HERE = Path(__file__).resolve().parent
DRAFTS = HERE / "drafts"


def main() -> None:
    rows = []          # (domain, lineno, syll, zh, en, pos, dz)
    for i, did in enumerate(S.DOMAIN_ORDER, 1):
        p = DRAFTS / f"domain_{i:02d}_{did}.tsv"
        if not p.exists():
            print(f"[缺] {did}")
            continue
        for ln, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            f = line.split("\t")
            if len(f) == 6:
                rows.append((did, ln, f[0], f[1], f[2], f[3], f[4]))

    by_zh, by_en = defaultdict(list), defaultdict(list)
    for r in rows:
        by_zh[r[3]].append(r)
        by_en[r[4].lower()].append(r)

    print(f"总条目 {len(rows)}")
    for name, d in (("中文词重复", by_zh), ("英文词重复", by_en)):
        dups = {k: v for k, v in d.items() if len(v) > 1}
        print(f"\n=== {name}：{len(dups)} 组 ===")
        for k, v in sorted(dups.items()):
            print(f"  {k!r}")
            for did, ln, syll, zh, en, pos, dz in v:
                where = "同场" if len({x[0] for x in v}) == 1 else "跨场"
                print(f"     [{where}] {did} 行{ln:>2}  {syll:<5} {zh:<6} ({pos})  {dz}")

    # 词性分布，便于核对
    poscount = defaultdict(int)
    for r in rows:
        poscount[r[5]] += 1
    print("\n词性分布:", dict(sorted(poscount.items())))
    print("各场条数:", {d: sum(1 for r in rows if r[0] == d) for d in S.DOMAIN_ORDER})


if __name__ == "__main__":
    sys.exit(main())
