#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文字符集现状审计 —— 为「向外部机构提案」提供硬数据。

做三件事，全部只读、可复算：
  1. 直接解析 font/GalHuiwen.ttf 的 cmap，看**字体真的编码了哪些码位**
     （不信任任何中间 CSV —— 提案里说错码位是致命错误）。
  2. 把码位按 Unicode 区块归类，算出「私用区占用率」与「撞别人地盘」的风险。
  3. 对照 characters.tsv / lexicon.tsv，核对已定义/备用字与词表规模。

输出：
  out/char_audit.json   机器可读（后续生成提案、码表都从这里取数）
  out/char_audit.md     人读报告

用法：
  python tools/char_audit.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("需要 fontTools：python -m pip install fonttools")

HERE = Path(__file__).resolve().parent          # huiwen/tools
ROOT = HERE.parent                              # huiwen
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

FONT = ROOT / "font" / "GalHuiwen.ttf"
PUA_MAP = ROOT / "font" / "pua-map.csv"
CHARS = ROOT / "characters.tsv"
LEXICON = ROOT / "lexicon.tsv"

# ---------------------------------------------------------------- Unicode 区块
# 只列与本案相关的。判定「落在哪个区块」用左闭右开区间。
BLOCKS: list[tuple[int, int, str, str]] = [
    (0x0000, 0x0080, "Basic Latin", "基本拉丁字母"),
    (0x0080, 0x0100, "Latin-1 Supplement", "拉丁字母补充"),
    (0x2000, 0x2070, "General Punctuation", "常用标点"),
    (0x3000, 0x3040, "CJK Symbols and Punctuation", "中日韩符号与标点"),
    (0x3400, 0x4E00, "CJK Ext A", "中日韩扩展A"),
    (0x4E00, 0x9FFF, "CJK Unified Ideographs", "中日韩统一表意文字"),
    (0xE000, 0xF8FF, "Private Use Area", "私用区（BMP）"),
    (0xF900, 0xFB00, "CJK Compatibility Ideographs", "中日韩兼容表意文字"),
    (0xF0000, 0xFFFFE, "Supplementary Private Use Area-A", "补充私用区A"),
    (0x100000, 0x10FFFE, "Supplementary Private Use Area-B", "补充私用区B"),
]


def block_of(cp: int) -> tuple[str, str]:
    for lo, hi, en, zh in BLOCKS:
        if lo <= cp < hi:
            return en, zh
    return "Unassigned / other", "其他未列入"


def load_map(path: Path, enc: str = "utf-8-sig") -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding=enc, newline="") as f:
        rows = [r for r in csv.DictReader(f)]
    return [r for r in rows if (r.get("glyph") or "").strip()]


def main() -> int:
    report: dict = {"sources": {}, "font": {}, "codepoints": {}, "lexicon": {}}

    # ------------------------------------------------------------ 1. 字体本身
    if not FONT.exists():
        sys.exit(f"找不到字体：{FONT}")
    font = TTFont(str(FONT), lazy=True)
    # 用 relative_to(ROOT)：克隆下来后 huiwen/ 就是仓库根，
    # 所以报告里应该是 font/GalHuiwen.ttf 而不是 font/GalHuiwen.ttf
    report["font"]["path"] = str(FONT.relative_to(ROOT)).replace("\\", "/")
    report["font"]["size_bytes"] = FONT.stat().st_size
    report["font"]["sfnt_version"] = font.sfntVersion
    report["font"]["num_glyphs"] = font["maxp"].numGlyphs
    report["font"]["units_per_em"] = font["head"].unitsPerEm
    report["font"]["tables"] = sorted(font.keys())

    name_tbl = font["name"]
    for nid, key in ((1, "family"), (2, "subfamily"), (4, "full_name"),
                     (5, "version"), (6, "postscript_name")):
        rec = name_tbl.getDebugName(nid)
        report["font"][key] = rec

    cmap: dict[int, str] = {}
    for sub in font["cmap"].tables:
        # 取平台 3 编码 1（Windows BMP）与 3/10（Windows 全范围）的并集
        cmap.update(sub.cmap)
    cps = sorted(cmap)
    report["codepoints"]["total_mapped"] = len(cps)
    report["codepoints"]["min"] = f"U+{cps[0]:04X}" if cps else None
    report["codepoints"]["max"] = f"U+{cps[-1]:04X}" if cps else None

    blocks = Counter(block_of(c)[0] for c in cps)
    report["codepoints"]["by_block"] = dict(blocks.most_common())

    pua = [c for c in cps if 0xE000 <= c <= 0xF8FF]
    other = [c for c in cps if c not in set(pua)]
    report["codepoints"]["pua_bmp_count"] = len(pua)
    report["codepoints"]["pua_bmp_span"] = (
        f"U+{pua[0]:04X}–U+{pua[-1]:04X}" if pua else None)
    report["codepoints"]["pua_bmp_used_ratio"] = round(len(pua) / 6400, 4)
    report["codepoints"]["non_pua_count"] = len(other)
    report["codepoints"]["non_pua_samples"] = [f"U+{c:04X}" for c in other[:40]]

    # 连续段（提案里要按段列，不能逐个列 15000 行）
    runs: list[tuple[int, int]] = []
    for c in pua:
        if runs and c == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], c)
        else:
            runs.append((c, c))
    report["codepoints"]["pua_runs"] = [
        {"start": f"U+{a:04X}", "end": f"U+{b:04X}", "count": b - a + 1}
        for a, b in runs
    ]
    report["codepoints"]["pua_run_count"] = len(runs)

    # ------------------------------------------------------- 2. pua-map.csv
    pm = load_map(PUA_MAP)
    if pm:
        report["sources"]["pua_map_rows"] = len(pm)
        st = Counter((r.get("status") or "").strip() for r in pm)
        report["sources"]["pua_map_status"] = dict(st)
        cls = Counter((r.get("class_zh") or "").strip() for r in pm)
        report["sources"]["pua_map_classes"] = len(cls)
        report["sources"]["pua_map_class_top"] = dict(cls.most_common(8))
        # 交叉校验：CSV 说的码位 与 字体真的编了的码位 是否一致
        csv_cps = set()
        for r in pm:
            v = (r.get("codepoint") or "").strip()
            if v.upper().startswith("U+"):
                try:
                    csv_cps.add(int(v[2:], 16))
                except ValueError:
                    pass
        if csv_cps:
            only_font = sorted(set(cps) - csv_cps)
            only_csv = sorted(csv_cps - set(cps))
            report["sources"]["crosscheck"] = {
                "csv_codepoints": len(csv_cps),
                "font_codepoints": len(cps),
                "only_in_font": len(only_font),
                "only_in_csv": len(only_csv),
                "consistent": not only_font and not only_csv,
                "only_in_font_sample": [f"U+{c:04X}" for c in only_font[:10]],
                "only_in_csv_sample": [f"U+{c:04X}" for c in only_csv[:10]],
            }

    # ------------------------------------------------------ 3. characters.tsv
    ch = load_map(CHARS, enc="utf-8")
    if ch:
        report["sources"]["characters_rows"] = len(ch)
        st = Counter((r.get("status") or "").strip() for r in ch)
        report["sources"]["characters_status"] = dict(st)
        # 备用字占的码位是不是也真在字体里？
        resv = [r for r in ch if (r.get("status") or "").strip() == "reserved"]
        if resv:
            rc = []
            for r in resv:
                try:
                    rc.append(int((r.get("codepoint") or "0").strip()))
                except ValueError:
                    pass
            in_font = sum(1 for c in rc if c in cmap)
            report["sources"]["reserved_in_font"] = {
                "reserved_rows": len(resv),
                "reserved_mapped_in_font": in_font,
            }

    # --------------------------------------------------------- 4. lexicon.tsv
    lex = load_map(LEXICON, enc="utf-8")
    if lex:
        report["lexicon"]["rows"] = len(lex)
        report["lexicon"]["kinds"] = dict(
            Counter((r.get("kind") or "").strip() for r in lex))
        syls = {(r.get("syll") or "").strip() for r in lex if (r.get("syll") or "").strip()}
        report["lexicon"]["distinct_syllables_used"] = len(syls)

    # ------------------------------------------------------------------ 落盘
    (OUT / "char_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    f = report["font"]
    c = report["codepoints"]
    L: list[str] = []
    L.append("# 洄文字符集现状审计\n")
    L.append("> 由 `tools/char_audit.py` 直接解析字体文件生成，非人工填写。\n")
    L.append("## 一、字体文件\n")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append(f"| 文件 | `{f['path']}` |")
    L.append(f"| 大小 | {f['size_bytes']:,} 字节 |")
    L.append(f"| 字体名 | {f.get('family')} / {f.get('full_name')} |")
    L.append(f"| 版本 | {f.get('version')} |")
    L.append(f"| PostScript 名 | {f.get('postscript_name')} |")
    L.append(f"| 字形数 | {f['num_glyphs']:,} |")
    L.append(f"| em 单位 | {f['units_per_em']} |")
    L.append(f"| 表 | {', '.join(f['tables'])} |")
    L.append("")
    L.append("## 二、码位占用（直接读 cmap）\n")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append(f"| cmap 中已映射码位 | **{c['total_mapped']:,}** |")
    L.append(f"| 最小 | {c['min']} |")
    L.append(f"| 最大 | {c['max']} |")
    L.append(f"| 私用区(BMP) 码位数 | **{c['pua_bmp_count']:,}**，跨度 {c['pua_bmp_span']} |")
    L.append(f"| 私用区占用率 | **{c['pua_bmp_used_ratio']:.1%}**（U+E000–U+F8FF 共 6400 位）|")
    L.append(f"| 私用区外的码位 | {c['non_pua_count']} |")
    L.append(f"| 连续段数 | {c['pua_run_count']} |")
    L.append("")
    L.append("### 按 Unicode 区块归类\n")
    L.append("| 区块 | 码位数 |")
    L.append("|---|---:|")
    for k, v in c["by_block"].items():
        L.append(f"| {k} | {v:,} |")
    L.append("")
    L.append("### 私用区连续段\n")
    L.append("| 段 | 起 | 止 | 数量 |")
    L.append("|---|---|---|---:|")
    for i, r in enumerate(c["pua_runs"], 1):
        L.append(f"| {i} | {r['start']} | {r['end']} | {r['count']:,} |")
    L.append("")
    if "crosscheck" in report.get("sources", {}):
        x = report["sources"]["crosscheck"]
        L.append("## 三、交叉校验（CSV vs 字体）\n")
        L.append(f"- CSV 声明的码位数：{x['csv_codepoints']:,}")
        L.append(f"- 字体实际映射的码位数：{x['font_codepoints']:,}")
        L.append(f"- **一致性：{'通过' if x['consistent'] else '不一致'}**")
        if not x["consistent"]:
            L.append(f"  - 只在字体里：{x['only_in_font']} 个 {x['only_in_font_sample']}")
            L.append(f"  - 只在 CSV 里：{x['only_in_csv']} 个 {x['only_in_csv_sample']}")
        L.append("")
    if "characters_status" in report.get("sources", {}):
        L.append("## 四、字符总表\n")
        L.append(f"- 行数：{report['sources']['characters_rows']:,}")
        for k, v in report["sources"]["characters_status"].items():
            L.append(f"  - {k}：{v:,}")
        if "reserved_in_font" in report["sources"]:
            r = report["sources"]["reserved_in_font"]
            L.append(f"- 备用字中**真的编进字体**的：{r['reserved_mapped_in_font']:,} / {r['reserved_rows']:,}")
        L.append("")
    if report.get("lexicon"):
        lx = report["lexicon"]
        L.append("## 五、词表\n")
        L.append(f"- 条目数：{lx['rows']:,}")
        L.append(f"- 用到的不同音节：{lx['distinct_syllables_used']:,}")
        for k, v in sorted(lx["kinds"].items()):
            L.append(f"  - {k}：{v:,}")
        L.append("")

    (OUT / "char_audit.md").write_text("\n".join(L), encoding="utf-8")

    # ------------------------------------------------------------------ 摘要
    print("=" * 62)
    print("洄文字符集审计")
    print("=" * 62)
    print(f"字体        {f.get('full_name')}   ({f['num_glyphs']:,} 字形, em={f['units_per_em']})")
    print(f"cmap 码位   {c['total_mapped']:,}   ({c['min']} .. {c['max']})")
    print(f"私用区      {c['pua_bmp_count']:,} 位，占 BMP 私用区 {c['pua_bmp_used_ratio']:.1%}")
    print(f"            {c['pua_bmp_span']}  （{c['pua_run_count']} 个连续段）")
    print(f"私用区外    {c['non_pua_count']} 位")
    for k, v in c["by_block"].items():
        print(f"    {k:<40} {v:>7,}")
    if "crosscheck" in report.get("sources", {}):
        x = report["sources"]["crosscheck"]
        print(f"交叉校验    {'通过' if x['consistent'] else '不一致'}  "
              f"(CSV {x['csv_codepoints']:,} / 字体 {x['font_codepoints']:,})")
    if report.get("lexicon"):
        print(f"词表        {report['lexicon']['rows']:,} 条，"
              f"{report['lexicon']['distinct_syllables_used']:,} 个音节")
    print("-" * 62)
    print(f"已写入 {OUT / 'char_audit.json'}")
    print(f"已写入 {OUT / 'char_audit.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
