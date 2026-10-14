#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径解析：同一份代码要能在「源码目录」和「打包成 exe」两种情形下都找到数据。

打包成单文件 exe 后，`__file__` 指向的是临时解包目录，且**只读、退出即删**；
所以：
  · 只读数据（词表、字符表、字体）→ 跟着 exe 走（解包目录）
  · 用户产物（导出的图）→ 必须写到用户目录，不能写解包目录
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def data_root() -> Path:
    """只读数据的根目录。

    - 打包后：PyInstaller 的解包目录（sys._MEIPASS）
    - 源码运行：huiwen/ 的上一级（即项目里的 huiwen/ 目录本身）
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def output_dir() -> Path:
    """用户产物目录。

    **不能想当然**：实测在打包版里写 `~/Documents/洄文导出` 会拿到
    `PermissionError: [WinError 5] 拒绝访问`（这台机器上文档目录对子进程不开放）。
    所以按优先级试几个候选，取第一个**真能写**的：
      1. exe 自己所在的目录（绿色版的正统做法，便携）
      2. 系统临时目录
      3. 用户主目录
    """
    cands: list[Path] = []
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        cands.append(exe_dir / "洄文导出")
        tmp = os.environ.get("TEMP") or os.environ.get("TMP")
        if tmp:
            cands.append(Path(tmp) / "洄文导出")
        cands.append(Path.home() / "洄文导出")
    else:
        cands.append(Path(__file__).resolve().parent / "output")

    last_err: Exception | None = None
    for c in cands:
        try:
            c.mkdir(parents=True, exist_ok=True)
            probe = c / "._write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return c
        except Exception as exc:                            # noqa: BLE001
            last_err = exc
            continue
    raise RuntimeError(f"找不到可写的输出目录（试过 {[str(c) for c in cands]}）：{last_err}")


def font_path() -> Path:
    return data_root() / "font" / "GalHuiwen.ttf"


def lexicon_path() -> Path:
    return data_root() / "lexicon.tsv"


def characters_path() -> Path:
    return data_root() / "characters.json"


def syllabary_path() -> Path:
    return data_root() / "tools" / "syllabary.tsv"
