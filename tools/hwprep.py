#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 字典条目备料

把「能算的部分」全部算好，交给撰写者的只剩散文（理／辨）：

  · 音 / 形 / 义 / 位　—— 全部从 lexicon.tsv 与字形表取，撰写者不得改动
  · 例　—— 由**例句生成器**按语法规则生成三则（源文 + 逐词 + 汉译），
           因此保证语法正确、且不出现词表外的词
  · 理 / 辨　—— 留给撰写者（这是字典与词表的分野）

用法：
    python tools/hwprep.py 1 8        # 备第 1 批（8 条）
    python tools/hwprep.py --all      # 备全部（每批 8 条，写到 dict/batches/）
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BATCH = ROOT / "dict" / "batches"
BATCH.mkdir(parents=True, exist_ok=True)
PER_BATCH = 8

# 例句生成用到的语法骨架（全部取自词表里真实存在的词，见 lexicon.tsv）
EVID = {"亲见": "#see", "亲闻": "#hear", "亲身感受": "#felt",
        "推知": "#infer", "传闻": "#hearsay", "常识": "#common",
        "想象": "#imagine"}

# ---- 发音的中文可懂说明（写给只懂中文的读者）----
ONSET_HINT = {
    "zero": "零声基：直接起元音，如汉语「啊」",
    "p": "汉语拼音 b（不送气，如「爸」的声母）",
    "b": "浊音 b，像英语 bee 的 b（汉语没有，读时让声带先振）",
    "t": "汉语拼音 d（不送气，如「大」的声母）",
    "d": "浊音 d，像英语 day 的 d",
    "k": "汉语拼音 g（不送气，如「哥」的声母）",
    "g": "浊音 g，像英语 go 的 g",
    "m": "汉语拼音 m，如「妈」",
    "n": "汉语拼音 n，如「拿」",
    "s": "汉语拼音 s，如「三」",
    "z": "浊音 z，像英语 zoo 的 z",
    "h": "汉语拼音 h（如「喝」），略靠后",
    "l": "汉语拼音 l，如「拉」",
}
VOWEL_HINT = {
    "a": "如汉语「啊」",
    "e": "如汉语「诶」的前半，口略开",
    "i": "如汉语「衣」",
    "o": "如汉语「哦」",
    "oe": "先摆「诶」的口型再把嘴唇收圆（德语 schön 的 ö）",
    "u": "如汉语「乌」",
    "y": "先摆「衣」的口型再把嘴唇收圆（法语 tu 的 u）",
    "v": "汉语「资」「思」里那个元音（-i），读得紧一些",
}
TONE_HINT = {
    1: "高平调（˥）：像汉语第一声，平平地读",
    2: "中升调（˧˥）：像汉语第二声，往上扬",
    3: "高降调（˥˩）：像汉语第四声，从高往下降",
    4: "短促微降（˦˨）：读得短，末尾略降",
    5: "低平调（˩）：压低嗓子平读，像说悄悄话",
    6: "高微降（˥˧）：起得高，轻轻落一点",
}


def load() -> tuple[list[dict], dict[str, dict]]:
    lines = (ROOT / "lexicon.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    rows = [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]
    return rows, {r["zh"]: r for r in rows}


def pron_hint(r: dict) -> str:
    """给中文读者的发音说明（逐音节拆开讲）。"""
    import syllabary as S
    table = {c["syll"]: c for c in S.all_syllables()}
    bits = []
    for s in r["form"].split():
        c = table.get(s)
        if not c:
            continue
        bits.append(f"`{s}`＝{ONSET_HINT.get(c['onset'], c['onset'])}＋"
                    f"{VOWEL_HINT.get(c['vowel'], c['vowel'])}＋{TONE_HINT[c['tone']]}")
    if len(bits) > 1:
        return "；".join(bits) + "；两音节连读，中间不要停顿"
    return bits[0] if bits else ""


def examples(r: dict, byzh: dict[str, dict]) -> str:
    """生成三则例句（源文 + 逐词 + 汉译）。

    按**词性**分派句型，避免造出语义不通的句子（如「雨中的雨」「我看见雨发生在我身上」）：
      名词 → 作受事被看见、作饰弓的限定者
      动词 → 作谓语，自足或带受事
      形容词 → 饰弓限定一个名词
      副词 → 限定一个动词
    """
    zh, pos = r["zh"], r["pos"]
    ex: list[tuple[str, str, str, str]] = []

    if pos == "n":
        ex.append(("一、作受事，被「看」看见",
                   f"@0 doe2.用　@1 yi6.体　@2 {r['form']}.体　"
                   f"@0 -甲-> 1　@0 -庚-> 2　#see",
                   f"看（用）／我（体）／{zh}（体）／"
                   f"看─甲位→我／看─庚位→{zh}／义标：亲见",
                   f"我看见{zh}。"))
        ex.append(("二、作饰弓的限定者（相当于汉语的「之」）",
                   f"@0 {r['form']}.体　@1 po4.体　@0 => 1　#common",
                   f"{zh}（体）／夜（体）／{zh}─饰弓→夜／义标：常识",
                   f"{zh}之夜。"))
        ex.append(("三、换声为「貌」，当性质用",
                   f"@0 {r['form']}.貌　@1 pe.体　@0 => 1　#common",
                   f"{zh}（换声为貌）／状态（体）／{zh}─饰弓→状态／义标：常识",
                   f"{zh}的状态。"))
    elif pos == "v":
        ex.append(("一、作谓语，接甲位（谁做）",
                   f"@0 {r['form']}.用　@1 yi6.体　@0 -甲-> 1　#see",
                   f"{zh}（用）／我（体）／{zh}─甲位→我／义标：亲见",
                   f"我{zh}。"))
        ex.append(("二、作谓语，同时接甲位与乙位",
                   f"@0 {r['form']}.用　@1 yi6.体　@2 lv2.体　@0 -甲-> 1　@0 -乙-> 2　#see",
                   f"{zh}（用）／我（体）／食物（体）／{zh}─甲位→我／{zh}─乙位→食物／义标：亲见",
                   f"我{zh}食物。"))
        ex.append(("三、换声为「体」，把它当成一件事来谈",
                   f"@0 {r['form']}.体　@1 po4.体　@0 -戊-> 1　#common",
                   f"{zh}（换声为体）／夜（体）／{zh}─戊位→夜／义标：常识",
                   f"{zh}发生在夜里。"))
    elif pos == "a":
        ex.append(("一、作饰弓，限定一个名词",
                   f"@0 {r['form']}.貌　@1 po4.体　@0 => 1　#common",
                   f"{zh}（貌）／夜（体）／{zh}─饰弓→夜／义标：常识",
                   f"{zh}的夜。"))
        ex.append(("二、作谓语（换声为「用」）",
                   f"@0 {r['form']}.用　@1 po4.体　@0 -甲-> 1　#see",
                   f"{zh}（用）／夜（体）／{zh}─甲位→夜／义标：亲见",
                   f"夜{zh}了。"))
        ex.append(("三、换声为「度」，当程度方式用",
                   f"@0 {r['form']}.度　@1 pe2.用　@0 -> 1　#common",
                   f"{zh}（度）／落（用）／{zh}─度位→落／义标：常识",
                   f"{zh}地落下。"))
    else:      # d 副词
        ex.append(("一、限定一个动作，说它做到什么程度",
                   f"@0 {r['form']}.度　@1 pe2.用　@0 -> 1　#common",
                   f"{zh}（度）／落（用）／{zh}─度位→落／义标：常识",
                   f"{zh}地落下。"))
        ex.append(("二、限定一个性状",
                   f"@0 {r['form']}.度　@1 mu.貌　@0 => 1　#common",
                   f"{zh}（度）／直（貌）／{zh}─饰弓→直／义标：常识",
                   f"{zh}直。"))
        ex.append(("三、换声为「度」，当程度方式用",
                   f"@0 {r['form']}.度　@1 no.貌　@0 => 1　#common",
                   f"{zh}（度）／高（貌）／{zh}─饰弓→高／义标：常识",
                   f"{zh}高。"))

    out = []
    for tag, src, gloss, tr in ex:
        out.append(f"　　　{tag}\n　　　　洄文　`{src}`\n"
                   f"　　　　逐词　{gloss}\n　　　　汉译　{tr}")
    return "\n".join(out)


def prep(rows: list[dict], byzh: dict[str, dict], lo: int, hi: int) -> Path:
    chunk = rows[lo:hi]
    out = [f"# 待撰写条目　第 {lo+1}–{hi} 条（共 {len(chunk)} 条）", "",
           "> 本文件已把**音／形／义／位／例**全部算好，你只需补写 **理** 与 **辨** 两个字段。",
           "> 不得改动其余字段；不得引入词表以外的洄文词。",
           "> 读者是**只懂中文、从未接触过洄文的人**，所以一切说明都要用中文讲透。", ""]
    for k, r in enumerate(chunk, start=lo + 1):
        out += [
            f"### {r['id']}　{r['form']}　{r['zh']}",
            "",
            f"**音**　`{r['syll']}`　读作 {r['spell']}｜{r['ipa']}",
            f"　　　　{pron_hint(r)}",
            f"**形**　字形编号 {r['glyph']}｜{r['class_zh']}类",
            f"**义**　{r['def_zh']}",
            f"　　　　{r['def_en']}",
            f"**位**　槽表「{r['slots']}」｜词性 {r['pos']}｜默认换声 {r['voice']}"
            + (f"｜派生式 {r['pattern']}" if r.get("pattern") else ""),
            f"**理**　〔待写〕",
            f"**辨**　〔待写〕",
            "**例**",
            examples(r, byzh),
            "",
            "---",
            "",
        ]
    # 文件名由**实际范围**推出，避免不同范围撞同一个文件名（曾经的 bug）
    first = lo // PER_BATCH + 1
    last = (hi - 1) // PER_BATCH + 1
    p = BATCH / (f"batch-{first:03d}.md" if first == last
                 else f"batch-{first:03d}-{last:03d}.md")
    p.write_text("\n".join(out), encoding="utf-8")
    return p


def main() -> int:
    rows, byzh = load()
    args = sys.argv[1:]
    if not args or args[0] == "--all":
        n = 0
        for lo in range(0, len(rows), PER_BATCH):
            prep(rows, byzh, lo, min(lo + PER_BATCH, len(rows)))
            n += 1
        print(f"已备 {n} 批（每批 {PER_BATCH} 条）→ dict/batches/")
        return 0
    lo, hi = int(args[0]) - 1, int(args[1])
    p = prep(rows, byzh, lo, hi)
    print(f"→ {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
