#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从词表生成 TS​F 输入法用的 C++ 数据表（hwdata.h）。

DLL 不读外部文件，词表直接编进二进制 —— 这样部署只有一个 dll，不会「找不到词表」。
3000 条记录按「归一化后的音节（无声调）」排序，匹配时二分/前缀扫描。
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tsf" / "hwdata.h"
OUT.parent.mkdir(exist_ok=True)


def norm(s: str) -> str:
    """去空格、去声调数字 —— 与 Python 引擎 engine.IME.norm 必须保持一致。"""
    return re.sub(r"[^a-z]", "", s.lower())


def cstr(s: str) -> str:
    """把字符串写成 C++ 宽字符串字面量（用 \\u 转义，避免源文件编码问题）。"""
    return "".join(f"\\u{ord(c):04x}" for c in s)


def main() -> None:
    rows = []
    with (ROOT / "lexicon.tsv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            rows.append(r)

    rows.sort(key=lambda r: (norm(r["syll"]), len(r["syll"]), r["syll"]))

    lines = [
        "// 本文件由 tools/hwmake_tsf_data.py 自动生成，请勿手改。",
        "// 词表编进二进制，DLL 不依赖外部数据文件。",
        "#pragma once",
        "",
        "struct HwEntry {",
        "    const wchar_t* key;   // 归一化音节（无声调，用于匹配）",
        "    const wchar_t* form;  // 词形（含声调，显示用）",
        "    const wchar_t* zh;    // 汉字",
        "    unsigned int   cp;    // 码位（私用区）",
        "};",
        "",
        f"static const int HW_ENTRY_COUNT = {len(rows)};",
        "",
        "static const HwEntry HW_ENTRIES[] = {",
    ]
    for r in rows:
        lines.append(
            f'    {{ L"{norm(r["syll"])}", L"{cstr(r["form"])}", '
            f'L"{cstr(r["zh"])}", 0x{int(r["codepoint"]):04X} }},')
    lines.append("};")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    kb = OUT.stat().st_size // 1024
    keys = {norm(r["syll"]) for r in rows}
    print(f"→ {OUT}（{kb} KB，{len(rows)} 条，{len(keys)} 个不同输入键）")
    # 抽查
    for k in ("za", "yydi", "ni", "wo"):
        hits = [r for r in rows if norm(r["syll"]) == k]
        print(f"   {k:<6} 精确匹配 {len(hits)} 条" +
              (f"：{'、'.join(h['zh'] for h in hits[:4])}" if hits else ""))


if __name__ == "__main__":
    main()
