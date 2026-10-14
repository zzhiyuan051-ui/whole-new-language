#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用递增规模跑转换，看耗时是线性还是超线性。

思路：如果 2 倍行数带来远大于 2 倍的耗时，说明有 O(n²) 的东西；
再配合"卡在第几行"就能定位。每步单独 flush，避免缓冲遮蔽进度。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "dict" / "洄文大字典.md"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dict_to_docx as C  # noqa: E402

all_lines = MD.read_text(encoding="utf-8").splitlines()
TMP_SRC = MD.parent / "_scale_test.md"
TMP_OUT = MD.parent / "_scale_test.docx"


def run(n: int) -> float:
    TMP_SRC.write_text("\n".join(all_lines[:n]), encoding="utf-8")
    C.SRC, C.OUT = TMP_SRC, TMP_OUT
    t0 = time.time()
    C.convert()
    return time.time() - t0


print("=== 递增规模 ===", flush=True)
prev = 0.0
for n in (2000, 4000, 8000, 16000):
    dt = run(n)
    ratio = (dt / prev) if prev else 0
    print(f"  {n:>6,} 行  {dt:7.2f} 秒   倍数 {ratio:5.2f}", flush=True)
    prev = dt
    if dt > 120:
        print("  （太慢了，停止加码）", flush=True)
        break
