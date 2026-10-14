#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 派生词条目的生成（中洄双语）

2488 个派生词按**与词根条目同一体例**逐条生成正文：
音（含给中文读者的发音说明）／形／义／位／理（构词理据）／辨（与词根及同式的分野）／例。

这些条目的「理」「辨」不是人手写的，而是**由构词式计算出来的**——
因为派生词的意义本来就由「词根 × 派生式」决定，这正是洄文的造词规矩：
**能算出来的，不另立词条**。所以这里算出来的解释与词表本身同源、必然一致。

输出：dict/entries-derived/<id>.md
"""
from __future__ import annotations

from pathlib import Path

import patterns as PT
import syllabary as S
from hwprep import VOWEL_HINT, ONSET_HINT, TONE_HINT, examples

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "dict" / "entries-derived"
OUT.mkdir(parents=True, exist_ok=True)


def load() -> list[dict]:
    lines = (ROOT / "lexicon.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]


def pron(form: str) -> str:
    table = {c["syll"]: c for c in S.all_syllables()}
    bits = []
    for s in form.split():
        c = table.get(s)
        if not c:
            continue
        bits.append(f"`{s}`＝{ONSET_HINT.get(c['onset'], c['onset'])}＋"
                    f"{VOWEL_HINT.get(c['vowel'], c['vowel'])}＋{TONE_HINT[c['tone']]}")
    return "；".join(bits) + ("；两音节连读，中间不要停顿" if len(bits) > 1 else "")


def main() -> None:
    rows = load()
    byid = {r["id"]: r for r in rows}
    byform = {r["form"]: r for r in rows}
    byzh = {r["zh"]: r for r in rows}
    deriv = [r for r in rows if r["kind"] == "derived"]
    made = 0
    for r in deriv:
        pat = PT.PATTERN_BY_CODE.get(r["pattern"])
        if not pat:
            continue
        # 找词根：词形里去掉派生语素音节
        parts = r["form"].split()
        root_form = parts[1] if pat.affix == "prefix" and len(parts) > 1 else parts[0]
        root = byform.get(root_form)
        if not root:
            continue
        # 同式兄弟（同一派生式、同一个词根所在场）
        sibs = [x for x in deriv if x["pattern"] == pat.code
                and x["class_no"] == r["class_no"] and x["id"] != r["id"]][:3]
        sib_txt = "、".join(f"{s['zh']}（{s['form']}）" for s in sibs) or "（本场尚无同类）"

        li = (
            f"由词根「{root['zh']}」（`{root['form']}`）加派生式 **{pat.code}「{pat.zh}」**合成，"
            f"词形 `{r['form']}`，派生语素取第 6 调音节。"
            f"按洄文「能算出来的不另立词条」的规矩，本词没有独立编号，"
            f"意思就是「{pat.def_zh.replace('{X}', root['zh']).replace('{x}', root['zh'])}」。"
            f"与词根同属「{r['class_zh']}」类，字形只多出那个派生语素音节。"
        )
        bian = (
            f"与词根「{root['zh']}」：词根问「是什么」，本词问「它的{pat.note}这一面」。"
            f"与同式兄弟（{sib_txt}）：式同根不同。"
            f"与同根别式：取的是同一个「{root['zh']}」的别的侧面。"
        )

        body = [
            f"### {r['id']}　{r['form']}　{r['zh']}",
            "",
            f"**音**　`{r['syll']}`　读作 {r['spell']}｜{r['ipa']}",
            f"　　　　{pron(r['form'])}",
            f"**形**　字形编号 {r['glyph']}｜{r['class_zh']}类（与词根同类）",
            f"**义**　{r['def_zh']}",
            f"　　　　{r['def_en']}",
            f"**位**　槽表「{r['slots']}」｜词性 {r['pos']}｜默认换声 {r['voice']}"
            f"｜派生式 {pat.code}「{pat.zh}」",
            f"　　　　接法与词根一致：先接{'、'.join(r['slots'])}位；"
            f"换声后立场改变，但派生义不变。",
            f"**理**　{li}",
            f"**辨**　{bian}",
            "**例**",
            examples(r, byzh),
            "",
        ]
        (OUT / f"{r['id']}.md").write_text("\n".join(body) + "\n", encoding="utf-8")
        made += 1
    print(f"已生成派生词条目 {made} 条 → dict/entries-derived/")


if __name__ == "__main__":
    main()
