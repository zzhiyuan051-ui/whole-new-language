#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成人读版词典（按语义类分组）+ 一行一类速查表。"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import hwglyph as G

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load() -> list[dict]:
    lines = (ROOT / "lexicon.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]


def main() -> None:
    rows = load()
    by_cls: dict[str, list[dict]] = {}
    for r in rows:
        by_cls.setdefault(r["class_zh"], []).append(r)

    order = [d[1] for d in __import__("syllabary").DOMAINS] + ["虚词"]
    md = ["# 洄文词典（按语义类）", "",
          f"共 **{len(rows)}** 条：词根 480 ＋ 虚词 32 ＋ 派生 2488。",
          "",
          "列：词形／音节（连写）／中文／英文／词性／槽表（临位）／字形编号／来源／定义。",
          "槽表里的 `甲 乙 丙 丁 戊 己 庚` 是七临位；`—` 表示虚词无槽。", ""]
    for cls in order:
        if cls not in by_cls:
            continue
        md.append(f"## {cls}（{len(by_cls[cls])} 条）")
        md.append("")
        md.append("| 词形 | 音节 | 中文 | 英文 | 词性 | 槽表 | 字形 | 来源 | 定义 |")
        md.append("|---|---|---|---|---|---|---:|---|---|")
        for r in by_cls[cls]:
            md.append(f"| {r['form']} | `{r['syll']}` | {r['zh']} | {r['en']} | "
                      f"{r['pos']} | {r['slots']} | {r['glyph']} | {r['kind']} | {r['def_zh']} |")
        md.append("")
    (ROOT / "dictionary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # 速查表：只放词根与虚词（派生词太多，单列一份）
    lines = ["# 洄文词表速查", "",
             "## 词根与虚词（512 条，单音节）", ""]
    for cls in order:
        if cls not in by_cls:
            continue
        base = [r for r in by_cls[cls] if r["kind"] in ("root", "function")]
        if base:
            items = "  ".join(f"{r['syll']}={r['zh']}" for r in base)
            lines.append(f"**{cls}**（{len(base)}）：{items}")
            lines.append("")
    deriv = [r for r in rows if r["kind"] == "derived"]
    lines += ["## 派生词（2488 条，双音节）", "",
              "派生词按「词根 × 派生式」机械合成，完整清单见 `dictionary.md`。",
              "构词式见 `spec/04-morphology.md`。", "",
              "样本："]
    for r in deriv[:40]:
        lines.append(f"- {r['form']}　{r['zh']}　{r['en']}")
    (ROOT / "lexicon-cheatsheet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    kc = Counter(r["kind"] for r in rows)
    print(f"dictionary.md（{len(rows)} 条）与 lexicon-cheatsheet.md 已生成")
    print(f"来源分布：{dict(kc)}｜语义类 {len(by_cls)} 个")


if __name__ == "__main__":
    main()
