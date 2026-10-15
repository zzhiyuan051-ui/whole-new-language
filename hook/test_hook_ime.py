#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文输入法（钩子版）· 端到端自动化测试

真启动输入法、真开一个靶子窗口、真注入按键，然后把靶子编辑框里的内容读回来，
和「按同一份词表算出的期望值」比对。

为什么要这么麻烦：
  「编译通过」和「输入法真能往别的程序里打出字」是两件事。
  前面在字体的系统注册上就吃过「探针自相矛盾」的亏，所以这次直接测最终效果。

注意：测试要用 --accept-injected。默认钩子会放过「注入的」按键
（那是别的程序合成的，不该被输入法接管），但测试脚本也只能用注入造键。
"""
from __future__ import annotations

import csv
import ctypes
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK_EXE = ROOT / "hook" / "out" / "洄文输入法-免安装版.exe"
TARGET_EXE = ROOT / "hook" / "out" / "huiwen_target.exe"
OUT_FILE = ROOT / "hook" / "out" / "_test_result.txt"

user32 = ctypes.WinDLL("user32", use_last_error=True)

KEYEVENTF_KEYUP = 0x0002
VK = {"z": 0x5A, "a": 0x41, "y": 0x59, "1": 0x31}

# SendInput 的 INPUT 结构体**在 x64 上必须是 40 字节**。
# 只声明 KEYBDINPUT + 一个 24 字节的 padding 会得到 28 字节，
# SendInput 直接返回 0 并给错误码 87（参数无效）—— 这个坑踩过。
# 所以把 MOUSEINPUT/HARDWAREINPUT 也声明出来，让 ctypes 自己算对齐。
_PUL = ctypes.POINTER(ctypes.c_ulong)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", _PUL)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", _PUL)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort),
                ("wParamH", ctypes.c_ushort)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("u", _INPUTUNION)]


assert ctypes.sizeof(INPUT) == 40, f"INPUT 大小应为 40，实为 {ctypes.sizeof(INPUT)}"


def norm(s: str) -> str:
    """必须与 C++ normKey / Python engine.IME.norm 一致。"""
    return re.sub(r"[^a-z]", "", s.lower())


def expected_first(query: str) -> tuple[str, str, int]:
    """复刻 C++ 的候选扫描，算出「第一个候选」是什么。

    C++ 侧：词表按 (归一化音节, 音节长度, 音节) 排序，扫描取前 9 个
    「归一化音节以输入为前缀」的条目。这里照做，才能对得上。
    """
    rows = list(csv.DictReader((ROOT / "lexicon.tsv").open(encoding="utf-8"),
                               delimiter="\t"))
    rows.sort(key=lambda r: (norm(r["syll"]), len(r["syll"]), r["syll"]))
    q = norm(query)
    hits = [r for r in rows if norm(r["syll"]).startswith(q)][:9]
    if not hits:
        raise SystemExit(f"词表里没有以 {q} 开头的词")
    r = hits[0]
    return r["zh"], r["syll"], int(r["codepoint"])


def press(vk: int) -> None:
    """用 SendInput 发一次「按下+抬起」。

    为什么不用 keybd_event：它已废弃，且返回值拿不到；
    SendInput 能回报「真发出去了几个事件」，测试才判得准。
    """
    arr = (INPUT * 2)()
    arr[0].type = 1                      # INPUT_KEYBOARD
    arr[0].u.ki.wVk = vk
    arr[1].type = 1
    arr[1].u.ki.wVk = vk
    arr[1].u.ki.dwFlags = KEYEVENTF_KEYUP
    ctypes.set_last_error(0)
    n = user32.SendInput(2, arr, ctypes.sizeof(INPUT))
    if n != 2:
        raise RuntimeError(
            f"SendInput 只发出 {n}/2 个事件，错误码 {ctypes.get_last_error()}")
    time.sleep(0.12)


def focus_window(title_part: str) -> bool:
    """把靶子窗口拉到前台。枚举顶层窗口按标题找。"""
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if title_part in buf.value:
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    if not found:
        return False
    hwnd = found[0]
    user32.ShowWindow(hwnd, 9)          # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    return True


def main() -> int:
    fails: list[str] = []

    def check(cond, label, extra=""):
        print(f"[{'通过' if cond else '失败'}] {label}" + (f"　{extra}" if extra else ""))
        if not cond:
            fails.append(label)

    if not HOOK_EXE.exists():
        print(f"找不到输入法程序：{HOOK_EXE}\n先运行 hook/build_hook.ps1")
        return 1
    if not TARGET_EXE.exists():
        print(f"找不到测试靶子：{TARGET_EXE}\n先运行 hook/build_target.ps1")
        return 1

    if OUT_FILE.exists():
        OUT_FILE.unlink()

    query = "za"
    zh, syll, cp = expected_first(query)
    print(f"输入「{query}」→ 期望第一个候选：{zh}（{syll}）U+{cp:04X}")
    print()

    hook = None
    target = None
    try:
        # 1) 启动输入法（测试模式）
        logf = ROOT / "hook" / "out" / "_hook.log"
        if logf.exists():
            logf.unlink()
        hook = subprocess.Popen([str(HOOK_EXE), "--accept-injected",
                                 "--log", str(logf)],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(1.5)
        check(hook.poll() is None, "输入法进程存活")

        # 2) 启动靶子并抢焦点
        target = subprocess.Popen([str(TARGET_EXE), str(OUT_FILE), "20"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        time.sleep(2.0)
        got_focus = focus_window("测试靶子")
        check(got_focus, "靶子窗口取得焦点")
        time.sleep(0.6)

        # 3) 注入按键：z a → 出候选；1 → 选第一个
        press(VK["z"])
        press(VK["a"])
        time.sleep(0.5)
        press(VK["1"])
        time.sleep(1.2)

        # 4) 读回结果
        check(OUT_FILE.exists(), "靶子写出了结果文件")
        if OUT_FILE.exists():
            txt = OUT_FILE.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"hex=([0-9A-F ]*)", txt)
            cps = [int(x, 16) for x in m.group(1).split()] if m else []
            print(f"       靶子编辑框里的码位：{['U+%04X' % c for c in cps]}")
            check(len(cps) == 1, "恰好打入 1 个字符", f"实得 {len(cps)} 个")
            if cps:
                check(cps[0] == cp, f"打入的字 = 期望的「{zh}」",
                      f"U+{cps[0]:04X} vs U+{cp:04X}")
                check(0xE000 <= cps[0] <= 0xF8FF, "打入的码位在私用区内",
                      f"U+{cps[0]:04X}")

        # 5) 再测一次多字节：esc 取消后重来
        if OUT_FILE.exists():
            OUT_FILE.unlink()
        # 清空编辑框
        hwnd = user32.GetForegroundWindow()
        user32.SendMessageW(hwnd, 0x000C, 0, 0)      # WM_SETTEXT ""
        time.sleep(0.4)
        press(VK["z"])
        press(VK["a"])
        time.sleep(0.4)
        press(0x20)                                   # 空格 = 选第一个
        time.sleep(1.2)
        if OUT_FILE.exists():
            txt = OUT_FILE.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"hex=([0-9A-F ]*)", txt)
            cps2 = [int(x, 16) for x in m.group(1).split()] if m else []
            print(f"       （空格提交）码位：{['U+%04X' % c for c in cps2]}")
            check(cps2 == [cp], "空格键同样能提交第一个候选")
    finally:
        for p in (target, hook):
            if p and p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()

    print()
    print("端到端测试全部通过。" if not fails else f"失败 {len(fails)} 项：{fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
