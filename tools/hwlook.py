#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 词典查询（按音节 / 中文 / 英文 / 编号 / 类）"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEX = HERE.parent / "lexicon.tsv"


def load(path=LEX) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]


def show(r: dict) -> str:
    slots = r["slots"] if r["slots"] != "—" else "无槽（虚词）"
    return (f"  {r['syll']:<5} {r['spell']:<6} {r['zh']:<7} {r['en']:<18} "
            f"{r['pos']:<4} 类{r['class_no']:>2}{r['class_zh']:<3} "
            f"i={r['index']:<3} 槽={slots:<4} 声={r['voice']}   {r['def_zh']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="洄文词典查询")
    ap.add_argument("query", nargs="*", help="音节 / 中文 / 英文 / 编号")
    ap.add_argument("-c", "--class", dest="cls", help="按语义类过滤（类名或类号）")
    ap.add_argument("-n", "--limit", type=int, default=40, help="最多显示条数")
    ap.add_argument("--stats", action="store_true", help="词表统计")
    a = ap.parse_args()

    rows = load()
    if a.stats:
        from collections import Counter
        c = Counter(r["class_zh"] for r in rows)
        p = Counter(r["pos"] for r in rows)
        print(f"总条目 {len(rows)}｜音节 {len({r['syll'] for r in rows})}")
        print("按语义类：", "  ".join(f"{k}{v}" for k, v in c.most_common()))
        print("按词性：", dict(p))
        print("有槽位的词根：", sum(1 for r in rows if r["slots"] != "—"))
        return 0

    hits = rows
    if a.cls:
        hits = [r for r in hits if a.cls in (r["class_zh"], str(r["class_no"]))]
    if a.query:
        out = []
        for r in hits:
            if any(q in (r["syll"], r["zh"], r["en"], r["id"], str(r["index"]))
                   or q.lower() in r["en"].lower() or q in r["def_zh"]
                   or q in r["def_en"].lower() for q in a.query):
                out.append(r)
        hits = out
    print(f"命中 {len(hits)} 条")
    for r in hits[:a.limit]:
        print(show(r))
    if len(hits) > a.limit:
        print(f"  …（还有 {len(hits)-a.limit} 条，用 -n 调整）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
