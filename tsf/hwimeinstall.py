#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文输入法（TSF 系统级）· 安装 / 卸载 / 验证

这个工具做三件事：
  1. install   —— 编译好的 DLL 复制到稳定位置，调它的 DllRegisterServer 注册进 TSF
  2. verify    —— 查注册表与 TSF 档案，确认「洄文输入法」真出现在输入法列表里
  3. uninstall —— 调 DllUnregisterServer 并清理

为什么不直接 regsvr32：
  本项目要**免管理员**安装。regsvr32 会写 HKLM，非管理员会失败。
  DLL 里的 RegisterServer 已改成写 HKCU\\Software\\Classes（按用户注册）。
  这里用 ctypes 直接 LoadLibrary + 调导出的 DllRegisterServer，
  顺便能把返回值（HRESULT）如实报出来，比 regsvr32 的弹窗有用。
"""
from __future__ import annotations

import ctypes
import os
import shutil
import sys
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DLL_SRC = ROOT / "tsf" / "out" / "huiwen_ime.dll"

CLSID = "{7F3A9C10-2B4D-4E6A-9C11-8A2F0D553E71}"
GUID_PROFILE = "{7F3A9C11-2B4D-4E6A-9C11-8A2F0D553E72}"
LANGID = "0x0804"

# 装到用户程序目录，路径稳定（DLL 一旦注册就不能随便挪）
INSTALL_DIR = Path(os.environ["LOCALAPPDATA"]) / "GalHuiwenIME"
DLL_DST = INSTALL_DIR / "huiwen_ime.dll"


def hresult_name(hr: int) -> str:
    """把 HRESULT 说成人话（至少把常见失败说清楚）。"""
    known = {
        0x00000000: "S_OK 成功",
        0x80004005: "E_FAIL 未指明的失败",
        0x80040154: "REGDB_E_CLASSNOTREG 类未注册（TSF 组件不可用）",
        0x800401F0: "CO_E_NOTINITIALIZED COM 未初始化",
        0x80070005: "E_ACCESSDENIED 拒绝访问（可能需要管理员）",
        0x80004002: "E_NOINTERFACE 接口不支持",
    }
    u = hr & 0xFFFFFFFF
    return known.get(u, f"HRESULT 0x{u:08X}")


def _load_dll(path: Path):
    if not path.exists():
        raise SystemExit(f"找不到 DLL：{path}\n先运行：powershell -File huiwen/tsf/build.ps1")
    try:
        return ctypes.WinDLL(str(path))
    except OSError as e:
        raise SystemExit(f"加载 DLL 失败：{e}") from e


def cmd_install() -> int:
    print("=" * 64)
    print("洄文输入法（TSF 系统级）· 安装")
    print("=" * 64)
    if not DLL_SRC.exists():
        raise SystemExit(f"找不到编译产物：{DLL_SRC}\n"
                         f"先编译：powershell -NoProfile -ExecutionPolicy Bypass "
                         f"-File huiwen/tsf/build.ps1")

    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DLL_SRC, DLL_DST)
    print(f"1) DLL 已放到 {DLL_DST}（{DLL_DST.stat().st_size // 1024} KB）")

    dll = _load_dll(DLL_DST)
    fn = dll.DllRegisterServer
    fn.restype = ctypes.c_long
    fn.argtypes = []
    hr = fn() & 0xFFFFFFFF
    print(f"2) DllRegisterServer → {hresult_name(hr)}")
    if hr != 0:
        return 1

    print("3) 注册表检查：")
    ok = True
    checks = [
        (winreg.HKEY_CURRENT_USER, rf"Software\Classes\CLSID\{CLSID}\InprocServer32",
         None, "COM 类（按用户）"),
        (winreg.HKEY_CURRENT_USER,
         rf"Software\Microsoft\CTF\TIP\{CLSID}\LanguageProfile\{LANGID}\{GUID_PROFILE}",
         None, "TSF 语言档案"),
    ]
    for hive, key, _, label in checks:
        try:
            with winreg.OpenKey(hive, key) as k:
                n = winreg.QueryInfoKey(k)[1]
                print(f"     ✔ {label}：存在（{n} 个值）")
        except FileNotFoundError:
            print(f"     ✘ {label}：不存在　{key}")
            ok = False
    print()
    print("安装完成。" if ok else "安装有缺项，见上面 ✘。")
    print("接下来：按 Win+Space（或点语言栏）选到「洄文输入法」，然后敲 za 试试。")
    return 0 if ok else 2


def cmd_verify() -> int:
    print("=" * 64)
    print("洄文输入法（TSF）· 验证")
    print("=" * 64)
    ok = True

    print(f"DLL：{DLL_DST}")
    print(f"  存在：{DLL_DST.exists()}")
    if DLL_DST.exists():
        print(f"  大小：{DLL_DST.stat().st_size // 1024} KB")

    for hive, key, label in (
        (winreg.HKEY_CURRENT_USER, rf"Software\Classes\CLSID\{CLSID}\InprocServer32",
         "COM 类注册（按用户）"),
        (winreg.HKEY_CURRENT_USER,
         rf"Software\Microsoft\CTF\TIP\{CLSID}\LanguageProfile\{LANGID}\{GUID_PROFILE}",
         "TSF 语言档案"),
        (winreg.HKEY_CURRENT_USER,
         rf"Software\Microsoft\CTF\TIP\{CLSID}\LanguageProfile\{LANGID}\{GUID_PROFILE}",
         "档案 Enable 值"),
    ):
        try:
            with winreg.OpenKey(hive, key) as k:
                info = winreg.QueryInfoKey(k)
                detail = f"{info[1]} 个值"
                try:
                    v, _ = winreg.QueryValueEx(k, "Enable")
                    detail += f"｜Enable={v}"
                except FileNotFoundError:
                    pass
                print(f"  ✔ {label}：{detail}")
        except FileNotFoundError:
            print(f"  ✘ {label}：不存在")
            ok = False

    # 直接问 DLL 在不在、导出行不行
    if DLL_DST.exists():
        try:
            dll = _load_dll(DLL_DST)
            _ = dll.DllGetClassObject
            print("  ✔ DLL 可加载，DllGetClassObject 导出存在")
        except SystemExit as e:
            print(f"  ✘ {e}")
            ok = False

    print()
    print("验证通过：洄文输入法已注册为系统输入法。" if ok else "验证未通过。")
    return 0 if ok else 1


def cmd_uninstall() -> int:
    print("=" * 64)
    print("洄文输入法（TSF）· 卸载")
    print("=" * 64)
    if DLL_DST.exists():
        try:
            dll = _load_dll(DLL_DST)
            fn = dll.DllUnregisterServer
            fn.restype = ctypes.c_long
            fn.argtypes = []
            hr = fn() & 0xFFFFFFFF
            print(f"DllUnregisterServer → {hresult_name(hr)}")
        except SystemExit as e:
            print(f"（跳过 DLL 反注册：{e}）")
        try:
            DLL_DST.unlink()
            print(f"已删除 {DLL_DST}")
        except OSError as e:
            print(f"删除 DLL 失败（可能仍被加载）：{e}")
    else:
        print("DLL 不在，跳过反注册")
    print("卸载完成。注销/重启后语言栏里的「洄文输入法」才会彻底消失。")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    return {"install": cmd_install, "verify": cmd_verify,
            "uninstall": cmd_uninstall}.get(cmd, cmd_verify)()


if __name__ == "__main__":
    sys.exit(main())
