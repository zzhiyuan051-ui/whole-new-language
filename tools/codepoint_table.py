#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成洄文码表（machine-readable + human-readable）。

**唯一真相源是字体文件本身**（cmap），不是任何中间 CSV —— 码表是拿去给外部
机构看的，填错码位等于自毁提案。所以本脚本以 cmap 为准，只从 characters.tsv
补齐「这个码位是什么字」的人文信息，并显式报告两边对不上的地方。

产物（全部落 huiwen/tools/out/）：
  codepoints.csv   码位主表，一行一码位（给程序、给提案附录）
  codepoints.md    人读码表（按语义类分组）
  codepoints.json  机器可读汇总

用法：
  python huiwen/tools/codepoint_table.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("需要 fontTools：python -m pip install fonttools")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

FONT = ROOT / "font" / "GalHuiwen.ttf"
CHARS = ROOT / "characters.tsv"


def read_tsv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with io.open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    return [r for r in rows if (r.get("glyph") or "").strip()]


def main() -> int:
    if not FONT.exists():
        sys.exit(f"找不到字体：{FONT}")

    # 1) 以字体 cmap 为唯一码位真相源
    font = TTFont(str(FONT), lazy=True)
    cmap: dict[int, str] = {}
    for sub in font["cmap"].tables:
        cmap.update(sub.cmap)
    font_cps = sorted(cmap)
    font_set = set(font_cps)
    gname_of = {cp: cmap[cp] for cp in font_cps}

    # 2) 人文信息从 characters.tsv 取
    ch_rows = read_tsv(CHARS)
    by_cp: dict[int, dict] = {}
    orphan_rows: list[dict] = []          # 表里有、字体里没有码位
    for r in ch_rows:
        raw = (r.get("codepoint") or "").strip()
        if raw in ("", "None", "none", "-"):
            continue
        try:
            cp = int(raw)                  # characters.tsv 存的是十进制
        except ValueError:
            try:
                cp = int(raw[2:], 16) if raw.upper().startswith("U+") else -1
            except ValueError:
                cp = -1
        if cp < 0:
            continue
        by_cp[cp] = r
        if cp not in font_set:
            orphan_rows.append(r)

    missing_meta = [cp for cp in font_cps if cp not in by_cp]

    # 3) 主表
    records: list[OrderedDict] = []
    for cp in font_cps:
        r = by_cp.get(cp, {})
        ch = chr(cp)
        records.append(OrderedDict([
            ("codepoint", f"U+{cp:04X}"),
            ("decimal", cp),
            ("char", ch),
            ("glyph_id", (r.get("glyph") or "").strip()),
            ("glyph_name", gname_of.get(cp, "")),
            ("status", (r.get("status") or "").strip()),
            ("class_no", (r.get("class_no") or "").strip()),
            ("class_zh", (r.get("class_zh") or "").strip()),
            ("family", (r.get("family") or "").strip()),
            ("family_zh", (r.get("family_zh") or "").strip()),
            ("form", (r.get("form") or "").strip()),
            ("syllable", (r.get("syll") or "").strip()),
            ("gloss_zh", (r.get("zh") or "").strip()),
            ("gloss_en", (r.get("en") or "").strip()),
            ("pos", (r.get("pos") or "").strip()),
            ("kind", (r.get("kind") or "").strip()),
            ("label", (r.get("label") or "").strip()),
        ]))

    with io.open(OUT / "codepoints.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)

    # 4) 汇总
    # 注意：本次编码只覆盖「已定义」字符，所以 by_class 只会覆盖一部分语义类。
    # 规范里的语义类总数是 44（class_no 0..43）。
    #
    # ⚠️ 踩过的坑：**必须按 class_no 数，不能按 class_zh 名数**。
    #    虚词与「自然」共用 class_no=13（不同 class_zh），按名数会得到 45 个类名，
    #    于是"21 有 + 24 无 = 45 ≠ 44"这个不自洽就是信号。按 class_no 数才是分区。
    def _cno(r: dict) -> str | None:
        v = (r.get("class_no") or "").strip()
        return v if v.isdigit() else None

    classes_in_font = {_cno(r) for r in records} - {None}
    classes_all = {_cno(r) for r in ch_rows} - {None}
    summary = {
        "font": str(FONT.relative_to(ROOT.parent)).replace("\\", "/"),
        "font_full_name": font["name"].getDebugName(4),
        "total_codepoints": len(font_cps),
        "range": {"first": f"U+{font_cps[0]:04X}", "last": f"U+{font_cps[-1]:04X}"}
                 if font_cps else None,
        "by_status": dict(Counter(r["status"] for r in records)),
        "by_class": dict(Counter(r["class_zh"] for r in records).most_common()),
        "by_family": dict(Counter(r["family_zh"] for r in records).most_common()),
        "classes": {
            "declared_in_spec": 44,
            "class_no_range": f"{min(classes_all, key=int)}..{max(classes_all, key=int)}"
                              if classes_all else None,
            "distinct_class_no_in_table": len(classes_all),
            "with_defined_characters": len(classes_in_font),
            "without_defined_characters": len(classes_all - classes_in_font),
            "distinct_class_names_in_table": len(
                {r.get("class_zh", "").strip() for r in ch_rows if r.get("class_zh")}),
            "note": "虚词与自然共用 class_no=13，故类名数(45)比类号数(44)多 1",
        },
        "distinct_syllables": len({r["syllable"] for r in records if r["syllable"]}),
        "all_in_pua_bmp": all(0xE000 <= cp <= 0xF8FF for cp in font_cps),
        "consistency": {
            "rows_in_characters_tsv_with_codepoint": len(by_cp),
            "codepoints_in_font": len(font_cps),
            "font_codepoints_without_metadata": len(missing_meta),
            "tsv_rows_whose_codepoint_not_in_font": len(orphan_rows),
            "consistent": not missing_meta and not orphan_rows,
        },
    }
    if missing_meta:
        summary["consistency"]["missing_metadata_sample"] = [
            f"U+{c:04X}" for c in missing_meta[:10]]
    if orphan_rows:
        summary["consistency"]["orphan_sample"] = [
            (r.get("label") or "")[:40] for r in orphan_rows[:10]]

    (OUT / "codepoints.json").write_text(
        json.dumps({"summary": summary, "records": records},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    # 5) 人读码表
    L: list[str] = []
    L.append("# 洄文码位表（Code Point Table）\n")
    L.append(f"> 数据源：`{summary['font']}` 的 `cmap` 表，"
             f"字体名 **{summary['font_full_name']}**。")
    L.append("> 生成脚本：`huiwen/tools/codepoint_table.py`（可复算）。\n")
    L.append("## 一、总览\n")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append(f"| 已编码码位总数 | **{summary['total_codepoints']:,}** |")
    if summary["range"]:
        L.append(f"| 码位范围 | {summary['range']['first']} – {summary['range']['last']} |")
    L.append(f"| 全部位于 BMP 私用区 | {'是' if summary['all_in_pua_bmp'] else '**否**'} |")
    L.append(f"| 不同音节数 | {summary['distinct_syllables']:,} |")
    cl = summary["classes"]
    L.append(f"| 语义类（规范声明） | {cl['declared_in_spec']}（class_no {cl['class_no_range']}） |")
    L.append(f"| 语义类（本表有已定义字符的） | {cl['with_defined_characters']} |")
    L.append(f"| 语义类（当前只有备用字、无码位） | {cl['without_defined_characters']} |")
    L.append("")
    L.append("> ⚠️ 本表只覆盖**已定义**字符，因此下面的「按语义类」只列出有码位的那几类。"
             f"规范里的语义类总数是 **{cl['declared_in_spec']}**"
             f"（`class_no` {cl['class_no_range']}），其余各类当前只有备用字"
             "（已成形、待指派音义），尚无码位。")
    L.append(f">")
    L.append(f"> 计数口径：按 `class_no` 分区（{cl['with_defined_characters']} + "
             f"{cl['without_defined_characters']} = {cl['declared_in_spec']}）。"
             f"表中共出现 {cl['distinct_class_names_in_table']} 个类名 —— "
             "因为虚词与「自然」共用 `class_no=13`，所以类名比类号多 1 个。")
    L.append("")
    L.append("### 按状态\n")
    L.append("| 状态 | 数量 |")
    L.append("|---|---:|")
    for k, v in summary["by_status"].items():
        L.append(f"| {k} | {v:,} |")
    L.append("")
    L.append("### 按家族纹\n")
    L.append("| 家族纹 | 数量 |")
    L.append("|---|---:|")
    for k, v in summary["by_family"].items():
        L.append(f"| {k} | {v:,} |")
    L.append("")
    L.append("### 按语义类\n")
    L.append("| 语义类 | 码位数 |")
    L.append("|---|---:|")
    for k, v in summary["by_class"].items():
        L.append(f"| {k} | {v:,} |")
    L.append("")
    c = summary["consistency"]
    L.append("## 二、一致性校验\n")
    L.append("| 项 | 值 |")
    L.append("|---|---:|")
    L.append(f"| characters.tsv 中带码位的行 | {c['rows_in_characters_tsv_with_codepoint']:,} |")
    L.append(f"| 字体 cmap 中的码位 | {c['codepoints_in_font']:,} |")
    L.append(f"| 字体有、元数据没有 | {c['font_codepoints_without_metadata']} |")
    L.append(f"| 元数据有、字体没有 | {c['tsv_rows_whose_codepoint_not_in_font']} |")
    L.append(f"| **结论** | **{'一致' if c['consistent'] else '不一致（见下）'}** |")
    L.append("")
    if not c["consistent"]:
        if c.get("missing_metadata_sample"):
            L.append(f"- 字体有、元数据没有的样例：{', '.join(c['missing_metadata_sample'])}")
        if c.get("orphan_sample"):
            L.append(f"- 元数据有、字体没有的样例：{'; '.join(c['orphan_sample'])}")
        L.append("")
    L.append("## 三、码位明细（按语义类分组）\n")
    L.append("完整机器可读表见 `out/codepoints.csv`。下按语义类列出前若干条。\n")

    grouped: dict[str, list[dict]] = {}
    for r in records:
        grouped.setdefault(r["class_zh"] or "(无)", []).append(r)
    for cls, rows in grouped.items():
        L.append(f"### {cls}（{len(rows)} 个）\n")
        L.append("| 码位 | 字符 | 字形号 | 家族纹 | 音节 | 词形 | 中文 |")
        L.append("|---|---|---|---|---|---|---|")
        for r in rows[:12]:
            L.append(f"| `{r['codepoint']}` | {r['char']} | {r['glyph_id']} | "
                     f"{r['family_zh']} | {r['syllable']} | {r['form']} | {r['gloss_zh']} |")
        if len(rows) > 12:
            L.append(f"| … | | | | | | 其余 {len(rows) - 12} 条见 CSV |")
        L.append("")

    (OUT / "codepoints.md").write_text("\n".join(L), encoding="utf-8")

    print("=" * 62)
    print("洄文码表")
    print("=" * 62)
    print(f"码位数        {summary['total_codepoints']:,}")
    if summary["range"]:
        print(f"范围          {summary['range']['first']} .. {summary['range']['last']}")
    print(f"全在 BMP 私用区  {summary['all_in_pua_bmp']}")
    print(f"状态          {summary['by_status']}")
    print(f"音节数        {summary['distinct_syllables']:,}")
    print(f"一致性        {'一致' if c['consistent'] else '不一致'}")
    print("-" * 62)
    for n in ("codepoints.csv", "codepoints.md", "codepoints.json"):
        print(f"已写入 {OUT / n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
