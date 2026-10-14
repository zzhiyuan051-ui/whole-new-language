#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 全链路自检

一步步跑完整条流水线，任何一步不通过就如实报出。可随时重跑：
    python tools/hwselftest.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY = sys.executable

STEPS = [
    ("音系：生成音节表（624）", [PY, str(HERE / "syllabary.py")]),
    ("音系：生成各场工单", [PY, str(HERE / "make_work_orders.py")]),
    ("词法：生成派生词", [PY, str(HERE / "hwderive.py")]),
    ("词表：编译草稿 → lexicon（3000）", [PY, str(HERE / "hwcompile.py")]),
    ("字符：生成字表（15000）", [PY, str(HERE / "hwcharset.py")]),
    ("词表：生成人读词典", [PY, str(HERE / "hwdict.py")]),
    ("字形：分页字表 + 分类字表", [PY, str(HERE / "hwtables.py")]),
    ("字形：生成字体 GalHuiwen.ttf", [PY, str(HERE / "hwfont.py")]),
    ("字形：字体保真度校验（占格比例）", [PY, str(HERE / "hwfontcheck.py")]),
    ("字形：字体演示页（内嵌子集）", [PY, str(HERE / "hwfontdemo.py")]),
    ("字形：应用图标", [PY, str(HERE / "hwicon.py")]),
    ("字形：辨识度实测", [PY, str(HERE / "hwlegibility.py")]),
    ("字体：GDI 可用性验证（系统能否取到字形）",
     [PY, str(HERE / "hwfontinstall.py"), "verify"]),
    ("输入法：词表 → TSF 数据表", [PY, str(HERE / "hwmake_tsf_data.py")]),
    ("输入法：TSF 文本服务 COM 自检", [str(ROOT / "tsf" / "out" / "hwimetool.exe"),
                                 "selftest"]),
    ("输入法：端到端自检（引擎/上屏/导出）",
     [PY, str(ROOT / "ime" / "selftest.py")]),
    ("语法：解析器自检", [PY, str(HERE / "hwlang.py")]),
    ("字典：词根条目（480）", [PY, str(HERE / "hwroot_dict.py")]),
    ("字典：派生词条目（2488）", [PY, str(HERE / "hwderived_dict.py")]),
    ("字典：虚词条目（32）", [PY, str(HERE / "hwfunction_dict.py")]),
    ("字典：合成全书", [PY, str(HERE / "hwbook.py")]),
]


def run(title: str, cmd: list[str]) -> bool:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT))
    ok = r.returncode == 0
    tail = [l for l in (r.stdout or "").strip().splitlines() if l.strip()][-3:]
    print(f"[{'通过' if ok else '失败'}] {title}")
    for l in tail:
        print(f"        {l}")
    if not ok:
        for l in (r.stderr or "").strip().splitlines()[-6:]:
            print(f"        ! {l}")
    return ok


def main() -> int:
    print("=" * 70)
    print("洄文 · 全链路自检")
    print("=" * 70)
    bad = []
    for title, cmd in STEPS:
        if not run(title, cmd):
            bad.append(title)

    # 字表与词表的一致性
    import json
    chars = json.loads((ROOT / "characters.json").read_text(encoding="utf-8"))
    lex = (ROOT / "lexicon.tsv").read_text(encoding="utf-8").splitlines()
    head = lex[0].split("\t")
    rows = [dict(zip(head, l.split("\t"))) for l in lex[1:] if l.strip()]
    defined = [c for c in chars["characters"] if c["status"] == "defined"]
    print(f"[{'通过' if len(defined) == len(rows) else '失败'}] "
          f"字表与词表一致：字符 {len(defined)} / 词 {len(rows)}")
    if len(defined) != len(rows):
        bad.append("字表与词表不一致")
    mismatch = [c for c in defined if c["class_no"] != c["glyph"] % 44]
    print(f"[{'通过' if not mismatch else '失败'}] 字形与语义类对齐（glyph mod 44 = class）")
    if mismatch:
        bad.append("字形与类不符")

    # 字典例句里的每一个音节都必须是真实存在的音节
    # （这条校验来自一次真实事故：虚词换调后，例句模板里的旧音节没跟着改，
    #   生成了一批发不出来的「伪音节」）
    import re as _re2
    import syllabary as _S
    valid = {c["syll"] for c in _S.all_syllables()}
    bogus: dict[str, int] = {}
    n_ex = 0
    for d in ("entries", "entries-derived", "entries-function"):
        for f in (ROOT / "dict" / d).glob("*.md"):
            t = f.read_text(encoding="utf-8")
            n_ex += t.count("洄文　`")
            for s in _re2.findall(r"@\d+\s+([a-z]+[0-9]?)(?:\.|　|\s|\])", t):
                if s not in valid:
                    bogus[s] = bogus.get(s, 0) + 1
    ok = not bogus
    print(f"[{'通过' if ok else '失败'}] 字典例句音节全部合法"
          f"（{n_ex} 则例句，伪音节 {len(bogus)} 种）")
    if not ok:
        bad.append("字典例句含伪音节：" + "、".join(list(bogus)[:5]))
        for k, v in sorted(bogus.items(), key=lambda x: -x[1])[:6]:
            print(f"        ! {k} 出现 {v} 次")

    # 辨识度指标：同骨架且同家族的近形词，每个词平均摊到几个
    import subprocess as _sp
    r = _sp.run([PY, str(HERE / "hwlegibility.py")], capture_output=True, text=True,
                encoding="utf-8", errors="replace", cwd=str(ROOT))
    txt = r.stdout or ""
    import re as _re3
    # 只取「修复后」那一段（同骨架且同家族才计），别抓到「修复前」
    seg = txt.split("修复后")[-1] if "修复后" in txt else txt
    m = _re3.search(r"相差 ≤2：(\d+) 对 → 每词平均摊到 ([\d.]+) 个", seg)
    m3 = _re3.search(r"相差 ≤3：(\d+) 对 → 每词平均摊到 ([\d.]+) 个", seg)
    if m and m3:
        v2, v3 = float(m.group(2)), float(m3.group(2))
        good = v2 <= 1.0 and v3 <= 3.0
        print(f"[{'通过' if good else '失败'}] 字形辨识度：同家族近形词"
              f" ≤2 笔 {v2} 个/词｜≤3 笔 {v3} 个/词（阈值 1.0 / 3.0）")
        if not good:
            bad.append(f"字形辨识度不足（≤2 笔 {v2} 个/词）")
    else:
        print("[跳过] 字形辨识度（未取到指标）")

    # 范文
    import hwlang as L
    lexd = L.load_lexicon(ROOT / "lexicon.tsv")
    texts = sorted((ROOT / "texts").glob("*.hw"))
    total_g = total_r = 0
    for t in texts:
        graphs = L.parse_document(t.read_text(encoding="utf-8"))
        for gi, g in enumerate(graphs, 1):
            L.attach(g, lexd)
            L.fill_roles(g, lexd)
            errs = L.validate(g, lexd)
            total_g += 1
            total_r += len(g.rels)
            print(f"[{'通过' if not errs else '失败'}] 范文 {t.name} 第 {gi} 图"
                  f"（{g.title or '—'}）结 {len(g.nodes)} 弓 {len(g.rels)}")
            for e in errs:
                print(f"        ! {e}")
            if errs:
                bad.append(f"{t.name}#{gi}")

    print("-" * 70)
    print(f"音节 624｜词 {len(rows)}｜字符 {chars['target']}"
          f"（已定义 {chars['defined']} + 备用 {chars['reserved']}）"
          f"｜范文 {len(texts)} 篇 / {total_g} 图 / {total_r} 弓")

    # 全书字数（本轮验收口径）
    import re as _re
    CJK = _re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
    book = ROOT / "dict" / "洄文大字典.md"
    if book.exists():
        n = len(CJK.findall(book.read_text(encoding="utf-8")))
        n_ent = (len(list((ROOT / "dict" / "entries").glob("*.md")))
                 + len(list((ROOT / "dict" / "entries-derived").glob("*.md")))
                 + len(list((ROOT / "dict" / "entries-function").glob("*.md"))))
        n_les = len(list((ROOT / "course").glob("*.md")))
        print(f"全书 {n} 字（目标 700000，达成 {n / 700000 * 100:.0f}%）"
              f"｜教程 {n_les} 篇｜词条 {n_ent} 条")
        if n < 700000:
            bad.append(f"全书字数不足（{n} < 700000）")
            print("[失败] 全书字数未达 700000")
        else:
            print("[通过] 全书字数达标")
    print("=" * 70)
    if bad:
        print(f"自检未通过：{len(bad)} 处 —— " + "；".join(bad[:8]))
        return 1
    print("自检全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
