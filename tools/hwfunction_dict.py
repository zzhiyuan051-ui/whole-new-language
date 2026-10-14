#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 虚词条目的生成（中洄双语）

32 个虚词（代词、指示、数词、疑问、语气、义标）。虚词没有槽表，
用法与实词不同，故单列一体：讲「它在句子里起什么作用」。
"""
from __future__ import annotations

from pathlib import Path

from hwprep import pron_hint

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "dict" / "entries-function"
OUT.mkdir(parents=True, exist_ok=True)

# 每个虚词的用法说明（源文写法、作用、例句）
USAGE: dict[str, tuple[str, str, str, str]] = {
    "此": ("近指", "指说话人近旁的人或物", "sa6",
           "@0 sa6.体　@1 doe2.用　@2 yi6.体　@1 -甲-> 2　@1 -庚-> 0　#see"),
    "彼": ("远指", "指离说话人远的人或物", "se6",
           "@0 se6.体　@1 doe2.用　@2 yi6.体　@1 -甲-> 2　@1 -庚-> 0　#see"),
    "我": ("自称", "说话人自己，接任何位都行", "yi6",
           "@0 doe2.用　@1 yi6.体　@0 -甲-> 1　#see"),
    "你": ("对称", "听话人", "yo6",
           "@0 pe3.用　@1 yo6.体　@0 -甲-> 1　#see"),
    "他": ("他称", "第三个人", "yoe6",
           "@0 pe3.用　@1 yoe6.体　@0 -甲-> 1　#hearsay"),
    "它": ("非人他称", "非人的第三方（物、事）", "yu6",
           "@0 doe2.用　@1 yu6.体　@0 -甲-> 1　#see"),
    "此之": ("近指之处", "此处、此时", "sy6",
           "@0 yi.用　@1 sy6.体　@0 -戊-> 1　#see"),
    "自": ("反身", "回指主结自身（代替回指弓）", "sv6",
           "@0 gy2.用　@1 sv6.体　@0 -甲-> 1　#felt"),
    "彼之": ("远指之处", "彼处、彼时", "za6",
           "@0 yi.用　@1 za6.体　@0 -戊-> 1　#hearsay"),
    "别": ("别指", "不是此也不是彼的那一个", "ze6",
           "@0 doe2.用　@1 ze6.体　@0 -甲-> 1　#see"),
    "另": ("另指", "此外的又一个", "zi6",
           "@0 pe3.用　@1 zi6.体　@0 -甲-> 1　#see"),
    "各": ("逐指", "逐一而指，一个一个地", "zo6",
           "@0 sa4.用　@1 zo6.体　@0 -甲-> 1　#common"),
    "诸": ("全指", "全部加在一起", "zoe6",
           "@0 pe2.用　@1 zoe6.体　@0 -甲-> 1　#common"),
    "些": ("部分指", "不确定的一部分", "zu6",
           "@0 doe2.用　@1 zu6.体　@0 -甲-> 1　#see"),
    "一": ("数词", "数目一", "zy6", "@0 te.用　@1 zy6.体　@0 -甲-> 1　#common"),
    "二": ("数词", "数目二", "zv6", "@0 te.用　@1 zv6.体　@0 -甲-> 1　#common"),
    "三": ("数词", "数目三", "ha6", "@0 te.用　@1 ha6.体　@0 -甲-> 1　#common"),
    "几": ("问数", "问数目多少", "he6", "@0 te.用　@1 he6.体　@0 -甲-> 1　#question"),
    "谁": ("问人", "问施事者是谁", "hi6",
           "@0 pe3.用　@1 hi6.体　@0 -甲-> 1　#question"),
    "何": ("问物", "问事物是什么", "ho6",
           "@0 doe2.用　@1 ho6.体　@0 -甲-> 1　#question"),
    "何处": ("问处", "问处所在哪里", "hoe6",
           "@0 yi.用　@1 hoe6.体　@0 -戊-> 1　#question"),
    "何时": ("问时", "问时间在什么时候", "hu6",
           "@0 pe2.用　@1 hu6.体　@0 -戊-> 1　#question"),
    "为何": ("问因", "问原因", "hy6",
           "@0 pe2.用　@1 hy6.体　@0 -己-> 1　#question"),
    "如何": ("问法", "问方式如何", "hv6",
           "@0 pe2.用　@1 hv6.体　@0 -> 1　#question"),
    "疑": ("语气", "疑问语气，罩住整张图", "la6", "? @0 pe2.用　@1 yy4.体　@0 -甲-> 1"),
    "毋": ("语气", "否定语气，罩住整张图", "le6", "~ @0 pe2.用　@1 yy4.体　@0 -甲-> 1"),
    "请": ("语气", "祈使语气，罩住整张图", "li6", "! @0 pe3.用　@1 yo6.体　@0 -甲-> 1"),
    "亲见": ("义标", "信息来源：说话人亲眼所见", "lo6", "#see"),
    "亲闻": ("义标", "信息来源：说话人亲耳所闻", "loe6", "#hear"),
    "推知": ("义标", "信息来源：由痕迹推断", "lu6", "#infer"),
    "闻者": ("义标", "信息来源：听别人说的", "ly6", "#hearsay"),
    "想者": ("义标", "信息来源：虚构、设想", "lv6", "#imagine"),
}


def load() -> list[dict]:
    lines = (ROOT / "lexicon.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]


def main() -> None:
    rows = load()
    fw = [r for r in rows if r["kind"] == "function"]
    made = 0
    for r in fw:
        u = USAGE.get(r["zh"])
        if not u:
            continue
        kind, use, ex_syll, ex_src = u
        body = [
            f"### {r['id']}　{r['form']}　{r['zh']}",
            "",
            f"**音**　`{r['syll']}`　读作 {r['spell']}｜{r['ipa']}",
            f"　　　　{pron_hint(r)}",
            f"**形**　字形编号 {r['glyph']}｜{r['class_zh']}类",
            f"**义**　{r['def_zh']}",
            f"　　　　{r['def_en']}",
            f"**位**　虚词，**无槽表**——它不接临位，而是直接进入句子："
            f"或充当某个位上的论元，或罩住整张图。",
            f"**理**　本词属**{kind}**一类。洄文的虚词取自第 6 调音节"
            f"（编号 520–551），与实词分开——因为虚词的作用不是「指称事物」，"
            f"而是「在句子里占一个位」或「给整句话定语气」。"
            f"用法：{use}。",
            f"**辨**　与实词的分野：实词有槽表，虚词没有。"
            f"虚词本身不构成主结，它总是依附于某个实词；"
            f"若把一个虚词单独摆出来，那句话不闭合。"
            f"与同类虚词的分野：{kind}这一类里，各词分工明确，"
            f"看它占的是哪一个位、或定的是哪一种语气即可分辨。",
            "**例**",
            f"　　　一、{kind}用法",
            f"　　　　洄文　`{ex_src}`",
            f"　　　　汉译　{use}。",
            f"　　　二、连用（虚词 + 实词）",
            f"　　　　洄文　`@0 pe3.用　@1 {r['form']}.体　@0 -甲-> 1　#see`",
            f"　　　　逐词　言说（用）／{r['zh']}（体）／言说─甲位→{r['zh']}／义标：亲见",
            f"　　　　汉译　说{r['zh']}。",
            f"　　　三、换声（虚词一般不变声，此处示其与实词同形的用法）",
            f"　　　　洄文　`@0 {r['form']}.体　@1 po4.体　@0 => 1　#common`",
            f"　　　　逐词　{r['zh']}（体）／夜（体）／{r['zh']}─饰弓→夜／义标：常识",
            f"　　　　汉译　夜之{r['zh']}。",
            "",
        ]
        (OUT / f"{r['id']}.md").write_text("\n".join(body) + "\n", encoding="utf-8")
        made += 1
    print(f"已生成虚词条目 {made} 条 → dict/entries-function/")


if __name__ == "__main__":
    main()
