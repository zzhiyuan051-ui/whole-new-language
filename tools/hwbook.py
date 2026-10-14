#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 全书合成

把「教程」「字典条目」「附录」合成一部书，输出 Markdown（并可选 DOCX）。

结构：
  封面 → 目录 → 教程（二十课）→ 词典用法说明 → 词典正文（按语义类）→ 附录

用法：
    python tools/hwbook.py            # 生成 dict/洄文大字典.md
    python tools/hwbook.py --docx     # 另出 DOCX
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import syllabary as S

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DICT = ROOT / "dict"
COURSE = ROOT / "course"

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def nchars(t: str) -> int:
    return len(CJK.findall(t))


def load_lex() -> list[dict]:
    lines = (ROOT / "lexicon.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]


def read_dir(p: Path) -> list[tuple[str, str]]:
    out = []
    for f in sorted(p.glob("*.md")):
        out.append((f.name, f.read_text(encoding="utf-8")))
    return out


def main() -> int:
    want_docx = "--docx" in sys.argv
    rows = load_lex()
    byid = {r["id"]: r for r in rows}
    parts: list[tuple[str, str]] = []      # (标题, 正文)

    # ---------- 封面 ----------
    parts.append(("封面", """# 洄文大字典

**一部人造语言的字典与教程**

洄文（huíwén）——自源文字，图语法。一句话是一张图，说话是把图搭起来，听懂是在图上走通。

---

**这一版包含**

| 部分 | 内容 | 规模 |
|---|---|---|
| 教程 | 二十课，从零学会读和写，只懂中文也能学 | 五编二十课 |
| 词典 | 3000 个词条，每条含音、形、义、位、理、辨、例 | 3000 条 |
| 附录 | 发音总表、常用词、字表、笔画索引、音节索引 | 五种 |

**读者设定**：只懂中文、从未接触过洄文的人。

---
"""))

    # ---------- 教程 ----------
    course_files = read_dir(COURSE)
    for name, text in course_files:
        title = text.splitlines()[0].lstrip("# ").strip() or name
        parts.append((f"教程 · {title}", text))

    # ---------- 词典用法 ----------
    usage = (DICT / "00-体例.md")
    if usage.exists():
        parts.append(("词典用法与体例", usage.read_text(encoding="utf-8")))

    # ---------- 词典正文 ----------
    root_entries = read_dir(DICT / "entries")
    deriv_entries = read_dir(DICT / "entries-derived")
    func_entries = read_dir(DICT / "entries-function")
    all_entries: dict[str, str] = {}
    for name, text in root_entries + deriv_entries + func_entries:
        all_entries[name.replace(".md", "")] = text
    # 按语义类分章
    class_of: dict[str, int] = {r["id"]: int(r["class_no"]) for r in rows}
    class_zh = [d[1] for d in S.DOMAINS] + ["虚词"]
    buckets: dict[int, list[str]] = {}
    for wid, text in all_entries.items():
        c = class_of.get(wid)
        if c is None:
            continue
        buckets.setdefault(c, []).append(text)
    for c in sorted(buckets):
        name = class_zh[c] if c < len(class_zh) else f"第 {c} 类"
        body = "\n\n".join(sorted(buckets[c], key=lambda t: t.split("　")[0]))
        parts.append((f"词典正文 · {name}类（{len(buckets[c])} 条）", body))

    # ---------- 附录 ----------
    app = []
    app.append("## 附录一　音节总表\n")
    app.append("洄文全部 624 个音节（13 声基 × 8 腔 × 6 调）。左列为拼式，右列为 IPA。\n")
    app.append("| 音节 | IPA | 声基 | 腔 | 调 |\n|---|---|---|---|---|")
    for c in S.all_syllables():
        app.append(f"| `{c['syll']}` | {c['ipa']} | {c['onset']} | {c['vowel']} | {c['tone']} |")
    app.append("\n## 附录二　派生式总表\n")
    import patterns as PT
    app.append("| 式 | 中文构词式 | 英文 | 词性 | 意义 |\n|---|---|---|---|---|")
    for p in PT.PATTERNS:
        app.append(f"| {p.code} | {p.zh} | {p.en} | {p.pos} | {p.note} |")
    app.append("\n## 附录三　字形索引（按编号）\n")
    app.append("| 编号 | 词形 | 汉字 | 类 | 来源 |\n|---:|---|---|---|---|")
    for r in sorted(rows, key=lambda r: int(r["glyph"])):
        app.append(f"| {r['glyph']} | {r['form']} | {r['zh']} | {r['class_zh']} | {r['kind']} |")
    app.append("\n## 附录四　汉字索引（按拼音）\n")
    app.append("| 汉字 | 词形 | 音节 | 类 |\n|---|---|---|---|")
    for r in sorted(rows, key=lambda r: r["zh"]):
        app.append(f"| {r['zh']} | {r['form']} | `{r['syll']}` | {r['class_zh']} |")
    app.append("\n## 附录五　阿拉伯数字与序数\n")
    app.append("见附录三与词典「数量」类。洄文的数词：`zy6` 一、`zv6` 二、`ha6` 三、"
               "`he6` 几、`tu` 零、`ty` 半、`toe` 双。\n")
    parts.append(("附录", "\n".join(app)))

    # ---------- 合成 ----------
    out = []
    for title, text in parts:
        out.append(text.rstrip() + "\n")
    book = "\n\n---\n\n".join(out)
    (DICT / "洄文大字典.md").write_text(book, encoding="utf-8")

    total = nchars(book)
    ent = len(all_entries)
    print(f"全书已合成 → dict/洄文大字典.md")
    print(f"  章节 {len(parts)} 节｜词条 {ent} 条｜合计 {total} 字")
    for title, text in parts:
        n = nchars(text)
        if n > 2000:
            print(f"    {title[:34]:<36} {n:>8} 字")

    if want_docx:
        try:
            make_docx(parts, DICT / "洄文大字典.docx")
        except Exception as e:                     # noqa: BLE001
            print(f"  DOCX 生成失败：{e}")
    return 0


def make_docx(parts, path: Path) -> None:
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.font.size = Pt(10.5)
    for title, text in parts:
        for line in text.splitlines():
            s = line.rstrip()
            if s.startswith("### "):
                doc.add_heading(s[4:], level=3)
            elif s.startswith("## "):
                doc.add_heading(s[3:], level=2)
            elif s.startswith("# "):
                doc.add_heading(s[2:], level=1)
            elif s.startswith("|"):
                doc.add_paragraph(s)
            elif s.strip() == "---":
                doc.add_paragraph("")
            else:
                doc.add_paragraph(s)
        doc.add_page_break()
    doc.save(str(path))
    print(f"  DOCX → {path.name}（{path.stat().st_size // 1024} KB）")


if __name__ == "__main__":
    sys.exit(main())
