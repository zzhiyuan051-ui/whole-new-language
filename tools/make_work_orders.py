#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为每个语义场生成一份「起草工单」Markdown，供并行起草者逐格填词。

工单里音节清单是逐格列出的（由 syllabary.py 派生），起草者不得增删改。
"""
from __future__ import annotations

import json
from pathlib import Path

import syllabary as S

HERE = Path(__file__).resolve().parent
OUT = HERE / "work_orders"

HEAD = """# 洄文词根起草工单 · 第 {idx} 场「{zh}」

你正在为一门**人造语言「洄文」**起草词根。洄文与任何自然语言没有发生学关系，
它不是汉语/英语的换皮，词根也不是任何现有词的音译。你只需产出**词义与定义**，
语音（音节）已经由系统分配好了，**不要改音节**。

## 本场边界（只写这个范围内的概念）

{scope}

## 硬性规则

1. **逐格填满**：下面 {n} 个音节，每个音节**恰好**填一个概念，不多不少、不跳过。
   一个音节就是一个词根（单音节词根是洄文的形态底色）。
2. **概念要区分得开**：同一个场里不要出现两个近义词（例如「看」与「瞧」不要都收）。
   每个词根应当是这个场里一个**不可再分**的基本概念。
3. **定义要精炼**：中文定义 ≤ 24 字，英文定义 ≤ 12 词。
4. 词性用缩写：`n` 名词性 / `v` 动词性 / `a` 形容词性 / `d` 副词性。
   洄文的词根在语法上可以换声（体/貌/性），所以你只要给出**最自然的那一种**。
5. 概念不要跑出本场边界，也不要写进别场的典型概念（跨场重复会被校验器打回）。

## 输出格式（严格）

只输出一个 ``` 围栏代码块，内部每行一条记录，**字段之间用一个制表符分隔**，共 6 列：

```
音节<TAB>中文词<TAB>英文词<TAB>词性<TAB>中文定义<TAB>英文定义
```

示例（**音节是假的，仅示范格式**）：

```
xx1\t边界\tedge\tn\t两物相接之处\tthe line where two things meet
xx2\t返回\treturn\tv\t回到原处\tto come back to the place of origin
```

不要写表头，不要写序号，不要写任何解释文字。{n} 行，一行一格，顺序与下表一致。

## 你的音节清单（顺序即输出顺序）

| # | 音节 | 优雅式 | IPA |
|---:|---|---|---|
{rows}
"""


def main():
    blk, sy = S.blocks()
    dom = json.loads((HERE / "domains.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    for idx, did in enumerate(S.DOMAIN_ORDER, start=1):
        cells = blk[did]
        rows = "\n".join(
            f"| {i+1} | `{c['syll']}` | {c['spell']} | {c['ipa']} |"
            for i, c in enumerate(cells))
        text = HEAD.format(idx=idx, zh=dom[did]["zh"], scope=dom[did]["scope"],
                           n=len(cells), rows=rows)
        (OUT / f"domain_{idx:02d}_{did}.md").write_text(text, encoding="utf-8")
    print(f"已生成 {len(S.DOMAIN_ORDER)} 份工单 → {OUT}")


if __name__ == "__main__":
    main()
