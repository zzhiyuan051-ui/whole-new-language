#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给已生成的字体补齐 Unicode 官方要求的 name 表字段（原地打补丁）。

为什么需要这个脚本
------------------
Unicode Consortium 的《Font Submission Policy》明确要求字体文件里**必须**包含
版权、厂商、设计者、许可说明等信息，而且给出了精确的读写要求：

    The values for the name IDs above must be present for platform ID 3 "Windows",
    encoding ID 1 "Unicode BMP" and languageID 1033 "en-US".

也就是 **platformID=3, platEncID=1, langID=0x409** 这组记录**必须存在**，
其他平台/语言的同名记录值必须与之一致。

`hwfont.py` 生成字体时写了 familyName/styleName/fullName/psName/version/copyright，
但**没有**写官方点名要的这几项：

    name ID 8   Manufacturer Name     厂商名
    name ID 9   Designer              设计者
    name ID 13  License Description   许可说明
    name ID 14  License Info URL      许可信息地址

本脚本在不重新生成字形的前提下补齐这些字段（重新生成要跑整条字形链，慢且无必要）。

用法
----
    # 预览将要写入什么，不改文件
    python huiwen/tools/hwfont_license.py --dry-run

    # 真的打补丁（会先备份成 GalHuiwen.ttf.bak）
    python huiwen/tools/hwfont_license.py

    # 指定其他字体文件
    python huiwen/tools/hwfont_license.py --font path/to/x.ttf
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("需要 fontTools：python -m pip install fonttools")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_FONT = ROOT / "font" / "GalHuiwen.ttf"

# 许可与署名信息（与仓库根目录的 LICENSE / LICENSE-FONT 保持一致）
#
# ⚠️ 两个必须注意的点：
#   1. OFL 1.1 要求版权声明里出现明确的「Copyright」字样与年份 ——
#      `<copyright notice>` 是 OFL 正文里的占位符，写全才成立。
#   2. 这里**不要**改字体名（familyName 的 "GalHuiwen"）。OFL 的
#      Reserved Font Name 机制：一旦用某个名字发布，衍生版本就不得沿用该名。
#      改名只在发布 fork 时做，不是在这里做。
COPYRIGHT = "Copyright (c) 2026 The Huiwen (洄文) Project Authors"
MANUFACTURER = "The Huiwen (洄文) Project"
DESIGNER = "The Huiwen (洄文) Project Authors"
LICENSE_DESC = (
    "This Font Software is licensed under the SIL Open Font License, "
    "Version 1.1. This license is available with a FAQ at: "
    "https://openfontlicense.org"
)
# 用 openfontlicense.org（OFL 官方站，稳定）而不是原始 .txt 的深链接 ——
# 那个路径在 SIL 站点改版后 404 过。
LICENSE_URL = "https://openfontlicense.org"
VENDOR_URL = "https://github.com/"

# OpenType name ID → 要写入的值
# 官方点名必需的是 0 / 8 / 9 / 13；14 与 11 为强烈建议。
# 注意：这里用**整数 name ID 作键**——fontTools 的 setName 直接收整数，
# 不存在字符串键的映射表（踩过，见下方注释）。
FIELDS: dict[int, str] = {
    0: COPYRIGHT,             # Copyright notice
    8: MANUFACTURER,          # Manufacturer Name
    9: DESIGNER,              # Designer
    11: VENDOR_URL,           # Vendor URL
    13: LICENSE_DESC,         # License Description
    14: LICENSE_URL,          # License Info URL
}

REQUIRED_IDS = {0, 8, 9, 13}


def read_name(font: TTFont, nid: int, plat: int = 3, enc: int = 1,
              lang: int = 0x409) -> str | None:
    for rec in font["name"].names:
        if rec.nameID == nid and rec.platformID == plat \
                and rec.platEncID == enc and rec.langID == lang:
            try:
                return rec.toUnicode()
            except Exception:                      # noqa: BLE001
                return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="补齐字体的许可 name 表字段")
    ap.add_argument("--font", type=Path, default=DEFAULT_FONT)
    ap.add_argument("--dry-run", action="store_true", help="只看结果，不改文件")
    args = ap.parse_args()

    path: Path = args.font
    if not path.exists():
        sys.exit(f"找不到字体：{path}")

    font = TTFont(str(path), lazy=False)

    print("=" * 66)
    print(f"字体：{path}")
    print(f"字体名(1/2)：{font['name'].getDebugName(1)} / {font['name'].getDebugName(2)}")
    print("=" * 66)
    print("补丁前（platformID=3, encID=1, langID=0x409）：")
    for nid, label in ((0, "Copyright"), (8, "Manufacturer"), (9, "Designer"),
                       (13, "License Description"), (14, "License Info URL")):
        v = read_name(font, nid)
        mark = "  " if v else "❌"
        print(f"  {mark} ID {nid:<2} {label:<20} {v if v else '(缺失)'}")

    if args.dry_run:
        print("\n--dry-run：将写入以下字段")
        for nid, val in sorted(FIELDS.items()):
            print(f"  ID {nid:<2} = {val}")
        print("\n未改动任何文件。")
        return 0

    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"\n已备份原字体 → {backup.name}")

    name_tbl = font["name"]
    # ⚠️ 踩过的坑（两个都是凭记忆写错的，已按 fontTools 4.66 源码改正）：
    #
    #   1. setName 的签名是
    #        setName(string, nameID, platformID, platEncID, langID)
    #      signature 实测确认；参数顺序不是"nameID 在前"。
    #   2. **没有 nameIDs 这个属性**（AttributeError 实测）。
    #      nameID 直接传整数即可，源码里 `namerecord = self.getName(nameID, ...)`。
    #
    # setName 本身是"有则改、无则加"，所以它已经幂等；再配 removeNames 清掉
    # 非 Windows 平台的同名残留，避免跨平台不一致（官方要求各平台取值必须相同）。
    def replace(nid: int, text: str) -> None:
        name_tbl.removeNames(nameID=nid)
        name_tbl.setName(text, nid, 3, 1, 0x409)   # Windows / Unicode BMP / en-US

    for nid, text in FIELDS.items():
        replace(nid, text)

    # 先在内存里编译一遍，编译得过再落盘 —— 不让写坏源文件
    try:
        font["name"].compile(font)
    except Exception as exc:                       # noqa: BLE001
        sys.exit(f"name 表编译失败，**未改动任何文件**：{exc}")

    font.save(str(path))
    font.close()

    # 读回来验证 —— 不验证不算做完
    chk = TTFont(str(path), lazy=True)
    print("\n验证（读回刚写入的文件）：")
    ok = True
    for nid in sorted(REQUIRED_IDS):
        v = read_name(chk, nid)
        good = bool(v)
        ok &= good
        print(f"  {'✓' if good else '❌'} ID {nid:<2} {'已写入' if good else '仍缺失'}"
              f"  {v[:64] + '…' if v and len(v) > 64 else (v or '')}")
    # 跨平台一致性：官方要求其他平台/语言的同名值必须相同
    for nid in sorted(REQUIRED_IDS):
        vals = {r.toUnicode() for r in chk["name"].names if r.nameID == nid}
        if len(vals) > 1:
            ok = False
            print(f"  ❌ ID {nid} 各平台取值不一致：{vals}")
    chk.close()

    print("=" * 66)
    print("结论：" + ("全部必需字段就位，且跨平台一致。" if ok
                     else "仍有问题，见上方 ❌。"))
    print(f"提示：如需回退，用 {backup.name} 覆盖回去即可。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
