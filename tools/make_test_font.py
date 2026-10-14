#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实验：把洄文字体"顶替"成一个 Chromium 一定会请求的家族名。

思路
----
Chromium 不对私用区做字体回退，但它**会**按 CSS 里写的家族名去系统字体集里查。
如果系统里存在一个名为「Microsoft YaHei」的字体、且它带有私用区字形，
那么当 QQ 的 CSS 写 `font-family: "Microsoft YaHei"` 时，Chromium 就会拿到含
洄文字形的那一份 —— 中文仍由真正的雅黑（或回退字体）画，洄文由我们画。

这是**实验**，不是成品：
  · 同名家族在系统里会有两份，DirectWrite 选谁不确定，必须实测；
  · 万一选错、影响中文显示，要立刻卸载。

本脚本只负责生成实验字体，不动系统。装/卸由 install_test_font.py 负责。
"""
from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "font" / "GalHuiwen.ttf"
OUT_DIR = ROOT / "tools"

# 要顶替的家族名（QQ/微信/浏览器在中文环境下最常请求的就是它）
TARGET_FAMILY = "Microsoft YaHei"
OUT_NAME = "GalAsYaHei-TEST.ttf"


def main() -> int:
    f = TTFont(str(SRC), lazy=False)
    name = f["name"]

    ps = "GalHuiwenAsYaHeiTEST"
    full = f"{TARGET_FAMILY} Huiwen TEST"

    # nameID: 1=family 2=subfamily 3=unique 4=full 6=postscript 16=typo family 17=typo sub
    for nid, val in ((1, TARGET_FAMILY), (2, "Regular"), (3, f"{ps};1.0"),
                     (4, full), (6, ps), (16, TARGET_FAMILY), (17, "Regular")):
        for rec in list(name.names):
            if rec.nameID == nid:
                name.names.remove(rec)
        name.setName(val, nid, 3, 1, 0x409)      # Windows, English
        name.setName(val, nid, 1, 0, 0)          # Mac, Roman

    out = OUT_DIR / OUT_NAME
    f.save(str(out))

    # 回读确认
    g = TTFont(str(out), lazy=True)
    gn = g["name"]
    def get(nid):
        r = gn.getDebugName(nid)
        return r
    print(f"已生成 {out}  ({out.stat().st_size / 1024:.0f} KB)")
    print(f"  family(1)     = {get(1)!r}")
    print(f"  subfamily(2)  = {get(2)!r}")
    print(f"  fullName(4)   = {get(4)!r}")
    print(f"  psName(6)     = {get(6)!r}")
    cmap = g.getBestCmap()
    cps = sorted(cmap.keys())
    print(f"  cmap 覆盖 {len(cps)} 个码位: U+{cps[0]:04X}..U+{cps[-1]:04X}")
    print(f"\n下一步：用 install_test_font.py install 装上，然后在 Edge 里看测试页。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
