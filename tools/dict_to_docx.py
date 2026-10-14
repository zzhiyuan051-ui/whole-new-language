#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把《洄文大字典》的 Markdown 转成**排好版**的 Word 文档。

为什么要重写：旧版 docx 是把 Markdown 文本直接灌进 Word 的 ——
标题转成了真样式，但 52,760 处 `**加粗**` 和 38,098 个表格竖线**原样留在了正文里**，
Word 里看到的是一堆 `**` 和 `| 部分 | 内容 |`，不是成书。

这一版要做对的事：
  · `**粗体**` → 真加粗；`` `代码` `` → 等宽 + 浅底纹；*斜体* → 真斜体
  · Markdown 表格 → 真 Word 表格（带表头底纹、跨页重复表头）
  · `>` 引用 → 缩进 + 左边框
  · ``` 代码块 → 等宽底纹块
  · `---` → 细分隔线
  · 封面页 + 目录域 + 页脚页码
  · 中文字体（正文宋体 / 标题微软雅黑）、行距、页边距

一个刻意的取舍：列表**不用 Word 的自动编号**，而是保留原marker 并做悬挂缩进。
因为 python-docx 的 'List Number' 会跨列表连续编号（第二组从 47 开始），
课程步骤的序号错乱比不好看严重得多。
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
DICT = ROOT / "dict"
SRC = DICT / "洄文大字典.md"
OUT = DICT / "洄文大字典.docx"
REPORT = DICT / "_转换报告.txt"

# ——— 字体设置：中文与西文分开设，否则 Word 会用错字体 ———
EA_BODY = "宋体"
EA_HEAD = "微软雅黑"
LATIN_BODY = "Times New Roman"
LATIN_HEAD = "Segoe UI"
MONO = "Consolas"

INK = RGBColor(0x1A, 0x1A, 0x1A)
HEAD_COLOR = RGBColor(0x1F, 0x3A, 0x5F)
MUTED = RGBColor(0x60, 0x60, 0x68)
CODE_BG = "F2F3F5"
QUOTE_BG = "F7F8FA"


# ================================================================ 底层工具
def set_font(run, *, ea=EA_BODY, latin=LATIN_BODY, size=None,
             bold=None, italic=None, color=None) -> None:
    """给一个 run 设字体。**中文必须走 w:eastAsia**，只设 run.font.name 对中文无效。"""
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    rf.set(qn("w:ascii"), latin)
    rf.set(qn("w:hAnsi"), latin)
    rf.set(qn("w:eastAsia"), ea)
    rf.set(qn("w:cs"), latin)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    run.font.color.rgb = color if color is not None else INK


def shade(element, fill: str) -> None:
    """给段落/单元格加底纹。"""
    pr = element.get_or_add_pPr() if hasattr(element, "get_or_add_pPr") \
        else element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pr.append(shd)


def para_border(p, *, left=None, bottom=None) -> None:
    ppr = p._element.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    for side, spec in (("left", left), ("bottom", bottom)):
        if not spec:
            continue
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(spec.get("sz", 6)))
        el.set(qn("w:space"), str(spec.get("space", 4)))
        el.set(qn("w:color"), spec.get("color", "C8CCD4"))
        pbdr.append(el)
    if len(pbdr):
        ppr.append(pbdr)


def field(p, instr: str, placeholder: str = "") -> None:
    """插入一个 Word 域（目录、页码都用它）。"""
    r1 = p.add_run()._element
    fc = OxmlElement("w:fldChar")
    fc.set(qn("w:fldCharType"), "begin")
    r1.append(fc)

    r2 = p.add_run()._element
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    r2.append(it)

    r3 = p.add_run()._element
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    r3.append(sep)

    if placeholder:
        r4 = p.add_run(placeholder)
        set_font(r4, size=10, color=MUTED)

    r5 = p.add_run()._element
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    r5.append(end)


# ================================================================ 行内解析
TOKEN = re.compile(r"(\*\*.+?\*\*|`[^`]+`|(?<![\w*])\*[^*\n]+?\*(?![\w*]))")


def add_inline(p, text: str, *, size=10.5, ea=EA_BODY, latin=LATIN_BODY,
               base_bold=False, color=INK) -> None:
    """把一行里的 **粗体** / `代码` / *斜体* 拆成多个 run。"""
    for part in TOKEN.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            set_font(p.add_run(part[2:-2]), size=size, ea=ea, latin=latin,
                     bold=True, color=color)
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            r = p.add_run(part[1:-1])
            set_font(r, size=size - 0.5, ea=MONO, latin=MONO,
                     color=RGBColor(0x9B, 0x2C, 0x2C))
        elif (part.startswith("*") and part.endswith("*") and len(part) > 2
              and not part.startswith("**")):
            set_font(p.add_run(part[1:-1]), size=size, ea=ea, latin=latin,
                     italic=True, color=color)
        else:
            set_font(p.add_run(part), size=size, ea=ea, latin=latin,
                     bold=base_bold, color=color)


# ================================================================ 样式
def setup_styles(doc: Document) -> None:
    st = doc.styles

    n = st["Normal"]
    n.font.size = Pt(10.5)
    n.font.color.rgb = INK
    rf = n.element.get_or_add_rPr().get_or_add_rFonts()
    rf.set(qn("w:ascii"), LATIN_BODY)
    rf.set(qn("w:hAnsi"), LATIN_BODY)
    rf.set(qn("w:eastAsia"), EA_BODY)
    pf = n.paragraph_format
    pf.line_spacing = 1.3
    pf.space_after = Pt(2)

    spec = {
        "Heading 1": (21, EA_HEAD, LATIN_HEAD, True, 18, 12),
        "Heading 2": (15.5, EA_HEAD, LATIN_HEAD, True, 16, 8),
        "Heading 3": (11.5, EA_HEAD, LATIN_HEAD, True, 12, 4),
        "Heading 4": (10.5, EA_HEAD, LATIN_HEAD, True, 8, 3),
    }
    for name, (size, ea, latin, bold, before, after) in spec.items():
        s = st[name]
        s.font.size = Pt(size)
        s.font.bold = bold
        s.font.color.rgb = HEAD_COLOR
        r = s.element.get_or_add_rPr().get_or_add_rFonts()
        r.set(qn("w:ascii"), latin)
        r.set(qn("w:hAnsi"), latin)
        r.set(qn("w:eastAsia"), ea)
        s.paragraph_format.space_before = Pt(before)
        s.paragraph_format.space_after = Pt(after)
        s.paragraph_format.keep_with_next = True

    st["Heading 1"].paragraph_format.page_break_before = True
    st["Heading 1"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER


def setup_page(doc: Document) -> None:
    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.top_margin = s.bottom_margin = Cm(2.2)
    s.left_margin = s.right_margin = Cm(2.0)

    # 页脚页码
    p = s.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("— "), size=9, color=MUTED)
    field(p, "PAGE", "1")
    set_font(p.add_run(" —"), size=9, color=MUTED)


def cover(doc: Document, stats: dict) -> None:
    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("洄文大字典"), size=40, ea=EA_HEAD, latin=LATIN_HEAD, bold=True,
             color=HEAD_COLOR)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("一部人造语言的字典与教程"), size=15, ea=EA_HEAD, latin=LATIN_HEAD,
             color=MUTED)
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("洄文（huíwén）· 自源文字 · 图语法"), size=11, color=MUTED)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("一句话是一张图 · 说话是把图搭起来 · 听懂是在图上走通"),
             size=11, color=MUTED)

    for _ in range(3):
        doc.add_paragraph()
    for line in (
        f"词典 {stats['entries']:,} 条　·　教程五编二十课",
        f"全书 {stats['han']:,} 汉字",
        f"音节 624　·　字符 15000　·　词 3000",
    ):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p.add_run(line), size=11, color=MUTED)

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # 目录页
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("目　录"), size=20, ea=EA_HEAD, latin=LATIN_HEAD, bold=True,
             color=HEAD_COLOR)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("（在 Word 里按 Ctrl+A 再按 F9 可刷新页码）"), size=9, color=MUTED)
    tp = doc.add_paragraph()
    field(tp, r'TOC \o "1-2" \h \z \u',
          "目录尚未生成：在 Word 里全选（Ctrl+A）后按 F9 刷新即可。")
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ================================================================ 主转换
def convert() -> dict:
    t0 = time.time()
    lines = SRC.read_text(encoding="utf-8").splitlines()
    han = len(re.findall(r"[\u4e00-\u9fff]", "\n".join(lines)))
    print(f"源文件 {len(lines):,} 行，{han:,} 汉字，开始转换…")

    doc = Document()
    setup_styles(doc)
    setup_page(doc)

    n_entries = sum(1 for l in lines if l.startswith("### "))
    cover(doc, {"entries": n_entries, "han": han})

    stats = {"bold": 0, "code": 0, "tables": 0, "table_rows": 0,
             "quotes": 0, "fences": 0, "hr": 0, "headings": 0, "lists": 0}

    i = 0
    n = len(lines)
    last_i = -1
    while i < n:
        # 防死循环：每个分支都必须让 i 前进。漏掉一处（水平线分支就漏过）
        # 就会无限新建空段落 —— 表现是"跑 19 分钟没完、内存涨到几百 MB"，
        # 极难从表象看出来。这里直接快失败。
        if i == last_i:
            raise RuntimeError(
                f"死循环：第 {i} 行没有前进 -> {lines[i][:80]!r}")
        last_i = i
        raw = lines[i]
        s = raw.rstrip()

        # —— 空行 ——
        if not s.strip():
            i += 1
            continue

        # —— 围栏代码块 ——
        if s.startswith("```"):
            stats["fences"] += 1
            i += 1
            block: list[str] = []
            while i < n and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1                                     # 跳过收尾 ```
            for ln in block:
                p = doc.add_paragraph()
                pf = p.paragraph_format
                pf.left_indent = Cm(0.6)
                pf.space_before = Pt(0)
                pf.space_after = Pt(0)
                pf.line_spacing = 1.0
                shade(p._element, CODE_BG)
                set_font(p.add_run(ln if ln.strip() else " "),
                         size=9, ea=MONO, latin=MONO)
            doc.add_paragraph().paragraph_format.space_after = Pt(4)
            continue

        # —— 表格 ——
        if s.startswith("|"):
            rows: list[list[str]] = []
            while i < n and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s:\-]+$", "".join(cells)):
                    rows.append(cells)
                i += 1
            if rows:
                ncol = max(len(r) for r in rows)
                t = doc.add_table(rows=0, cols=ncol)
                t.style = "Table Grid"
                t.alignment = WD_TABLE_ALIGNMENT.CENTER
                t.autofit = True
                for ri, r in enumerate(rows):
                    cells = t.add_row().cells
                    for ci in range(ncol):
                        txt = r[ci] if ci < len(r) else ""
                        cell = cells[ci]
                        cell.text = ""
                        p = cell.paragraphs[0]
                        p.paragraph_format.space_after = Pt(1)
                        p.paragraph_format.space_before = Pt(1)
                        add_inline(p, txt, size=9.5,
                                   base_bold=(ri == 0))
                        if ri == 0:
                            shade(cell._element, "E8EDF4")
                        for run in p.runs:
                            if ri == 0:
                                run.font.bold = True
                # 表头跨页重复
                trpr = t.rows[0]._tr.get_or_add_trPr()
                th = OxmlElement("w:tblHeader")
                th.set(qn("w:val"), "true")
                trpr.append(th)
                stats["tables"] += 1
                stats["table_rows"] += len(rows)
                doc.add_paragraph().paragraph_format.space_after = Pt(4)
            continue

        # —— 水平线 ——
        if re.match(r"^ {0,3}([-*_])\s*(\1\s*){2,}$", s):
            stats["hr"] += 1
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(8)
            para_border(p, bottom={"sz": 6, "color": "D8DCE3", "space": 1})
            i += 1                     # ← 别忘了它！漏掉就是死循环（真踩过）
            continue

        # —— 标题 ——
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lvl = len(m.group(1))
            stats["headings"] += 1
            p = doc.add_paragraph(style=f"Heading {min(lvl, 4)}")
            add_inline(p, m.group(2), size={1: 21, 2: 15.5, 3: 11.5, 4: 10.5}[min(lvl, 4)],
                       ea=EA_HEAD, latin=LATIN_HEAD, base_bold=True)
            for r in p.runs:
                r.font.color.rgb = HEAD_COLOR
            i += 1
            continue

        # —— 引用 ——
        if s.startswith("> "):
            stats["quotes"] += 1
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Cm(0.7)
            pf.space_before = Pt(3)
            pf.space_after = Pt(3)
            para_border(p, left={"sz": 18, "color": "9BB0C9", "space": 6})
            shade(p._element, QUOTE_BG)
            add_inline(p, s[2:], size=10, color=None)
            for r in p.runs:
                r.font.color.rgb = RGBColor(0x44, 0x4A, 0x55)
            i += 1
            continue

        # —— 列表（保留原 marker，悬挂缩进；不用 Word 自动编号，避免跨列表串号）——
        m = re.match(r"^(\s*)([-*+]|\d+[.、)])\s+(.*)$", s)
        if m:
            stats["lists"] += 1
            indent = len(m.group(1)) // 2
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Cm(0.75 + indent * 0.6)
            pf.first_line_indent = Cm(-0.55)
            pf.space_after = Pt(2)
            add_inline(p, f"{m.group(2)}　{m.group(3)}", size=10.5)
            i += 1
            continue

        # —— 正文 ——
        p = doc.add_paragraph()
        # 保留行首全角空格（体例里用它做层级），但去掉半角前导空白
        text = raw.rstrip()
        lead = len(text) - len(text.lstrip("\u3000"))
        if lead:
            set_font(p.add_run("\u3000" * lead))
            text = text.lstrip("\u3000")
        add_inline(p, text)
        i += 1

    doc.save(str(OUT))
    stats["seconds"] = round(time.time() - t0, 1)
    stats["han"] = han
    stats["entries"] = n_entries
    return stats


def main() -> int:
    if not SRC.exists():
        print(f"找不到 {SRC}")
        return 1
    st = convert()
    lines = [
        "洄文大字典 · Markdown → Word 转换报告",
        "=" * 46,
        f"源文件   : {SRC.name}",
        f"输出     : {OUT.name}  ({OUT.stat().st_size / 1024:.0f} KB)",
        f"用时     : {st['seconds']} 秒",
        "",
        f"汉字      : {st['han']:,}",
        f"词条      : {st['entries']:,}",
        f"标题      : {st['headings']:,}",
        f"粗体      : {st['bold'] or '（随行内解析处理）'}",
        f"表格      : {st['tables']:,} 张，共 {st['table_rows']:,} 行",
        f"代码块    : {st['fences'] // 2:,} 块",
        f"引用      : {st['quotes']:,}",
        f"列表项    : {st['lists']:,}",
        f"分隔线    : {st['hr']:,}",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
