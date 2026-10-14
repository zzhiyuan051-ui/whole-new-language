#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 词表扩容：用 20 个派生式把词根派生成完整词表

设计（重要）：
  · 词形 = 词根音节 + 派生语素音节，**机械合成、可复算**，不是随口编的
  · 中文词与中英定义由派生式模板套出（"雨" + "{X}者" → "雨者"），因此**必然正确**
  · 一个词根配哪一个派生式，由**词根的词性**与语义场决定（见 _patterns_for）
  · 目标：词根 512 + 派生 2500+ ＝ 3000+ 条

输出：tools/drafts/derived.tsv（与各场草稿同格式，六列）
"""
from __future__ import annotations

import sys
from pathlib import Path

import patterns as PT
import syllabary as S

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DRAFTS = HERE / "drafts"

TARGET_TOTAL = 3000
SLOTS = 6                    # 派生词槽位数（音节 1 + 语素 1 = 2 音节）


def load_domain_drafts() -> dict[str, list[dict]]:
    """载入前 20 场的词根（含音节、中文、英文、词性）。"""
    out: dict[str, list[dict]] = {}
    for di, did in enumerate(S.DOMAIN_ORDER):
        p = DRAFTS / f"domain_{di+1:02d}_{did}.tsv"
        if not p.exists():
            continue
        rows = []
        for ln in p.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            f = ln.split("\t")
            if len(f) == 6:
                rows.append({"syll": f[0], "zh": f[1], "en": f[2], "pos": f[3],
                             "dz": f[4], "de": f[5], "dom": did})
        out[did] = rows
    return out


def load_fwords() -> list[dict]:
    p = HERE / "fwords.tsv"
    rows = []
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            f = ln.split("\t")
            if len(f) == 6:
                rows.append({"syll": f[0], "zh": f[1], "en": f[2], "pos": f[3],
                             "dz": f[4], "de": f[5], "dom": None})
    return rows


# 派生式与词性的适配：体词根多走名词化，谓词根多走动词化/性状化
def _patterns_for(pos: str) -> list[str]:
    if pos == "n":
        return ["AG", "IN", "LO", "AB", "CA", "EF", "ME", "DU", "TI", "AR",
                "MI", "MA", "NE", "SI", "EX", "PA"]
    if pos == "a":
        return ["AB", "MI", "MA", "NE", "SI", "EX", "PA", "DU", "AG", "LO",
                "VE", "CO", "AR", "CA"]
    if pos == "v":
        return ["AG", "IN", "LO", "ME", "VE", "CO", "RE", "PR", "CA", "EF",
                "TI", "DU", "AB", "NE"]
    return ["AB", "DU", "EX", "PA", "AG", "LO", "ME", "AR"]


def build(target: int = TARGET_TOTAL, seed: int = 20240601) -> list[dict]:
    import random
    rng = random.Random(seed)
    blk, _sy = S.blocks()
    pool = [c["syll"] for c in blk["_deriv_pool"]]
    affix = PT.syllabic_patterns(pool)
    roots = load_domain_drafts()
    fwords = load_fwords()

    per_round = (SLOTS - 1) * len(roots)         # 每轮所有场上各出 SLOTS-1 个派生词
    out: list[dict] = []

    # ---- 先把「词根本身」也算作词条（它们是词表的主体）
    for did, rows in roots.items():
        for r in rows:
            out.append({"syll": r["syll"], "zh": r["zh"], "en": r["en"], "pos": r["pos"],
                        "dz": r["dz"], "de": r["de"], "dom": r["dom"],
                        "kind": "root", "form": r["syll"]})
    for r in fwords:
        out.append({"syll": r["syll"], "zh": r["zh"], "en": r["en"], "pos": r["pos"],
                    "dz": r["dz"], "de": r["de"], "dom": None,
                    "kind": "function", "form": r["syll"]})

    seen_zh = {r["zh"] for r in out}
    seen_form = {r["form"] for r in out}

    # ---- 再按「一轮一轮」的方式派生，保证覆盖各场
    doms = list(roots)
    k = 0
    while len(out) < target and k < 40:
        k += 1
        for did in doms:
            rows = roots[did]
            for r in rows:
                if len(out) >= target:
                    break
                cands = _patterns_for(r["pos"])
                # 每轮每个词根取 1 个派生式（按轮次与词根位置平移选取，避免总取同几个）
                order = cands[(k - 1) % len(cands):] + cands[:(k - 1) % len(cands)]
                for code in order:
                    pat = PT.PATTERN_BY_CODE[code]
                    asy = affix[code][pat.kind]
                    form = PT.form_of(r["syll"], pat, asy)
                    zh = PT.gloss_of(r["zh"], pat)
                    en = PT.egloss_of(r["en"], pat, r["pos"])
                    if zh in seen_zh or form in seen_form:
                        continue
                    dz, de = PT.defs_of(r["zh"], r["en"], pat, r["pos"])
                    seen_zh.add(zh)
                    seen_form.add(form)
                    out.append({"syll": form.replace(" ", ""), "zh": zh, "en": en,
                                "pos": pat.pos, "dz": dz, "de": de, "dom": did,
                                "kind": "derived", "form": form, "pattern": code})
                    break
    return out


def main() -> None:
    rows = build()
    words = [r for r in rows if r["kind"] in ("root", "function", "derived")]
    derived = [r for r in rows if r["kind"] == "derived"]
    print(f"词条总数 {len(words)}｜词根 {sum(1 for r in words if r['kind']=='root')}"
          f"｜虚词 {sum(1 for r in words if r['kind']=='function')}"
          f"｜派生 {len(derived)}")
    # 落一份派生词草稿（与各场草稿同格式），供编译器合并
    DRAFTS.mkdir(exist_ok=True)
    lines = []
    for r in derived:
        lines.append("\t".join([r["form"], r["zh"], r["en"], r["pos"], r["dz"], r["de"]]))
    (DRAFTS / "derived.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 派生词的场属（词形 → 场 code）：派生词继承**词根所在场**，语义类因此不丢
    import json
    dommap = {r["form"]: r["dom"] for r in derived if r.get("dom")}
    (DRAFTS / "derived_domain.json").write_text(
        json.dumps(dommap, ensure_ascii=False, indent=0), encoding="utf-8")
    patmap = {r["form"]: r.get("pattern", "") for r in derived}
    (DRAFTS / "derived_pattern.json").write_text(
        json.dumps(patmap, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"派生词草稿 → tools/drafts/derived.tsv（{len(lines)} 行，词形列含空格=双音节）")
    print(f"场属映射 → tools/drafts/derived_domain.json（{len(dommap)} 条）"
          f"｜派生式映射 {len(patmap)} 条")
    # 统计
    from collections import Counter
    c = Counter(r.get("pattern") for r in derived)
    print("派生式使用：", "  ".join(f"{k}×{v}" for k, v in c.most_common(8)))
    print("音节数分布：", Counter(len(r["form"].split()) for r in derived))


if __name__ == "__main__":
    sys.exit(main())
