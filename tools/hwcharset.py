#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 字符总表（15000 字）

「字」在洄文里是**书写单位**，与「词」不是一回事：
  · 已定义字符：有音、有义、有字形（＝词表里的 3000 条）
  · 备用字符：有字形、有类号，但音与义尚未指派（＝字形空间里已成形而待用的字）

为什么要预留：洄文的字形是 f(编号) 生成的，编号空间 4^8 = 65536。
把编号空间里**前 15000 个**都算作「本字表收录的字」，就得到 15000 个字形；
其中 3000 个已有词义，其余 12000 个是**已成形待指派**的字——
新词一旦定稿，只要给它一个编号，字形立刻存在，不需要重画。

输出：
  characters.tsv / characters.json   全 15000 字（字形编号、类号、状态、标签）
  tools/hwchar.py 的查询函数         按编号/标签查字
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import syllabary as S
import hwglyph as G

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TARGET = 15000
NCLASS = len(S.DOMAINS)      # 44 个语义类（40 个词场 + 虚词类）


def load_lexicon() -> list[dict]:
    lines = (ROOT / "lexicon.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]


def main() -> None:
    rows = load_lexicon()
    by_glyph = {int(r["glyph"]): r for r in rows}
    defined = len(rows)
    if defined > TARGET:
        raise SystemExit(f"词表 {defined} 条已超过字符目标 {TARGET}")

    # ---- 家族分配：由词表决定（hwcompile 已用贪心算好），此处只读取 ----
    #   若词表里没有 family 列（旧版），则现算一遍。
    fam: dict[int, int] = {}
    for r in rows:
        if "family" in r and str(r["family"]).strip() != "":
            fam[int(r["glyph"])] = int(r["family"])
    if not fam:
        fam = assign_families(sorted(by_glyph))

    out = []
    for i in range(TARGET):
        r = by_glyph.get(i)
        if r:
            cp = int(r["codepoint"]) if str(r.get("codepoint", "")).strip() else None
            out.append({
                "glyph": i, "status": "defined", "class_no": int(r["class_no"]),
                "class_zh": r["class_zh"], "family": fam.get(i, 0),
                "family_zh": G.FAMILY_ZH[fam.get(i, 0)],
                "codepoint": cp,
                "form": r["form"], "syll": r["syll"], "zh": r["zh"], "en": r["en"],
                "pos": r["pos"], "kind": r["kind"], "label": f'{r["syll"]} {r["zh"]}',
            })
        else:
            cls = i % NCLASS
            out.append({
                "glyph": i, "status": "reserved", "class_no": cls,
                "class_zh": (S.DOMAINS[cls][1] if cls < len(S.DOMAINS) else "虚词"),
                "family": 0, "family_zh": G.FAMILY_ZH[0],
                # 备用字**没有码位**：它还没被指派给任何词，也就没人会打它。
                # 进字体需要码位，而留白在这里是诚实的。
                "codepoint": None,
                "form": "", "syll": "", "zh": "", "en": "", "pos": "",
                "kind": "spare", "label": f"〔未指派 {i}〕",
            })

    fields = ["glyph", "status", "class_no", "class_zh", "family", "family_zh",
              "codepoint", "form", "syll", "zh", "en", "pos", "kind", "label"]
    lines = ["\t".join(fields)]
    for c in out:
        lines.append("\t".join(str(c[f]) for f in fields))
    (ROOT / "characters.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ROOT / "characters.json").write_text(
        json.dumps({"target": TARGET, "glyph_space": G.GLYPH_SPACE,
                    "defined": defined, "reserved": TARGET - defined,
                    "class_count": G.CLASS_COUNT, "mark_count": G.MARK_COUNT,
                    "family_count": G.FAMILY_COUNT,
                    "characters": out}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    from collections import Counter as _C
    fz = _C(c["family_zh"] for c in out if c["status"] == "defined")
    print(f"字符总表 {len(out)} 字：已定义 {defined}｜备用 {len(out)-defined}"
          f"（字形空间 {G.GLYPH_SPACE}，尚余 {G.GLYPH_SPACE - TARGET} 个未收录）")
    print(f"语义类 {G.CLASS_COUNT} 个｜类标记 {G.MARK_COUNT} 式｜"
          f"家族纹 {G.FAMILY_COUNT} 式（用四角预留格）")
    print("家族分布：", "  ".join(f"{k}{v}" for k, v in fz.most_common()))


def visual_key(glyph: int) -> tuple:
    """视觉指纹：先骨架、再数位模式。用于把相似的字排到一起（便于下一轮挑开）。"""
    return (glyph % 3,
            glyph // G.WEIGHT[1] % 4, glyph // G.WEIGHT[2] % 4,
            glyph // G.WEIGHT[3] % 4, glyph // G.WEIGHT[4] % 4,
            glyph // G.WEIGHT[5] % 4, glyph // G.WEIGHT[6] % 4,
            glyph // G.WEIGHT[7] % 4, glyph // G.WEIGHT[8] % 4, glyph)


def _digit_tuple(glyph: int) -> tuple[int, ...]:
    return tuple(glyph // G.WEIGHT[p] % 4 for p in G.USED)


def _dist(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    """两个字的「数位距离」：有几个位的取值不同。"""
    return sum(1 for x, y in zip(a, b) if x != y)


def assign_families(glyphs: list[int]) -> dict[int, int]:
    """贪心分配家族号：每个字放进「与已有成员最不像」的那个家族。

    为什么不能用「排序后轮流发号」：排序只保证**顺序上相邻**的像，
    而轮流发号未必把它们分开（编号在视觉上并不连续）。
    贪心直接优化目标本身——让同家族内最近的一对尽量远。
    同时用平衡约束避免某一家族被塞满。
    """
    per = max(1, len(glyphs) // G.FAMILY_COUNT) + 1
    counts = [0] * G.FAMILY_COUNT
    members: list[list[tuple[int, ...]]] = [[] for _ in range(G.FAMILY_COUNT)]
    out: dict[int, int] = {}
    for g in sorted(glyphs, key=visual_key):
        dg = _digit_tuple(g)
        best, best_score = None, None
        for f in range(G.FAMILY_COUNT):
            if counts[f] >= per:
                continue
            # 与本家族已有成员的最近距离：越大越好
            mind = min((_dist(dg, m) for m in members[f]), default=99)
            score = (mind, -counts[f])
            if best_score is None or score > best_score:
                best, best_score = f, score
        if best is None:                       # 都满了（浮点取整），退回最小家族
            best = min(range(G.FAMILY_COUNT), key=lambda f: counts[f])
        out[g] = best
        counts[best] += 1
        members[best].append(dg)
    return out


if __name__ == "__main__":
    main()
