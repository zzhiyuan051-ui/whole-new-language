#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 派生式（词法引擎）

洄文没有「无限造词权」：词形由**词根音节 + 派生语素音节**机械合成，
所以每一条派生词的音形都是可复算的，不是随口编的。

派生式（20 式）：把「X」换成词根的中文词，即得该派生词的中文词；
英文侧用同一式的英文模板。词性、定义模板也由式决定。

语素池：40 个第 5 调音节（编号 480..519），每式取 2 个（一式两读，
用于分词类：体词读甲、谓词读乙），余下作为将来扩充。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pattern:
    code: str
    zh: str            # 中文构词式模板，如 "{X}者"
    en: str            # 英文构词式模板
    pos: str           # 派生词的词性
    def_zh: str        # 定义模板（{x} = 词根中文词）
    def_en: str
    affix: str         # "suffix" = 语素在后；"prefix" = 语素在前
    kind: str          # n / a / v / d —— 决定取哪一支音节
    note: str = ""


PATTERNS: list[Pattern] = [
    Pattern("AG", "{X}之举", "act of {x}ing", "n",
            "做{x}这件事的行为本身", "the act of {x}ing",
            "suffix", "n", "行为名词化"),
    Pattern("IN", "{X}具", "tool for {x}ing", "n",
            "用于{x}的器具", "an instrument for {x}ing",
            "suffix", "n", "工具名词化"),
    Pattern("LO", "{X}之处", "place of {x}", "n",
            "{X}发生或所在之处", "the place where {x} happens or is",
            "suffix", "n", "处所名词化"),
    Pattern("AB", "{X}性", "quality of being {x}", "n",
            "{X}这一性质本身", "the quality of being {x}",
            "suffix", "n", "性质名词化"),
    Pattern("CA", "{X}之所致", "what {x} brings about", "n",
            "由{x}所引起者", "what is brought about by {x}",
            "suffix", "n", "结果名词化"),
    Pattern("EF", "{X}之所由", "what gives rise to {x}", "n",
            "使{x}得以发生者", "what gives rise to {x}",
            "suffix", "n", "致因名词化"),
    Pattern("ME", "{X}之法", "way of {x}ing", "n",
            "做{x}的门径与次第", "the method or manner of {x}ing",
            "suffix", "n", "方式名词化"),
    Pattern("DU", "{X}之度", "degree of {x}", "n",
            "{X}所达到的深浅", "the degree to which something is {x}",
            "suffix", "n", "程度名词化"),
    Pattern("TI", "{X}之时", "time of {x}", "n",
            "{X}发生的时候", "the time when {x} happens",
            "suffix", "n", "时点名词化"),
    Pattern("AR", "{X}之属", "kind of {x}", "n",
            "{X}所属的类", "the kind to which {x} belongs",
            "suffix", "n", "类别名词化"),
    Pattern("MI", "{X}之小", "small {x}", "a",
            "小的{X}", "a small {x}",
            "prefix", "a", "指小"),
    Pattern("MA", "{X}之大", "great {x}", "a",
            "大的{X}", "a great {x}",
            "prefix", "a", "指大"),
    Pattern("NE", "不{X}", "un-{x}", "a",
            "与{X}相反或缺失{X}的", "lacking {x}, or the opposite of {x}",
            "prefix", "a", "否定"),
    Pattern("SI", "似{X}", "{x}-like", "a",
            "像{X}那样的", "resembling {x}",
            "prefix", "a", "比拟"),
    Pattern("EX", "极{X}", "utterly {x}", "d",
            "在{X}这一点上到极点", "to the utmost degree of {x}",
            "prefix", "d", "极致"),
    Pattern("PA", "略{X}", "slightly {x}", "d",
            "在{X}这一点上稍有所偏", "slightly, in respect of {x}",
            "prefix", "d", "轻微"),
    Pattern("VE", "使{X}", "make {x}", "v",
            "使某物成为{X}", "to cause something to become {x}",
            "prefix", "v", "使成"),
    Pattern("CO", "成{X}", "become {x}", "v",
            "自身转为{X}", "to become {x} oneself",
            "prefix", "v", "转变"),
    Pattern("RE", "再{X}", "re-{x}", "v",
            "把{X}重做一次", "to {x} again",
            "prefix", "v", "重复"),
    Pattern("PR", "能{X}", "can {x}", "v",
            "有能力做{X}", "to be able to {x}",
            "prefix", "v", "能力"),
]

PATTERN_BY_CODE = {p.code: p for p in PATTERNS}


# ---------------------------------------------------------------- 语素池
def syllabic_patterns(deriv_pool: list[str]) -> dict[str, dict[str, str]]:
    """把派生语素池按「一式两读」分给各派生式。

    一式两读：体词性派生取第一读，谓词性派生取第二读——
    这样「{X}者」与「使{X}」虽然同式，听起来不会混。
    """
    out: dict[str, dict[str, str]] = {}
    for k, p in enumerate(PATTERNS):
        a, b = deriv_pool[2 * k], deriv_pool[2 * k + 1]
        out[p.code] = {"n": a, "v": b, "a": a, "d": b}
    return out


def form_of(root_syll: str, pattern: Pattern, affix_syll: str) -> str:
    """合成词形（音节序列）。"""
    if pattern.affix == "suffix":
        return f"{root_syll} {affix_syll}"
    return f"{affix_syll} {root_syll}"


def _stem(root_en: str, pos: str) -> str:
    """把词根的英文词变成可套模板的词干。

    动词去 to；名词**原样用作名词性词干**（英语的名词没有动名词形式，
    套 "-ing" 会造出 actualitying 这种不存在的词，所以名词模板一律用名词本身）。
    """
    e = root_en.strip()
    if pos == "v":
        return e[3:] if e.startswith("to ") else e
    return e


# 名词性词根的英文模板需要名词化说法，这里给一份「式 → 名词性英文模板」的对照
NOUN_EN = {
    "AG": "the act of {x}", "IN": "an instrument of {x}", "LO": "the place of {x}",
    "AB": "the quality of {x}", "CA": "what {x} brings about",
    "EF": "what gives rise to {x}", "ME": "the method of {x}",
    "DU": "the degree of {x}", "TI": "the time of {x}", "AR": "the kind of {x}",
}
NOUN_DE = {
    "AG": "the act of {x}", "IN": "an instrument of {x}", "LO": "the place of {x}",
    "AB": "the quality of being {x}", "CA": "what {x} brings about",
    "EF": "what gives rise to {x}", "ME": "the method of {x}",
    "DU": "the degree of {x}", "TI": "the time of {x}", "AR": "the kind of {x}",
}


def gloss_of(root_zh: str, pattern: Pattern) -> str:
    return pattern.zh.replace("{X}", root_zh)


def egloss_of(root_en: str, pattern: Pattern, pos: str = "n") -> str:
    if pos != "v" and pattern.code in NOUN_EN:
        return NOUN_EN[pattern.code].replace("{x}", root_en)
    return pattern.en.replace("{x}", _stem(root_en, pos)).replace("{X}", root_en)


def defs_of(root_zh: str, root_en: str, pattern: Pattern, pos: str = "n") -> tuple[str, str]:
    """返回 (中文定义, 英文定义)。中文限制 24 字。"""
    if pos != "v" and pattern.code in NOUN_DE:
        de = NOUN_DE[pattern.code].replace("{x}", root_en)
    else:
        stem = _stem(root_en, pos)
        de = pattern.def_en.replace("{x}", stem).replace("{X}", stem)
    dz = pattern.def_zh.replace("{X}", root_zh).replace("{x}", root_zh)
    return dz[:24], de


if __name__ == "__main__":
    import syllabary as S
    blk, sy = S.blocks()
    pool = [c["syll"] for c in blk["_deriv_pool"]]
    print(f"派生式 {len(PATTERNS)} 式｜语素池 {len(pool)} 个")
    m = syllabic_patterns(pool)
    for p in PATTERNS[:6]:
        s = m[p.code]
        print(f"  {p.code} {p.zh:8s} 语素 n={s['n']:<5} v={s['v']:<5} "
              f"例：{gloss_of('雨', p):8s} 词形 {form_of('yy4', p, s['n'])}")
