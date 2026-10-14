#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 全书字数统计

「字数」按**中文字符**计（CJK 统一汉字），不含标点、拉丁字母、数字与空白。
这是出版口径的字数，也是本项目的验收口径。

用法：
    python tools/hwcount.py                 # 统计 dict/ 下全部文件
    python tools/hwcount.py 文件或目录 ...
    python tools/hwcount.py --per-entry     # 按条目（### 开头）细分
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DICT = ROOT / "dict"

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
ENTRY = re.compile(r"^###\s", re.M)


def count_text(t: str) -> int:
    return len(CJK.findall(t))


def files_of(args: list[str]) -> list[Path]:
    if not args:
        return sorted(p for p in DICT.rglob("*.md"))
    out: list[Path] = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            out += sorted(p.rglob("*.md"))
        elif p.exists():
            out.append(p)
    return out


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    per_entry = "--per-entry" in sys.argv
    fs = files_of(args)
    if not fs:
        print("没有找到文件")
        return 1

    total = 0
    rows = []
    for f in fs:
        t = f.read_text(encoding="utf-8")
        n = count_text(t)
        ents = len(ENTRY.findall(t))
        rows.append((f, n, ents))
        total += n

    def label(f: Path) -> str:
        try:
            return str(f.resolve().relative_to(ROOT))
        except ValueError:
            return str(f)

    width = max(len(label(f)) for f, _, _ in rows)
    for f, n, ents in rows:
        rel = label(f)
        avg = f"　均 {n // ents} 字/条" if ents else ""
        print(f"{rel:<{width}}  {n:>8} 字　{ents:>5} 条{avg}")
    print("─" * (width + 30))
    print(f"{'合计':<{width}}  {total:>8} 字　{sum(e for _, _, e in rows):>5} 条")
    print(f"目标 700000 字　达成 {total / 700000 * 100:.1f}%　"
          f"尚差 {max(0, 700000 - total)} 字")

    if per_entry:
        print("\n条目字数分布：")
        for f in fs:
            t = f.read_text(encoding="utf-8")
            blocks = re.split(r"^###\s", t, flags=re.M)[1:]
            if not blocks:
                continue
            nums = sorted(count_text(b) for b in blocks)
            print(f"  {f.name}: 最短 {nums[0]}　中位 {nums[len(nums)//2]}　最长 {nums[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
