#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直接调 DllRegisterServer，把真实 HRESULT 与注册表结果写进文件。

为什么要这个：`regsvr32 /s` 失败时也可能返回 0，而且它把真实错误藏在对话框里。
直接 LoadLibrary + 调导出函数，才能拿到确切的 HRESULT。
"""
from __future__ import annotations

import ctypes
import sys
import winreg
from pathlib import Path

OUT = Path(__file__).resolve().parent / "register_trace.txt"
DLLS = [
    "huiwen_ime6.dll",     # 用 ITfKeystrokeMgr::AdviseKeyEventSink 挂按键（正解）
    "huiwen_ime5.dll",
    "huiwen_ime4.dll",
    "huiwen_ime3.dll",
    "huiwen_ime2.dll",
    "huiwen_ime.dll",
]

CLSID = "{7F3A9C10-2B4D-4E6A-9C11-8A2F0D553E71}"
GUIDP = "{7F3A9C11-2B4D-4E6A-9C11-8A2F0D553E72}"

lines: list[str] = []


def say(s: str) -> None:
    lines.append(s)


def hr(u: int) -> str:
    names = {
        0x00000000: "S_OK",
        0x80004005: "E_FAIL",
        0x80070005: "E_ACCESSDENIED",
        0x80070002: "ERROR_FILE_NOT_FOUND",
        0x80040154: "REGDB_E_CLASSNOTREG",
        0x800401F0: "CO_E_NOTINITIALIZED",
    }
    return names.get(u & 0xFFFFFFFF, f"0x{u & 0xFFFFFFFF:08X}")


def reg_state() -> list[str]:
    out = []
    def chk(hive, name, path):
        try:
            with winreg.OpenKey(hive, path) as k:
                try:
                    v = winreg.QueryValueEx(k, "")[0]
                except FileNotFoundError:
                    v = ""
                out.append(f"    {name}: 有  {v}")
                return True
        except FileNotFoundError:
            out.append(f"    {name}: 没有")
            return False
    chk(winreg.HKEY_LOCAL_MACHINE, "HKLM COM类",
        rf"SOFTWARE\Classes\CLSID\{CLSID}\InprocServer32")
    chk(winreg.HKEY_LOCAL_MACHINE, "HKLM 语言档案",
        rf"SOFTWARE\Microsoft\CTF\TIP\{CLSID}\LanguageProfile\0x00000804\{GUIDP}")
    return out


def main() -> int:
    here = Path(__file__).resolve().parent

    say("=== 注册前 ===")
    lines.extend(reg_state())

    # 确认当前是不是管理员
    try:
        admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:                                     # noqa: BLE001
        admin = False
    say(f"\n管理员: {admin}")

    # COM 初始化
    ole32 = ctypes.WinDLL("ole32")
    hrco = ole32.CoInitializeEx(None, 2)
    say(f"CoInitializeEx -> {hr(hrco)}")

    def call(dll, export: str) -> str:
        if not hasattr(dll, export):
            return "找不到导出"
        fn = getattr(dll, export)
        fn.restype = ctypes.c_long
        fn.argtypes = []
        return hr(fn() & 0xFFFFFFFF)

    # 第一步：把所有旧版本都反注册掉，避免多个档案打架。
    # **注意**：不能对同一个 DLL 先注册再反注册 —— 那样最后一步会把刚注册的清掉
    #（这个脚本第一版就是这么写的，结果"注册后"是空的，白折腾一轮）。
    say("\n--- 清理旧版本 ---")
    for name in DLLS:
        p = here / "out" / name
        if not p.exists():
            continue
        try:
            dll = ctypes.WinDLL(str(p))
        except OSError as e:
            say(f"  {name}: LoadLibrary 失败 {e}")
            continue
        say(f"  {name} DllUnregisterServer -> {call(dll, 'DllUnregisterServer')}")

    # 第二步：只注册最终要用的那个（列表第一个）
    target = here / "out" / DLLS[0]
    say(f"\n--- 注册 {DLLS[0]} ---")
    if not target.exists():
        say("  文件不存在")
        return 1
    try:
        dll = ctypes.WinDLL(str(target))
    except OSError as e:
        say(f"  LoadLibrary 失败：{e}")
        return 1
    say("  LoadLibrary: 成功")
    say(f"  DllRegisterServer -> {call(dll, 'DllRegisterServer')}")
    # 再问一次 TSF 认不认
    say(f"  （注册后立刻回读见下）")

    say("\n=== 注册后 ===")
    lines.extend(reg_state())

    OUT.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
