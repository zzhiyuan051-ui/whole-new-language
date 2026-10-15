#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给《洄文大字典》DOCX 写入正确的文档属性。

为什么需要这一步
----------------
python-docx 生成的 DOCX，docProps 里全是它模板的默认值：

    dc:creator     = "python-docx"
    dc:title       = （空）
    dcterms:created= 2013-12-23   ← python-docx 打包时带的模板日期
    Application    = "Microsoft Macintosh Word"
    Pages = 1, Words = 0

于是**在 Word 的"文件 → 信息"里、或在资源管理器里看这个文件**，
会显示成「作者：python-docx」「共 1 页」「创建于 2013 年」。
内容再好，这一栏也是错的。

本脚本只改 docProps 两个部件，不碰 word/document.xml。

用法：
  python tools/docx_metadata.py --dry-run     # 只看，不改
  python tools/docx_metadata.py               # 写入（会先备份）
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DOCX = ROOT / "dict" / "洄文大字典.docx"

TITLE = "洄文大字典"
SUBJECT = "一部人造语言的字典与教程"
CREATOR = "The Huiwen (洄文) Project"
KEYWORDS = "洄文;Huiwen;人造语言;自源文字;图语法;字典"
DESCRIPTION = ("洄文（Huiwen）——自源文字与图语法的人造语言。"
               "全书含教程五编二十课与 3,136 条词条。"
               "https://github.com/zzhiyuan051-ui/whole-new-language")

# 这些统计由 Word 自己重算；这里填真值，免得别人在没打开过的情况下看到 0。
# 数值取自转码时的 Word COM 实测（见 dict/_转换报告.txt）。
STATS = {
    "Pages": "2704",
    "Words": "1968272",
    "Characters": "2428179",
    "Paragraphs": "100944",
    "Lines": "0",
    "CharactersWithSpaces": "2428179",
}


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def set_tag(xml: str, tag: str, value: str) -> str:
    """有则替换内容，无则在根元素开标签后插入。"""
    pat = re.compile(r"(<%s(?:\s[^>]*)?>)(.*?)(</%s>)" % (tag, tag), re.S)
    if pat.search(xml):
        return pat.sub(lambda m: m.group(1) + esc(value) + m.group(3), xml, count=1)
    return xml


def upsert(xml: str, tag: str, value: str, root: str) -> str:
    if re.search(r"<%s(?:\s[^>]*)?>" % tag, xml):
        return set_tag(xml, tag, value)
    m = re.search(r"<%s(?:\s[^>]*)?>" % root, xml)
    if not m:
        return xml
    return xml[:m.end()] + "<%s>%s</%s>" % (tag, esc(value), tag) + xml[m.end():]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--docx", type=Path, default=DOCX)
    args = ap.parse_args()

    path: Path = args.docx
    if not path.exists():
        sys.exit(f"找不到 {path}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # 源 Markdown 的 mtime 作为「创建时间」更诚实
    src = ROOT / "dict" / "洄文大字典.md"
    created = (datetime.fromtimestamp(src.stat().st_mtime, timezone.utc)
               .strftime("%Y-%m-%dT%H:%M:%SZ") if src.exists() else now)

    print("=" * 68)
    print(f"目标：{path}")
    print("=" * 68)

    with zipfile.ZipFile(path) as z:
        core = z.read("docProps/core.xml").decode("utf-8")
        app = z.read("docProps/app.xml").decode("utf-8")

    print("改写前：")
    for tag in ("dc:title", "dc:creator", "dc:subject", "dcterms:created"):
        m = re.search(r"<%s[^>]*>([^<]*)</%s>" % (tag, tag), core)
        print(f"  {tag:<18} {m.group(1) if m else '(无)'}")
    for tag in ("Application", "Pages", "Words"):
        m = re.search(r"<%s>([^<]*)</%s>" % (tag, tag), app)
        print(f"  {tag:<18} {m.group(1) if m else '(无)'}")

    # ---- core.xml ----
    core = upsert(core, "dc:title", TITLE, "cp:coreProperties")
    core = upsert(core, "dc:subject", SUBJECT, "cp:coreProperties")
    core = upsert(core, "dc:creator", CREATOR, "cp:coreProperties")
    core = upsert(core, "cp:lastModifiedBy", CREATOR, "cp:coreProperties")
    core = upsert(core, "dc:description", DESCRIPTION, "cp:coreProperties")
    core = upsert(core, "cp:keywords", KEYWORDS, "cp:coreProperties")
    core = upsert(core, "cp:category", "人造语言 / Constructed language",
                  "cp:coreProperties")
    core = set_tag(core, "dcterms:created", created)
    core = set_tag(core, "dcterms:modified", now)
    # created/modified 需要 xsi:type 属性，缺了 Word 会抱怨
    core = re.sub(r'<dcterms:created>',
                  '<dcterms:created xsi:type="dcterms:W3CDTF">', core)
    core = re.sub(r'<dcterms:modified>',
                  '<dcterms:modified xsi:type="dcterms:W3CDTF">', core)

    # ---- app.xml ----
    app = set_tag(app, "Application", "Microsoft Office Word")
    app = re.sub(r"<AppVersion>.*?</AppVersion>", "<AppVersion>16.0000</AppVersion>",
                 app)
    for tag, val in STATS.items():
        app = set_tag(app, tag, val)
    app = set_tag(app, "Company", CREATOR)
    app = set_tag(app, "TotalTime", "6")

    print()
    print("改写后：")
    for tag in ("dc:title", "dc:creator", "dc:subject", "dcterms:created"):
        m = re.search(r"<%s[^>]*>([^<]*)</%s>" % (tag, tag), core)
        print(f"  {tag:<18} {m.group(1) if m else '(无)'}")
    for tag in ("Application", "Pages", "Words"):
        m = re.search(r"<%s>([^<]*)</%s>" % (tag, tag), app)
        print(f"  {tag:<18} {m.group(1) if m else '(无)'}")

    if args.dry_run:
        print("\n--dry-run：未改动任何文件。")
        return 0

    backup = path.with_suffix(".docx.bak")
    shutil.copy2(path, backup)
    print(f"\n已备份 → {backup.name}")

    # 重写 zip：保留原压缩方式，只替换两个部件
    tmp = path.with_suffix(".docx.tmp")
    with zipfile.ZipFile(path) as zin, \
            zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == "docProps/core.xml":
                zout.writestr(item, core.encode("utf-8"))
            elif item.filename == "docProps/app.xml":
                zout.writestr(item, app.encode("utf-8"))
            else:
                zout.writestr(item, zin.read(item.filename))
    tmp.replace(path)

    # 复验：读回，并确认正文部件未被破坏
    print("\n复验：")
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        print(f"  ZIP 完整性     : {'损坏: ' + str(bad) if bad else 'OK'}")
        doc = z.read("word/document.xml")
        print(f"  document.xml   : {len(doc):,} 字节")
        print(f"  段落数         : {len(re.findall(rb'<w:p[ >]', doc)):,}")
        print(f"  表格数         : {len(re.findall(rb'<w:tbl>', doc)):,}")
        c2 = z.read("docProps/core.xml").decode("utf-8")
        m = re.search(r"<dc:creator[^>]*>([^<]*)</dc:creator>", c2)
        print(f"  dc:creator     : {m.group(1) if m else '(无)'}")
    font = ROOT / "font" / "GalHuiwen.ttf"
    print(f"\n提示：如需回退，用 {backup.name} 覆盖回去。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
