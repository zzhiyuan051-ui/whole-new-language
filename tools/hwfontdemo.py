#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 字体渲染验证

把 GalHuiwen.ttf 子集化后以 @font-face 内嵌进 SVG/HTML，用它渲染一段洄文——
既不依赖系统安装字体，也顺带证明字体本身可用（glyf/cmap 都对）。

输出：
  font/demo.html      可直接双击打开的演示页（内嵌字体，离线可用）
  font/subset.ttf     子集（只含演示用到的字），体积很小
  font/demo.svg       同一段文字的静态图
"""
from __future__ import annotations

import base64
import csv
import json
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FONT = ROOT / "font"
PUA = 0xE000

TEXT_ZH = "我爱你 · 雨夜 · 现实与真 · 洄文大字典"


def main() -> None:
    lex = {}
    for l in (ROOT / "lexicon.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        f = l.split("\t")
        if len(f) > 16:
            lex[f[9]] = f          # 汉字 → 行

    # 选要演示的字：优先「我爱你」，再补几个
    wanted_zh = ["爱", "我", "你", "雨", "夜", "现", "实", "真", "同", "文", "大", "字", "典", "与"]
    keep_cp, lines = [], []
    for zh in wanted_zh:
        r = lex.get(zh)
        if not r:
            continue
        cp = PUA + int(r[16])
        keep_cp.append(cp)
        lines.append((zh, r[1], r[2], cp))

    # 子集化
    f = TTFont(str(FONT / "GalHuiwen.ttf"))
    opt = Options()
    opt.layout_features = []
    opt.name_IDs = ["*"]
    opt.notdef_outline = True
    opt.recalc_bounds = True
    sub = Subsetter(options=opt)
    sub.populate(unicodes=keep_cp)
    sub.subset(f)
    f.save(str(FONT / "subset.ttf"))
    b64 = base64.b64encode((FONT / "subset.ttf").read_bytes()).decode()

    # 渲染文本（用 PUA 字符）
    run = "".join(chr(c) for _, _, _, c in lines[:3]) + "　" + \
          "".join(chr(c) for _, _, _, c in lines[3:9])
    style = ("@font-face{font-family:'GalHuiwen';"
             f"src:url(data:font/ttf;base64,{b64}) format('truetype');}}"
             ".gh{font-family:'GalHuiwen';}")
    html = f"""<!doctype html><meta charset="utf-8">
<title>洄文 · 字体演示</title>
<style>
 body{{background:#fbfaf7;color:#1b1b1f;font-family:system-ui,'Microsoft YaHei';padding:36px;line-height:1.7}}
 h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#7d786f;font-size:13px;margin-bottom:24px}}
 .big{{font-size:96px;letter-spacing:.12em;margin:18px 0}}
 table{{border-collapse:collapse;margin-top:20px}} td,th{{border:1px solid #e2ded6;padding:6px 12px;font-size:14px}}
 th{{background:#f2efe9;text-align:left}} .pua{{font-size:44px;vertical-align:middle}}
 code{{background:#f2efe9;padding:1px 5px;border-radius:3px}}
</style>
<style>{style}</style>
<h1>洄文 · 字体演示</h1>
<div class="sub">GalHuiwen.ttf ｜ 码位在私用区 U+E000 起 ｜ 本页内嵌子集字体，离线可用</div>

<div class="gh big">{run}</div>

<table>
<tr><th>汉字</th><th>词形</th><th>音节</th><th>码位</th><th>字形</th></tr>
{"".join(f'<tr><td>{zh}</td><td>{form}</td><td><code>{syll}</code></td>'
         f'<td><code>U+{cp:04X}</code></td>'
         f'<td class="gh pua">{chr(cp)}</td></tr>' for zh, form, syll, cp in lines)}
</table>

<p style="margin-top:24px;color:#7d786f;font-size:13px">
提示：上面大字与表格末列的方块，就是字体渲染出来的洄文字形。<br>
若方块显示为空白，说明字体没被加载——请用 Chromium 内核浏览器打开。
</p>
"""
    (FONT / "demo.html").write_text(html, encoding="utf-8")

    # 静态 SVG
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="150">'
           f'<style>{style}</style>'
           f'<rect width="100%" height="100%" fill="#fbfaf7"/>'
           f'<text x="20" y="105" class="gh" font-size="90" fill="#1b1b1f">{run}</text>'
           f'</svg>')
    (FONT / "demo.svg").write_text(svg, encoding="utf-8")

    print(f"子集字体：{len(keep_cp)} 个字形 → font/subset.ttf"
          f"（{(FONT / 'subset.ttf').stat().st_size // 1024} KB）")
    print(f"演示页 → font/demo.html（内嵌字体 {len(b64) // 1024} KB）")
    print(f"静态图 → font/demo.svg")
    print("演示文字：", "".join(zh for zh, *_ in lines))


if __name__ == "__main__":
    main()
