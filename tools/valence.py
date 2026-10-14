#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 临位（槽表）与换声的派生规则 —— spec/02-grammar.md §1.3 的可执行实现。"""
from __future__ import annotations

# 七临位，按默认填写顺序排列
ROLES = ["甲", "乙", "丙", "丁", "戊", "己", "庚"]
ROLE_LATIN = {"甲": "A", "乙": "B", "丙": "C", "丁": "D", "戊": "E", "己": "F", "庚": "G"}
ROLE_GLOSS = {
    "甲": "施事/主体", "乙": "受事/客体", "丙": "予事/受益", "丁": "工具/手段",
    "戊": "处所/时间", "己": "因/由", "庚": "语/题",
}

# 关键词触发：词义里出现这些字眼就要多一个槽
GIVE_HINTS = ("给", "送", "教", "授予", "交给", "递", "传", "卖", "付", "赠", "借出", "告知")
MOVE_HINTS = ("走", "来", "去", "行", "跑", "移", "到达", "离开", "进", "出", "回", "降", "升", "落")
# 命题态度类：所接的是「所言所思的内容」→ 庚位
CONTENT_HINTS = ("说", "问", "答", "想", "信", "疑", "希望", "认为", "觉得", "诉", "倾听",
                 "想象", "回忆", "遗忘", "注意", "分心", "直觉", "论证", "解释", "教导",
                 "解惑", "推理", "学习", "阅读", "书写", "命名", "证实")
# 感受与认知类：所接的是「物」→ 乙位（默认）
SENSE_HINTS = ("看", "听", "闻", "尝", "觉知", "抓住", "握")

# 语义场默认槽表
BY_POS = {
    "n": ["乙"],
    "a": ["乙"],
    "d": ["乙"],
    "v": ["甲", "乙"],
}


def derive(zh: str, en: str, pos: str) -> list[str]:
    """由词义与词性派生槽表。这是推导，不是规定；用户可在 lexicon 里覆写。"""
    slots = list(BY_POS.get(pos, ["乙"]))
    text = zh + " " + en
    if pos == "v":
        if any(h in text for h in GIVE_HINTS):
            slots = ["甲", "丙", "乙"]
        elif any(h in text for h in CONTENT_HINTS):
            slots = ["甲", "庚"]
        elif any(h in text for h in MOVE_HINTS):
            slots = ["甲", "戊", "己"]
    return slots


# 换声（voice）
VOICES = {"体": "n", "貌": "a", "用": "v", "度": "d", "场": "l"}
VOICE_FROM_POS = {"n": "体", "a": "貌", "v": "用", "d": "度"}


def default_voice(pos: str) -> str:
    return VOICE_FROM_POS.get(pos, "体")


def role_of_order(slots: list[str], k: int) -> str:
    """第 k 条临弓（0 起）默认填哪个位；超出的算附带说明，回到乙位。"""
    if k < len(slots):
        return slots[k]
    return "乙"


if __name__ == "__main__":
    for zh, en, pos in [("给", "give", "v"), ("走", "walk", "v"), ("想", "think", "v"),
                        ("雨", "rain", "n"), ("冷", "cold", "a"), ("很", "very", "d")]:
        print(f"{zh:4s} {pos}  →  {' '.join(derive(zh, en, pos))}")
