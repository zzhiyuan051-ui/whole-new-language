#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑打包好的 exe 并如实回报：退出码、标准错误、产物文件。

为什么要专门写这个：用 PowerShell 的 Start-Process 测窗口版 exe 会**假挂起** ——
子进程继承了输出管道，工具就一直等管道关闭，看起来像"卡住了"。
Python 的 subprocess 用 DEVNULL 就不会有这个问题。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent       # huiwen/
EXE = ROOT / "dist" / "洄文输入法" / "洄文输入法.exe"
OUT_DIR = EXE.parent / "洄文导出"


def run(arg: str, timeout: int = 90) -> None:
    print(f"=== {arg} ===")
    print(f"  exe: {EXE}  存在={EXE.exists()}")
    if not EXE.exists():
        return
    try:
        r = subprocess.run([str(EXE), arg], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL)
        print(f"  退出码: {r.returncode}")
        if r.stdout.strip():
            print("  stdout:")
            for line in r.stdout.strip().splitlines()[-25:]:
                print(f"    {line}")
        if r.stderr.strip():
            print("  stderr:")
            for line in r.stderr.strip().splitlines()[-25:]:
                print(f"    {line}")
    except subprocess.TimeoutExpired:
        print(f"  ⚠ {timeout} 秒没退出（真的卡住了，不是管道问题）")


def show_outputs() -> None:
    print(f"\n=== 产物目录 {OUT_DIR} ===")
    if not OUT_DIR.exists():
        print("  不存在")
        # 顺便看看是不是落在别处
        for cand in (EXE.parent / "output", Path.home() / "洄文导出",
                     Path.home() / "Documents" / "洄文导出"):
            if cand.exists():
                print(f"  但在 {cand} 找到了：")
                for f in cand.iterdir():
                    print(f"    {f.name}  {f.stat().st_size} 字节")
        return
    for f in sorted(OUT_DIR.iterdir()):
        print(f"  {f.name}  {f.stat().st_size} 字节")
    for name in ("自检报告.txt", "分享图自检.txt"):
        p = OUT_DIR / name
        if p.exists():
            print(f"\n--- {name} ---")
            print(p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    args = sys.argv[1:] or ["--test-share"]
    for a in args:
        run(a)
    show_outputs()
