#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文字体 · 安装 / 验证 / 卸载（用户级，不需要管理员权限）

为什么不再用 `AddFontResourceEx`：
  它只把字体临时挂进**当前进程**，进程一退就没了；而且实测对本字体返回 0。
  真正要「装成系统字体」应该走**用户级字体安装**：
     1. 把 ttf 复制到 %LOCALAPPDATA%\\Microsoft\\Windows\\Fonts
     2. 在 HKCU\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts 登记
     3. 广播 WM_FONTCHANGE
  这样重启后依然在，所有程序都能用，**且不需要管理员**。

验证也不再用 Tk（它的字体列表有缓存，判据不可靠），改用 **GDI 自己的判据**：
     CreateFontIndirectW → SelectObject → GetGlyphIndicesW
  目标码位取不到字形（0xFFFF）就是没装上；取到了就是装上了。
  这是权威答案，不依赖任何缓存。

用法：
    python tools/hwfontinstall.py probe       # 只诊断，不改任何东西
    python tools/hwfontinstall.py install     # 用户级安装
    python tools/hwfontinstall.py verify      # GDI 验证
    python tools/hwfontinstall.py uninstall   # 卸载
"""
from __future__ import annotations

import ctypes
import shutil
import sys
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TTF = ROOT / "font" / "GalHuiwen.ttf"
FAMILY = "GalHuiwen"
REG_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
REG_VALUE = "GalHuiwen (TrueType)"
PROBE_CP = 0xE14C          # 爱（新码位分配后的值）

gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

GGI_MARK_NONEXISTING_GLYPHS = 0x0001
DEFAULT_CHARSET = 1
HWND_BROADCAST = 0xFFFF
WM_FONTCHANGE = 0x001D
SMTO_ABORTIFHUNG = 0x0002


class LOGFONTW(ctypes.Structure):
    _fields_ = [
        ("lfHeight", wintypes.LONG), ("lfWidth", wintypes.LONG),
        ("lfEscapement", wintypes.LONG), ("lfOrientation", wintypes.LONG),
        ("lfWeight", wintypes.LONG), ("lfItalic", wintypes.BYTE),
        ("lfUnderline", wintypes.BYTE), ("lfStrikeOut", wintypes.BYTE),
        ("lfCharSet", wintypes.BYTE), ("lfOutPrecision", wintypes.BYTE),
        ("lfClipPrecision", wintypes.BYTE), ("lfQuality", wintypes.BYTE),
        ("lfPitchAndFamily", wintypes.BYTE), ("lfFaceName", wintypes.WCHAR * 32),
    ]


def user_font_dir() -> Path:
    import os
    return Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts"


def gdi_probe(family: str = FAMILY, cp: int = PROBE_CP) -> dict:
    """问 GDI：这个字体家族能不能取到目标码位的字形。

    返回 {'face': 实际选中的字体名, 'glyph_index': 字形号 or 0xFFFF, 'ok': bool}
    """
    lf = LOGFONTW()
    lf.lfHeight = -48
    lf.lfWeight = 400
    lf.lfCharSet = DEFAULT_CHARSET
    lf.lfFaceName = family
    hf = gdi32.CreateFontIndirectW(ctypes.byref(lf))
    if not hf:
        return {"face": None, "glyph_index": None, "ok": False,
                "err": "CreateFontIndirectW 失败"}

    hdc = gdi32.CreateCompatibleDC(0)
    old = gdi32.SelectObject(hdc, hf)
    try:
        buf = ctypes.create_unicode_buffer(64)
        gdi32.GetTextFaceW(hdc, 64, buf)
        face = buf.value
        gi = wintypes.WORD()
        text = ctypes.c_wchar_p(chr(cp))
        gdi32.GetGlyphIndicesW(hdc, text, 1, ctypes.byref(gi),
                               GGI_MARK_NONEXISTING_GLYPHS)
        # 顺便量一下宽度：回退字体的宽度与真字体不同
        sz = wintypes.SIZE()
        gdi32.GetTextExtentPoint32W(hdc, text, 1, ctypes.byref(sz))
        return {"face": face, "glyph_index": gi.value,
                "ok": gi.value != 0xFFFF and gi.value != 0,
                "width": sz.cx, "height": sz.cy}
    finally:
        gdi32.SelectObject(hdc, old)
        gdi32.DeleteDC(hdc)
        gdi32.DeleteObject(hf)


def registered_value() -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            v, _ = winreg.QueryValueEx(k, REG_VALUE)
            return v
    except FileNotFoundError:
        return None


def broadcast_fontchange() -> None:
    res = ctypes.c_ulong()
    user32.SendMessageTimeoutW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0,
                               SMTO_ABORTIFHUNG, 3000, ctypes.byref(res))


def cmd_probe() -> int:
    print("=" * 62)
    print("洄文字体 · GDI 诊断")
    print("=" * 62)
    print(f"字体文件：{TTF}")
    print(f"  存在：{TTF.exists()}　大小：{TTF.stat().st_size // 1024} KB"
          if TTF.exists() else "  不存在！")
    print()

    # 1) 安装前（只有可能来自别处的注册）
    ufd = user_font_dir()
    installed = ufd / TTF.name
    print(f"用户字体目录：{ufd}")
    print(f"  目录存在：{ufd.exists()}")
    print(f"  字体已复制：{installed.exists()}")
    print(f"注册表登记：{registered_value()!r}")
    print()

    r = gdi_probe()
    print("GDI 探测（未做任何安装动作）：")
    print(f"  请求家族：{FAMILY}")
    print(f"  实际选中：{r.get('face')!r}")
    print(f"  字形号  ：{r.get('glyph_index')}")
    print(f"  可用    ：{'是' if r.get('ok') else '否'}")
    print()

    # 2) 用 AddFontResourceEx 临时挂载后再探（解释历史现象）
    FR_PRIVATE = 0x10
    n_priv = gdi32.AddFontResourceExW(ctypes.c_wchar_p(str(TTF)), FR_PRIVATE, 0)
    n_perm = gdi32.AddFontResourceExW(ctypes.c_wchar_p(str(TTF)), 0, 0)
    r2 = gdi_probe()
    print("GDI 探测（AddFontResourceEx 临时挂载之后）：")
    print(f"  AddFontResourceEx(FR_PRIVATE) 返回：{n_priv}")
    print(f"  AddFontResourceEx(0)          返回：{n_perm}")
    print(f"  实际选中：{r2.get('face')!r}　字形号：{r2.get('glyph_index')}")
    print(f"  可用    ：{'是' if r2.get('ok') else '否'}")
    if n_perm:
        gdi32.RemoveFontResourceExW(ctypes.c_wchar_p(str(TTF)), 0, 0)
    if n_priv:
        gdi32.RemoveFontResourceExW(ctypes.c_wchar_p(str(TTF)), FR_PRIVATE, 0)
    print()
    print("判读：字形号 != 0xFFFF 且 != 0 才算这个家族真的提供了该字形。")
    return 0


def cmd_install() -> int:
    print("=" * 62)
    print("洄文字体 · 用户级安装（不需要管理员）")
    print("=" * 62)
    if not TTF.exists():
        print(f"✘ 找不到字体文件：{TTF}")
        return 1

    ufd = user_font_dir()
    ufd.mkdir(parents=True, exist_ok=True)
    dst = ufd / TTF.name
    shutil.copy2(TTF, dst)
    print(f"1) 已复制到用户字体目录")
    print(f"   {dst}　{dst.stat().st_size // 1024} KB")

    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, REG_VALUE, 0, winreg.REG_SZ, str(dst))
    print(f"2) 已登记注册表")
    print(f"   HKCU\\{REG_KEY}")
    print(f"   {REG_VALUE} = {dst}")

    broadcast_fontchange()
    print("3) 已广播 WM_FONTCHANGE")

    print()
    r = gdi_probe()
    print("4) GDI 验证：")
    print(f"   实际选中：{r.get('face')!r}　字形号：{r.get('glyph_index')}")
    print(f"   可用    ：{'✔ 是' if r.get('ok') else '✘ 否'}")
    return 0 if r.get("ok") else 2


def cmd_verify() -> int:
    r = gdi_probe()
    print(f"家族 {FAMILY} → 实际选中 {r.get('face')!r}，"
          f"U+{PROBE_CP:04X} 字形号 {r.get('glyph_index')}")
    print("✔ 字体已生效，系统能取到洄文字形" if r.get("ok")
          else "✘ 取不到字形：字体未生效")
    return 0 if r.get("ok") else 1


def cmd_uninstall() -> int:
    import winreg
    ufd = user_font_dir()
    dst = ufd / TTF.name
    if dst.exists():
        dst.unlink()
        print(f"已删除 {dst}")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, REG_VALUE)
        print(f"已删除注册表值 {REG_VALUE}")
    except FileNotFoundError:
        print("注册表值不存在")
    broadcast_fontchange()
    print("已广播 WM_FONTCHANGE")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    return {"probe": cmd_probe, "install": cmd_install,
            "verify": cmd_verify, "uninstall": cmd_uninstall}.get(
        cmd, cmd_probe)()


if __name__ == "__main__":
    sys.exit(main())
