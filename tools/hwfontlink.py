#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把洄文字体装成**系统级**字体，并建立「字体链接」。

要解决的具体问题：
  洄文用 Unicode 私用区（U+E000…）。私用区的码位**没有任何系统字体会去覆盖**，
  所以别的程序拿到这个字符只会画一个空心方格（tofu）。
  即使我们把自己的字体装好了，程序也不会自动改用它。

两条措施：
  1) 装到系统级（C:\\Windows\\Fonts + HKLM），让所有用户/进程都能用；
  2) 写 `FontLink\\SystemLink`：告诉 GDI「主字体缺字形时，去 GalHuiwen 里找」。
     这是 GDI 的字体回退机制，值名是**主字体名**，值是 MULTI_SZ，
     每项形如 `文件名.ttf,字体族名`。

诚实备注：SystemLink 是 **GDI** 的机制。用 DirectWrite 渲染的程序
（Win11 记事本、部分新应用）不一定吃这一套 —— 那类程序仍需手动选字体。
这一点没法靠注册表绕过去，实测为准。
"""
from __future__ import annotations

import ctypes
import shutil
import sys
import winreg
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FONT_SRC = ROOT / "font" / "GalHuiwen.ttf"
FAMILY = "GalHuiwen"
FONT_FILE = "GalHuiwen.ttf"
WIN_FONTS = Path(r"C:\Windows\Fonts")

# 要把洄文挂到哪些主字体后面。
# 覆盖常见的中英文界面字体、中文字体、等宽字体、Office 常用字体。
# **挂了不会有害** —— 只有当主字体**缺**这个字形时才会用到我们。
LINK_TARGETS = [
    # 中文（简体）
    "Microsoft YaHei", "Microsoft YaHei UI", "Microsoft YaHei Light",
    "微软雅黑", "微软雅黑 Light",
    "SimSun", "宋体", "NSimSun", "新宋体", "SimSun-ExtB",
    "SimHei", "黑体", "KaiTi", "楷体", "FangSong", "仿宋",
    "DengXian", "等线", "DengXian Light", "YouYuan", "幼圆", "LiSu", "隶书",
    # 中文（繁体）
    "Microsoft JhengHei", "Microsoft JhengHei UI", "微軟正黑體",
    "MingLiU", "細明體", "PMingLiU", "新細明體",
    # 华文系
    "STXihei", "华文细黑", "STSong", "华文宋体", "STKaiti", "华文楷体",
    "STFangsong", "华文仿宋", "STHeiti", "华文黑体",
    # 西文界面
    "Segoe UI", "Segoe UI Variable", "Segoe UI Semibold", "Segoe UI Light",
    "Tahoma", "Arial", "Arial Unicode MS", "Microsoft Sans Serif",
    "Verdana", "Calibri", "Calibri Light", "Times New Roman", "Georgia",
    "Trebuchet MS", "Comic Sans MS", "Impact", "Palatino Linotype",
    "Book Antiqua", "Garamond", "Franklin Gothic Book", "Century Gothic",
    # 等宽（编辑器/终端常用，最需要）
    "Consolas", "Lucida Console", "Courier New", "Cascadia Mono", "Cascadia Code",
    "MS Gothic", "MS Mincho", "Yu Gothic UI", "Yu Mincho",
    "Malgun Gothic", "Gulim", "Batang", "Nirmala UI",
]
LINK_VALUE = f"{FONT_FILE},{FAMILY}"

OUT = HERE / "font_link_result.txt"
lines: list[str] = []


def say(s: str) -> None:
    lines.append(s)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:                                      # noqa: BLE001
        return False


def install_system_font() -> bool:
    """把字体复制到 C:\\Windows\\Fonts 并在 HKLM 登记。"""
    if not FONT_SRC.exists():
        say(f"  源字体不存在：{FONT_SRC}")
        return False
    dst = WIN_FONTS / FONT_FILE
    try:
        if not dst.exists() or dst.stat().st_size != FONT_SRC.stat().st_size:
            shutil.copy2(FONT_SRC, dst)
            say(f"  已复制到 {dst}")
        else:
            say(f"  已存在于 {dst}（大小一致，跳过复制）")
    except OSError as e:
        say(f"  复制失败：{e}")
        return False

    key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
    try:
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key, 0,
                                winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, f"{FAMILY} (TrueType)", 0,
                              winreg.REG_SZ, FONT_FILE)
        say("  已登记 HKLM ...\\Fonts")
    except OSError as e:
        say(f"  登记 HKLM 失败：{e}")
        return False
    return True


def add_links() -> tuple[int, int]:
    """给每个主字体追加我们这条链接。返回 (新增, 已有)。"""
    key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\FontLink\SystemLink"
    added = exists = 0
    try:
        k = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key, 0,
                               winreg.KEY_READ | winreg.KEY_SET_VALUE)
    except OSError as e:
        say(f"  打开 FontLink 键失败：{e}")
        return 0, 0

    with k:
        for target in LINK_TARGETS:
            cur: list[str] = []
            try:
                v, _t = winreg.QueryValueEx(k, target)
                if isinstance(v, list):
                    cur = list(v)
                elif isinstance(v, str) and v:
                    cur = [v]
            except FileNotFoundError:
                pass

            # 去掉空串，避免写坏多字符串
            cur = [x for x in cur if x]
            if any(FONT_FILE.lower() in x.lower() for x in cur):
                exists += 1
                continue
            cur.append(LINK_VALUE)
            winreg.SetValueEx(k, target, 0, winreg.REG_MULTI_SZ, cur)
            added += 1
    return added, exists


def main() -> int:
    say("=== 洄文字体 · 系统级安装 + 字体链接 ===")
    say(f"管理员: {is_admin()}")
    if not is_admin():
        say("结果: 失败 —— 需要管理员")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 1

    say("\n--- 1) 系统级安装字体 ---")
    ok = install_system_font()
    say(f"  安装: {'成功' if ok else '失败'}")

    say("\n--- 2) 建立字体链接 ---")
    added, exists = add_links()
    say(f"  新增 {added} 条，已有 {exists} 条")

    say("\n--- 3) 回读确认 ---")
    key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\FontLink\SystemLink"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
            n = winreg.QueryInfoKey(k)[1]
            say(f"  SystemLink 现有 {n} 条")
            for probe in ("Microsoft YaHei", "Consolas", "Segoe UI"):
                try:
                    v, _t = winreg.QueryValueEx(k, probe)
                    hit = [x for x in v if FONT_FILE.lower() in x.lower()]
                    say(f"    {probe}: {'已含洄文' if hit else '未含'}")
                except FileNotFoundError:
                    say(f"    {probe}: 无此项")
    except OSError as e:
        say(f"  回读失败：{e}")

    say("\n结果: 完成")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
