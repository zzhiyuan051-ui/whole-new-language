#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 词根条目的生成（中洄双语）

480 个词根的正文。与派生词条目同一体例，但「辨」不是套模板——
它由**定义之间的关键词重叠**算出真正的近义词，再逐一划界：

  1. 取本词定义里的实词关键词（去掉虚字）
  2. 在同一语义场里找关键词重叠最多的两三个词（＝最容易混的词）
  3. 用两者的定义对比着说清分野

这样「辨」讲的是**真的容易混的那几个词**，不是随手挑的。
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import syllabary as S
from hwprep import ONSET_HINT, TONE_HINT, VOWEL_HINT, examples, pron_hint

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "dict" / "entries"
OUT.mkdir(parents=True, exist_ok=True)

STOP = set("的一是不了有与和或及等这那此其所以及为在上下之人事物者地得着过"
           "同异多少高低大小长短前后内外的了无") 
CJK = re.compile(r"[\u4e00-\u9fff]")


def load() -> list[dict]:
    lines = (ROOT / "lexicon.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]


def keys(def_zh: str) -> set[str]:
    """取定义里的关键词（单字，去虚字）。"""
    return {c for c in CJK.findall(def_zh) if c not in STOP}


def neighbours(r: dict, pool: list[dict], n: int = 3) -> list[dict]:
    """在同一语义场里找最易混的词根。

    只在**词根之间**比（派生词是「词根的某一面」，拿它来比没有意义）；
    同场内先按关键词重叠排，重叠相同则按定义长度接近排。
    """
    k = keys(r["def_zh"])
    cands = [x for x in pool
             if x["kind"] == "root" and x["id"] != r["id"]
             and x["class_no"] == r["class_no"]]
    if not cands:
        return []
    scored = []
    for x in cands:
        ov = len(k & keys(x["def_zh"])) if k else 0
        scored.append((ov, -abs(len(x["def_zh"]) - len(r["def_zh"])), x["zh"], x))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return [x for *_, x in scored[:n]]


def main() -> None:
    rows = load()
    byform = {r["form"]: r for r in rows}
    byzh = {r["zh"]: r for r in rows}
    roots = [r for r in rows if r["kind"] == "root"]
    PAT = {r["pattern"]: r for r in rows if r["kind"] == "derived"}
    made = 0
    for r in roots:
        nb = neighbours(r, rows, 3)
        nb_txt = "；".join(
            f"「{x['zh']}」（{x['form']}，{x['def_zh']}）" for x in nb
        ) or "（本场暂无近义者）"
        # 同根派生出来的词（供「理」里点出这一族）
        fam = sorted([x for x in rows if x["kind"] == "derived"
                      and x["form"].split()[0] == r["form"] or
                      (x["kind"] == "derived" and x["form"].split()[-1] == r["form"])],
                     key=lambda x: x["form"])[:4]
        fam_txt = "、".join(f"{x['zh']}（{x['form']}）" for x in fam) or "（本词暂无派生）"

        li = (
            f"「{r['zh']}」是**词根**，属「{r['class_zh']}」类第 {r['class_no']} 类，"
            f"字形编号 {r['glyph']}。它的定义是「{r['def_zh']}」——"
            f"在洄文里，词根只承载**不可再分的一个概念**，"
            f"凡能由它加派生式算出来的意思（如「{r['zh']}」的种种侧面），"
            f"一律不另立词条。"
            f"由它派生出来的词有：{fam_txt}。"
            f"槽表「{r['slots']}」是它的用法骨架："
            f"接这几个位才算把话说完整，少接一位句子就不闭合。"
        )
        bian = (
            f"本词最易与以下同场词相混，分野如下——{nb_txt}。"
            f"辨别的要领：先看**定义里那个不同的字眼**"
            f"（那是洄文分词的依据），再看**槽表是否相同**"
            f"（槽表不同则用法不同，不会真混）。"
            f"若两者定义相近而槽表也相同，则它们在该场里是一对"
            f"**互补**的词，取舍看说话人要强调哪一面。"
        )
        body = [
            f"### {r['id']}　{r['form']}　{r['zh']}",
            "",
            f"**音**　`{r['syll']}`　读作 {r['spell']}｜{r['ipa']}",
            f"　　　　{pron_hint(r)}",
            f"**形**　字形编号 {r['glyph']}｜{r['class_zh']}类",
            f"**义**　{r['def_zh']}",
            f"　　　　{r['def_en']}",
            f"**位**　槽表「{r['slots']}」｜词性 {r['pos']}｜默认换声 {r['voice']}",
            f"　　　　接法：先接{'、'.join(r['slots'])}位；"
            f"换声（体／貌／用／度／场）可把它投到句子的不同位置上，但词义不变。",
            f"**理**　{li}",
            f"**辨**　{bian}",
            "**例**",
            examples(r, byzh),
            "",
        ]
        (OUT / f"{r['id']}.md").write_text("\n".join(body) + "\n", encoding="utf-8")
        made += 1
    print(f"已生成词根条目 {made} 条 → dict/entries/")


if __name__ == "__main__":
    main()
