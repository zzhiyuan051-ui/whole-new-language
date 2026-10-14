#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 GalHuiwen.ttf 的 OS/2 ulUnicodeRange 是否声明了私用区覆盖。

为什么要查这个：
  输入法已经把字插进文档了（日志为证），但 QQ（Electron/DirectWrite）画不出来。
  引擎在决定「用哪个字体画这个码位」时会参考字体的 Unicode 覆盖声明。
  私用区（U+E000–U+F8FF）对应 ulUnicodeRange 的 bit 57。这一位没声明的话，
  某些引擎会认为这个字体「不负责这段码位」，于是根本不考虑它。
"""
from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont

FONT = Path(r"C:\Windows\Fonts\GalHuiwen.ttf")

NAMES = {
    0: "Basic Latin", 1: "Latin-1 Supplement", 2: "Latin Extended-A",
    3: "Latin Extended-B", 4: "IPA Extensions", 5: "Spacing Modifier Letters",
    6: "Combining Diacritical Marks", 7: "Greek and Coptic", 9: "Cyrillic",
    11: "Hebrew", 12: "Arabic", 15: "Devanagari", 24: "Thai",
    48: "CJK Symbols and Punctuation", 49: "Hiragana", 50: "Katakana",
    51: "Bopomofo", 52: "Hangul Compatibility Jamo", 54: "Enclosed CJK",
    56: "CJK Unified Ideographs", 57: "Private Use Area (私用区)",
    58: "CJK Strokes", 59: "Alphabetic Presentation Forms",
    60: "Arabic Presentation Forms-A", 61: "Combining Half Marks",
    62: "Vertical Forms", 63: "Small Form Variants",
    64: "Arabic Presentation Forms-B", 65: "Halfwidth and Fullwidth Forms",
    69: "Specials",
}


def main() -> int:
    f = TTFont(str(FONT), lazy=True)
    os2 = f["OS/2"]
    bits = (os2.ulUnicodeRange1 | (os2.ulUnicodeRange2 << 32)
            | (os2.ulUnicodeRange3 << 64) | (os2.ulUnicodeRange4 << 96))

    print(f"字体: {FONT}")
    print("\nOS/2 ulUnicodeRange 已声明的位:")
    any_bit = False
    for b in range(128):
        if (bits >> b) & 1:
            print(f"   bit {b:3d}  {NAMES.get(b, '(未命名)')}")
            any_bit = True
    if not any_bit:
        print("   （一位都没声明！）")

    print(f"\n私用区位(bit 57)是否声明: {'是' if (bits >> 57) & 1 else '否  ← 问题可能在这'}")

    cmap = f.getBestCmap()
    cps = sorted(cmap.keys())
    print(f"\ncmap 覆盖 {len(cps)} 个码位: U+{cps[0]:04X} .. U+{cps[-1]:04X}")
    print(f"  全部落在私用区: {all(0xE000 <= c <= 0xF8FF for c in cps)}")
    print(f"\nfsType = {os2.fsType}（0 = 可自由嵌入）")
    print(f"usWeightClass = {os2.usWeightClass}   usWidthClass = {os2.usWidthClass}")
    print(f"panose = {os2.panose.__dict__ if hasattr(os2, 'panose') else 'n/a'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
