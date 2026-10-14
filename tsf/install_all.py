#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文输入法 · 一键安装（需要管理员）

把下面这几件事一次做完，全部幂等，可以反复运行：

  1. 把字体与输入法组件复制到规范位置（默认 C:\\Program Files\\GalHuiwen）
     —— 不能直接注册工作区里的 DLL：工作区一移动/删除，输入法就废了。
  2. 装字体：复制到 C:\\Windows\\Fonts 并在 HKLM 登记
  3. 建字体链接：主字体缺字形时回退到洄文字体（私用区码位没有系统字体会覆盖，
     不建链接的话别的程序只会画出空心方格）
  4. 注册 TSF 文本服务（HKLM；TSF 只认机器级注册，用户级写了也不生效）
  5. 把输入法加进**当前用户**的输入法清单（不写这个，Win+Space 切不到它）

用法：
    提权运行本脚本        python install_all.py
    只做第 4 步           python install_all.py --register-only

卸载：python uninstall_all.py（见同目录）
"""
from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # huiwen/
OUT = HERE / "out"

INSTALL_DIR = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "GalHuiwen"
FONT_NAME = "GalHuiwen.ttf"
DLL_NAME = "huiwen_ime.dll"
ICO_NAME = "GalHuiwen.ico"
FAMILY = "GalHuiwen"
WIN_FONTS = Path(r"C:\Windows\Fonts")

CLSID = "{7F3A9C10-2B4D-4E6A-9C11-8A2F0D553E71}"
GUID_PROFILE = "{7F3A9C11-2B4D-4E6A-9C11-8A2F0D553E72}"
LANGID_HEX = "0x00000804"

# 要用哪个版本的 DLL 作为正式组件（按顺序取第一个存在的）
DLL_CANDIDATES = ["huiwen_ime6.dll", "huiwen_ime5.dll", "huiwen_ime4.dll",
                  "huiwen_ime3.dll", "huiwen_ime.dll"]

REPORT = HERE / "install_all_result.txt"
log: list[str] = []


def say(s: str = "") -> None:
    log.append(s)
    print(s)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:                                       # noqa: BLE001
        return False


# ---------------------------------------------------------------- 1. 复制文件
def copy_files() -> bool:
    say("--- 1) 复制到规范位置 ---")
    src_font = ROOT / "font" / FONT_NAME
    if not src_font.exists():
        say(f"  ✘ 找不到字体源文件：{src_font}")
        return False

    dll_src = None
    for name in DLL_CANDIDATES:
        p = OUT / name
        if p.exists():
            dll_src = p
            break
    if dll_src is None:
        say(f"  ✘ 找不到输入法组件（找过 {DLL_CANDIDATES}）")
        return False

    try:
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_font, INSTALL_DIR / FONT_NAME)
        # 图标：注册时要用真实路径，不能留空
        for cand in (ROOT / "font" / ICO_NAME, ROOT / "tsf" / ICO_NAME):
            if cand.exists():
                shutil.copy2(cand, INSTALL_DIR / ICO_NAME)
                break
        # DLL 可能正被进程占用 —— 那就换个名字（注册表指向新文件即可）
        dst = INSTALL_DIR / DLL_NAME
        try:
            shutil.copy2(dll_src, dst)
        except OSError:
            dst = INSTALL_DIR / dll_src.name
            shutil.copy2(dll_src, dst)
            say(f"  （{DLL_NAME} 被占用，改用 {dst.name}）")
        say(f"  ✔ 目录 {INSTALL_DIR}")
        say(f"  ✔ 组件 {dst.name}（来自 {dll_src.name}）")
        (HERE / "_installed_path.txt").write_text(str(dst), encoding="utf-8")
        return True
    except OSError as e:
        say(f"  ✘ 复制失败：{e}")
        return False


# ---------------------------------------------------------------- 2. 装字体
def install_font() -> bool:
    say("\n--- 2) 安装字体到系统 ---")
    src = INSTALL_DIR / FONT_NAME
    dst = WIN_FONTS / FONT_NAME
    try:
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
            say(f"  ✔ 复制到 {dst}")
        else:
            say(f"  ✔ 已存在 {dst}")
        key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key, 0,
                                winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, f"{FAMILY} (TrueType)", 0,
                              winreg.REG_SZ, FONT_NAME)
        say("  ✔ 已登记 HKLM\\...\\Fonts")
        return True
    except OSError as e:
        say(f"  ✘ 失败：{e}")
        return False


# ---------------------------------------------------------------- 3. 字体链接
LINK_TARGETS = [
    "Microsoft YaHei", "Microsoft YaHei UI", "Microsoft YaHei Light",
    "微软雅黑", "SimSun", "宋体", "NSimSun", "新宋体", "SimSun-ExtB",
    "SimHei", "黑体", "KaiTi", "楷体", "FangSong", "仿宋",
    "DengXian", "等线", "YouYuan", "幼圆", "LiSu", "隶书",
    "Microsoft JhengHei", "Microsoft JhengHei UI", "MingLiU", "PMingLiU",
    "STXihei", "华文细黑", "STSong", "华文宋体", "STKaiti", "华文楷体",
    "Segoe UI", "Segoe UI Variable", "Tahoma", "Arial", "Arial Unicode MS",
    "Microsoft Sans Serif", "Verdana", "Calibri", "Times New Roman",
    "Georgia", "Trebuchet MS", "Comic Sans MS", "Palatino Linotype",
    "Consolas", "Lucida Console", "Courier New", "Cascadia Mono",
    "Cascadia Code", "MS Gothic", "MS Mincho", "Yu Gothic UI",
    "Malgun Gothic", "Gulim", "Batang", "Nirmala UI",
]


def add_font_links() -> bool:
    say("\n--- 3) 建立字体链接（私用区字形回退）---")
    key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\FontLink\SystemLink"
    value = f"{FONT_NAME},{FAMILY}"
    added = exists = 0
    try:
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key, 0,
                                winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            for target in LINK_TARGETS:
                cur: list[str] = []
                try:
                    v, _t = winreg.QueryValueEx(k, target)
                    cur = list(v) if isinstance(v, list) else ([v] if v else [])
                except FileNotFoundError:
                    pass
                cur = [x for x in cur if x]
                if any(FONT_NAME.lower() in x.lower() for x in cur):
                    exists += 1
                    continue
                cur.append(value)
                winreg.SetValueEx(k, target, 0, winreg.REG_MULTI_SZ, cur)
                added += 1
        say(f"  ✔ 新增 {added} 条，已有 {exists} 条（共 {len(LINK_TARGETS)} 个目标字体）")
        return True
    except OSError as e:
        say(f"  ✘ 失败：{e}")
        return False


# ---------------------------------------------------------------- 4. 注册 TSF
def register_tsf() -> bool:
    say("\n--- 4) 注册 TSF 输入法 ---")
    path_file = HERE / "_installed_path.txt"
    dll = Path(path_file.read_text(encoding="utf-8").strip()) if path_file.exists() \
        else INSTALL_DIR / DLL_NAME
    if not dll.exists():
        say(f"  ✘ 组件不存在：{dll}")
        return False
    try:
        lib = ctypes.WinDLL(str(dll))
    except OSError as e:
        say(f"  ✘ 加载组件失败：{e}")
        return False
    fn = lib.DllRegisterServer
    fn.restype = ctypes.c_long
    fn.argtypes = []
    hr = fn() & 0xFFFFFFFF
    say(f"  DllRegisterServer -> 0x{hr:08X} {'成功' if hr == 0 else '失败'}")

    # 回读机器级注册（TSF 只认这一份）
    ok = True
    for sub, label in ((rf"SOFTWARE\Classes\CLSID\{CLSID}\InprocServer32", "COM 类"),
                       (rf"SOFTWARE\Microsoft\CTF\TIP\{CLSID}\LanguageProfile"
                        rf"\{LANGID_HEX}\{GUID_PROFILE}", "语言档案")):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub):
                say(f"  ✔ HKLM {label}")
        except FileNotFoundError:
            say(f"  ✘ HKLM {label} 缺失")
            ok = False
    return hr == 0 and ok


# ---------------------------------------------------------------- 5. 用户清单
def add_to_user_list() -> bool:
    say("\n--- 5) 加进当前用户的输入法清单 ---")
    tip = f"0804:{CLSID}{GUID_PROFILE}"
    ps = (
        "$ErrorActionPreference='Stop';"
        f"$tip='{tip}';"
        "$l=Get-WinUserLanguageList;"
        "foreach($x in $l){if($x.LanguageTag -eq 'zh-Hans-CN' -and "
        "($x.InputMethodTips -notcontains $tip)){$x.InputMethodTips.Add($tip)}};"
        "Set-WinUserLanguageList $l -Force;"
        "'ok'"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=60)
        if "ok" in (r.stdout or ""):
            say("  ✔ 已写入")
            return True
        say(f"  ✘ 失败：{r.stderr.strip()[:200]}")
        return False
    except Exception as e:                                  # noqa: BLE001
        say(f"  ✘ 异常：{e}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--register-only", action="store_true",
                    help="只做注册（跳过复制与字体）")
    args = ap.parse_args()

    say("=== 洄文输入法 · 一键安装 ===")
    say(f"管理员: {is_admin()}")
    if not is_admin():
        say("\n✘ 需要管理员权限。请右键以管理员身份运行，")
        say("  或：powershell -Command \"Start-Process python -ArgumentList '<本文件>' -Verb RunAs\"")
        REPORT.write_text("\n".join(log), encoding="utf-8")
        return 1

    results = {}
    if not args.register_only:
        results["复制文件"] = copy_files()
        if not results["复制文件"]:
            say("\n复制失败，后续步骤无法进行。")
            REPORT.write_text("\n".join(log), encoding="utf-8")
            return 1
        results["安装字体"] = install_font()
        results["字体链接"] = add_font_links()
    else:
        say("（--register-only：跳过复制、字体、链接）")

    results["注册 TSF"] = register_tsf()
    results["用户清单"] = add_to_user_list()

    say("\n=== 结果 ===")
    for k, v in results.items():
        say(f"  {'✔' if v else '✘'} {k}")

    allok = all(results.values())
    say(f"\n{'全部完成' if allok else '有步骤失败'}。")
    if allok:
        say("\n现在按 Win+Space 切到「洄文输入法」即可使用。")
    REPORT.write_text("\n".join(log), encoding="utf-8")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
