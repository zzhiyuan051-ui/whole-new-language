#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计洄文大字典.md 里实际用到的 Markdown 构造。

先测量再写转换器：如果只按想象的语法写，漏掉一种构造就是几万处错误留在成书里。
"""
from __future__ import annotations

import collections
import re
from pathlib import Path

DICT = Path(__file__).resolve().parent.parent / "dict"
MD = DICT / "洄文大字典.md"


def main() -> int:
    lines = MD.read_text(encoding="utf-8").splitlines()
    print(f"总行数 {len(lines):,}\n")

    counts: collections.Counter[str] = collections.Counter()
    samples: dict[str, list[str]] = collections.defaultdict(list)

    in_fence = False
    for ln in lines:
        s = ln.rstrip()
        if s.startswith("```"):
            counts["围栏代码块标记"] += 1
            in_fence = not in_fence
            continue
        if in_fence:
            counts["代码块内容行"] += 1
            continue

        if re.match(r"^# ", s):
            counts["# 一级标题"] += 1
        elif re.match(r"^## ", s):
            counts["## 二级标题"] += 1
        elif re.match(r"^### ", s):
            counts["### 三级标题"] += 1
        elif re.match(r"^#### ", s):
            counts["#### 四级标题"] += 1

        if s.startswith("|"):
            counts["表格行"] += 1
            if re.match(r"^\|[\s:\-|]+\|$", s):
                counts["  其中：表格分隔行"] += 1
        if s.startswith("> "):
            counts["引用行 >"] += 1
        if re.match(r"^\s*[-*+] ", s):
            counts["无序列表"] += 1
        if re.match(r"^\s*\d+[.、)] ", s):
            counts["有序列表"] += 1
        if s in ("---", "***", "___"):
            counts["水平分隔线"] += 1

        for name, pat in (("**粗体**", r"\*\*[^*\n]+\*\*"),
                          ("*斜体*", r"(?<!\*)\*(?!\*)[^*\n]+\*(?!\*)")):
            n = len(re.findall(pat, s))
            if n:
                counts[name] += n
                if len(samples[name]) < 3:
                    samples[name].append(s[:100])

        if re.search(r"`[^`\n]+`", s):
            counts["行内代码 `x`"] += len(re.findall(r"`([^`\n]+)`", s))
            if len(samples["行内代码 `x`"]) < 3:
                samples["行内代码 `x`"].append(s[:100])
        if re.search(r"\[[^\]]+\]\([^)]+\)", s):
            counts["链接 [x](y)"] += len(re.findall(r"\[[^\]]+\]\([^)]+\)", s))
        if re.search(r"!\[", s):
            counts["图片 ![x](y)"] += 1
        if re.match(r"^\s*\|?\s*:?-{3,}", s) or re.match(r"^ {0,3}([-*_])\s*(\1\s*){2,}$", s):
            pass

    width = max(len(k) for k in counts)
    print("=== 实际出现的构造 ===")
    for k, v in counts.most_common():
        print(f"  {k:<{width}}  {v:>9,}")

    print("\n=== 样例 ===")
    for k, v in samples.items():
        print(f"  {k}:")
        for x in v:
            print(f"      {x}")

    # 表格规模
    tbl_lines = [l for l in lines if l.startswith("|")]
    print(f"\n表格行合计 {len(tbl_lines):,}")
    blocks = 0
    prev = False
    for l in lines:
        cur = l.startswith("|")
        if cur and not prev:
            blocks += 1
        prev = cur
    print(f"表格块数约 {blocks:,}，平均每块 {len(tbl_lines)/max(blocks,1):.1f} 行")

    # 字体/Unicode 情况
    text = MD.read_text(encoding="utf-8")
    han = len(re.findall(r"[\u4e00-\u9fff]", text))
    pua = len(re.findall(r"[\ue000-\uf8ff]", text))
    print(f"\n汉字 {han:,}   私用区字符 {pua:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
