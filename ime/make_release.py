#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把输入法打包成一个可下载的发布包。

输入：dist/洄文输入法/（PyInstaller onedir 的产物）
输出：dist/洄文输入法-<版本>-win64.zip

包里放：程序本体 + 使用说明 + 独立字体文件 + 界面截图。
独立字体是给「想让别的程序也能显示洄文」的用户准备的（自己双击安装）。
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
APP = DIST / "洄文输入法"
IME = ROOT / "ime"
VERSION = "1.0"
NAME = f"洄文输入法-{VERSION}-win64"

STAGE = DIST / NAME


def main() -> None:
    if not (APP / "洄文输入法.exe").exists():
        raise SystemExit(f"没找到打包产物：{APP / '洄文输入法.exe'}；先跑 PyInstaller")

    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    # 1) 程序本体
    shutil.copytree(APP / "_internal", STAGE / "_internal")
    shutil.copy2(APP / "洄文输入法.exe", STAGE / "洄文输入法.exe")

    # 2) 文档
    shutil.copy2(IME / "README.md", STAGE / "使用说明.md")
    (STAGE / "安装说明.txt").write_text(
        "洄文输入法 1.0\n"
        "========================================\n\n"
        "【怎么开始用】\n"
        "  双击「洄文输入法.exe」即可，不需要安装，也不需要装 Python。\n"
        "  （整个文件夹一起拷走就能用，别只拷 exe。）\n\n"
        "【怎么打字】\n"
        "  在顶部输入框里打 za3 → 出候选 → 按 1 或回车选中。\n"
        "  · 音节：za3 = 爱、yy4 = 雨、yy4 di6 = 雨具\n"
        "  · 前缀：打 za 会列出所有 za 开头的音节\n"
        "  · 汉字：直接打「爱」也能反查出洄文词\n\n"
        "【上屏后怎么用】\n"
        "  · 「复制洄文」拷到剪贴板；别的程序需要装了 GalHuiwen.ttf 才显示字形\n"
        "  · 「导出 PNG」存成图片 —— 发给别人用这个，对方什么都不用装\n"
        "  · 「导出 SVG」矢量图，内嵌了字体，任何浏览器都能看\n"
        "  导出文件默认落在程序目录下的「洄文导出」文件夹里。\n\n"
        "【想在其他程序里也能显示洄文】\n"
        "  双击本文件夹里的 GalHuiwen.ttf，点「安装」。\n"
        "  码位在私用区 U+E000 起，连续、都在 BMP 内。\n"
        "  装上后，把目标程序的字体选成 GalHuiwen，复制出去的字才能显示。\n\n"
        "【这个 exe 不是系统级输入法】\n"
        "  它不会在微信、Word、浏览器里接管你的键盘。\n"
        "  用法是：在这里打好，复制走。\n"
        "  系统级那一份是 TSF 文本服务，要另装，并且安装时要一次管理员确认。\n\n"
        "【出问题怎么办】\n"
        "  程序若报错，会把详细报告写到「崩溃报告.txt」（和导出文件同目录）。\n",
        encoding="utf-8")

    # 3) 独立字体
    shutil.copy2(ROOT / "font" / "GalHuiwen.ttf", STAGE / "GalHuiwen.ttf")

    # 4) 界面截图
    shot = IME / "output" / "界面截图.png"
    if shot.exists():
        shutil.copy2(shot, STAGE / "界面截图.png")

    # 5) 压缩
    zpath = DIST / f"{NAME}.zip"
    if zpath.exists():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(STAGE.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(DIST))

    size = zpath.stat().st_size / 1024 / 1024
    files = sum(1 for p in STAGE.rglob("*") if p.is_file())
    print(f"发布目录 → {STAGE}（{files} 个文件）")
    print(f"发布包   → {zpath}（{size:.1f} MB）")
    print()
    print("包内结构：")
    for p in sorted(STAGE.rglob("*"))[:8]:
        rel = p.relative_to(STAGE)
        if p.is_file():
            print(f"  {rel}　{p.stat().st_size // 1024} KB")
        else:
            print(f"  {rel}\\")
    print("  ...")


if __name__ == "__main__":
    main()
