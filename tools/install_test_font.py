#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""装卸"顶替家族名"的实验字体（按用户级，不需要管理员，随时可卸）。

按用户级装的理由：这是实验，可能影响中文显示，必须能一键撤掉。
用户级注册在 HKCU，删除 key + 删文件即可，不动系统。
"""
from __future__ import annotations

import ctypes
import shutil
import sys
import winreg
from pathlib import Path
from ctypes import wintypes

HERE = Path(__file__).resolve().parent
SRC = HERE / "GalAsYaHei-TEST.ttf"
FONT_FILE = "GalAsYaHei-TEST.ttf"
FAMILY = "Microsoft YaHei"
DEST_DIR = Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
FONTS_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
REG_NAME = f"{FAMILY} Huiwen TEST (TrueType)"

gdi32 = ctypes.WinDLL("gdi32")
user32 = ctypes.WinDLL("user32")
FR_PRIVATE = 0x10
FR_NOT_ENUM = 0x20
HWND_BROADCAST = 0xFFFF
WM_FONTCHANGE = 0x001D


def broadcast_font_change() -> None:
    # SendMessageW 在 user32 里，不在 gdi32（第一次写错，报 function not found）
    user32.SendMessageW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0)


def install() -> int:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    dst = DEST_DIR / FONT_FILE
    shutil.copy2(SRC, dst)
    print(f"复制到 {dst}")

    n = gdi32.AddFontResourceExW(str(dst), FR_PRIVATE, 0)
    print(f"AddFontResourceEx -> {n}  {'成功' if n else '失败'}")

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, FONTS_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, REG_NAME, 0, winreg.REG_SZ, str(dst))
    print("已写 HKCU 字体登记")
    broadcast_font_change()      # WM_FONTCHANGE broadcast
    print("\n已安装（实验）。现在刷新 Edge 里的测试页看效果。")
    print("看完用：python install_test_font.py uninstall")
    return 0


def uninstall() -> int:
    dst = DEST_DIR / FONT_FILE
    if dst.exists():
        gdi32.RemoveFontResourceExW(str(dst), FR_PRIVATE, 0)
        dst.unlink()
        print(f"已删除 {dst}")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, FONTS_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, REG_NAME)
        print("已删 HKCU 登记")
    except FileNotFoundError:
        print("HKCU 里没有该登记（已清）")
    broadcast_font_change()
    print("已卸载。")
    return 0


def main() -> int:
    if not SRC.exists():
        print(f"找不到 {SRC}，先跑 make_test_font.py")
        return 1
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    return install() if action == "install" else uninstall()


if __name__ == "__main__":
    raise SystemExit(main())
