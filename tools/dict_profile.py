#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给字典转换器做性能剖析：先量规模，再对一小段做 cProfile 找热点。

为什么值得单独做：第一版跑了 19 分钟 CPU 还没完。
不定位热点就盲目等待或盲目优化，都是浪费。
"""
from __future__ import annotations

import cProfile
import io
import pstats
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "dict" / "洄文大字典.md"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dict_to_docx as C  # noqa: E402


def survey() -> None:
    lines = MD.read_text(encoding="utf-8").splitlines()
    body = [l for l in lines
            if l.strip() and not l.startswith(("|", "#", ">")) and not l.startswith("```")]
    lens = sorted((len(l) for l in body), reverse=True)
    print(f"  总行 {len(lines):,}   正文行 {len(body):,}")
    print(f"  最长正文行 {lens[0]:,} 字   第 10 长 {lens[9]:,}   中位 {lens[len(lens)//2]} 字")
    print(f"  超过 1000 字的行 {sum(1 for x in lens if x > 1000):,}")
    print(f"  超过 5000 字的行 {sum(1 for x in lens if x > 5000):,}")
    nb = sum(len(re.findall(r"\*\*.+?\*\*", l)) for l in body)
    nc = sum(len(re.findall(r"`[^`]+`", l)) for l in body)
    print(f"  粗体 {nb:,}   行内代码 {nc:,}")
    print(f"  预计 run 数 ≈ {len(body) + (nb + nc) * 2:,}")

    # 正则本身会不会回溯爆炸？
    print("\n  正则耗时测试（在最长的一行上）：")
    worst = max(body, key=len)
    t0 = time.time()
    C.TOKEN.split(worst)
    print(f"    最长行 {len(worst):,} 字  split 用时 {time.time()-t0:.3f} 秒")

    t0 = time.time()
    total_tok = 0
    for l in body[:20000]:
        total_tok += len(C.TOKEN.split(l))
    dt = time.time() - t0
    print(f"    前 20000 行 split 用时 {dt:.3f} 秒（外推全量约 {dt*len(body)/20000:.1f} 秒）")


def profile_subset(n_lines: int = 4000) -> None:
    print(f"\n=== cProfile：只转前 {n_lines} 行 ===")
    lines = MD.read_text(encoding="utf-8").splitlines()[:n_lines]
    # 临时把源换成子集
    tmp = MD.parent / "_profile_subset.md"
    tmp.write_text("\n".join(lines), encoding="utf-8")
    orig_src, orig_out = C.SRC, C.OUT
    C.SRC = tmp
    C.OUT = MD.parent / "_profile_subset.docx"
    t0 = time.time()
    pr = cProfile.Profile()
    pr.enable()
    C.convert()
    pr.disable()
    dt = time.time() - t0
    C.SRC, C.OUT = orig_src, orig_out
    print(f"  {n_lines} 行用时 {dt:.1f} 秒 → 外推 {len(MD.read_text(encoding='utf-8').splitlines())} 行"
          f"约 {dt * len(MD.read_text(encoding='utf-8').splitlines()) / n_lines / 60:.1f} 分钟")

    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(18)
    print(s.getvalue())


if __name__ == "__main__":
    print("=== 规模 ===")
    survey()
    profile_subset(int(sys.argv[1]) if len(sys.argv) > 1 else 4000)
