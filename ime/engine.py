#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文输入法 · 核心引擎（与界面无关，可单独使用）

输入方式有三种，都指向同一个词表：
  1. **音节**：输入 `za3`（爱）；多音节词用空格或连写 `yy4 ni5` / `yy4ni5`（雨具）
  2. **音节前缀**：只打 `za`，列出所有以 za 开头的音节
  3. **汉字**：输入 `爱`，反查出洄文词（给「我知道中文但不知道洄文怎么写」的人用）

为什么用罗马字而不是字形：字形的编号是给机器排字用的，人记不住；
而音节是 624 个有限集合、且与词一一对应，是最合适的人机接口。
这正是设计里「形声二分」留给输入法的口子。
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths                                            # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = paths.data_root()


@dataclass(frozen=True)
class Entry:
    id: str
    form: str            # 词形（音节序列，空格分隔）
    syll: str            # 连写形
    zh: str
    en: str
    pos: str
    kind: str            # root / derived / function
    glyph: int
    family: int
    codepoint: int          # 显式码位（不再用 0xE000+编号：编号不连续）
    class_zh: str
    def_zh: str
    pattern: str

    @property
    def char(self) -> str:
        """该词对应的洄文字符（私用区码位）。派生词是双音节，逐音节映射为两个字。"""
        return chr(self.codepoint)


class IME:
    """洄文输入法引擎：输入罗马字 → 候选词。"""

    def __init__(self, lexicon: Path | None = None, characters: Path | None = None):
        self.entries: list[Entry] = []
        self.by_syll: dict[str, list[Entry]] = {}
        self.by_form: dict[str, Entry] = {}
        self.by_zh: dict[str, list[Entry]] = {}
        self.syllables: list[str] = []
        self._load(lexicon or paths.lexicon_path())

    def _load(self, path: Path) -> None:
        lines = path.read_text(encoding="utf-8").splitlines()
        head = lines[0].split("\t")
        for l in lines[1:]:
            if not l.strip():
                continue
            d = dict(zip(head, l.split("\t")))
            e = Entry(
                id=d["id"], form=d["form"], syll=d["syll"], zh=d["zh"], en=d["en"],
                pos=d["pos"], kind=d["kind"], glyph=int(d["glyph"]),
                family=int(d.get("family", 0) or 0),
                codepoint=int(d["codepoint"]), class_zh=d["class_zh"],
                def_zh=d["def_zh"], pattern=d.get("pattern", ""),
            )
            self.entries.append(e)
            self.by_form.setdefault(e.form, e)
            self.by_zh.setdefault(e.zh, []).append(e)
            for s in e.form.split():
                self.by_syll.setdefault(s, [])
                if e not in self.by_syll[s]:
                    self.by_syll[s].append(e)
        # 音节表（用于前缀补全）：从字符表取全部合法音节
        syl = set()
        for l in paths.syllabary_path().read_text(
                encoding="utf-8").splitlines()[1:]:
            f = l.split("\t")
            if f:
                syl.add(f[0])
        self.syllables = sorted(syl)

    # ------------------------------------------------------------ 查询
    @staticmethod
    def norm(s: str) -> str:
        """归一化：去空格、去声调数字。

        这是**输入法的核心规则**：声调可选。
        人打字习惯是「连字母打出来，再从候选里挑」，不该被迫记住声调数字；
        但声调仍然可以打（打了就更准）—— 所以匹配时把两边的数字都剥掉再比。
        """
        return re.sub(r"[^a-z]", "", s.lower())

    def candidates(self, text: str, limit: int = 60) -> list[Entry]:
        """按输入给候选词。

        优先级：**全词精确**（含声调）→ 归一化全词匹配 → 归一化前缀匹配 → 中文反查。
        """
        q = text.strip()
        if not q:
            return []
        out: list[Entry] = []
        seen: set[str] = set()

        def push(items) -> None:
            for e in items:
                if e.id not in seen:
                    seen.add(e.id)
                    out.append(e)

        # 1) 词形精确（`yy4 di6` 或 `yy4di6`）——打了声调就优先按声调给
        #    注意：音节字符类必须含数字（za3 / yy4），否则声调会被吞掉，
        #    多音节词的精确匹配永远落空（这个坑真踩过）。
        form = " ".join(re.findall(r"[a-z]+[0-9]?", q.lower()))
        if form and form in self.by_form:
            push([self.by_form[form]])
        low = q.lower().replace(" ", "")
        if low in self.by_syll:
            push(self.by_syll[low])

        # 2) 归一化匹配：剥掉声调再比
        nq = self.norm(q)
        if nq:
            exact = [e for e in self.entries if self.norm(e.syll) == nq]
            push(exact)
            if len(out) < limit:
                pref = [e for e in self.entries if self.norm(e.syll).startswith(nq)]
                # 短的优先（同前缀时「雨」比「雨具」先用得上）
                pref.sort(key=lambda e: (len(e.syll), e.syll))
                push(pref)

        # 3) 中文反查
        if not out or any("\u4e00" <= c <= "\u9fff" for c in q):
            for zh, es in self.by_zh.items():
                if q in zh:
                    push(es)
        return out[:limit]

    def syllable_hint(self, text: str) -> str:
        """输入提示：把已输入的部分切成合法音节，指出哪一段不合法。"""
        parts = re.findall(r"[a-z]+[0-9]?", text.lower())
        bad = [p for p in parts if p not in self.syllables]
        if not parts:
            return "请输入音节，如 za3，或汉字，如 爱"
        if bad:
            near = [s for s in self.syllables if s.startswith(bad[0][:2])][:5]
            return f"音节「{bad[0]}」不存在" + (f"，相近的有：{'、'.join(near)}" if near else "")
        return "＋".join(f"{p}＝{self.by_syll[p][0].zh}" for p in parts[:4]
                         if p in self.by_syll)

    # ------------------------------------------------------------ 组合
    def render_text(self, entries: list[Entry]) -> str:
        """把若干个词合成洄文文本（逐词映射为字形字符）。"""
        return "".join(e.char for e in entries)

    def lookup_char(self, cp: int) -> Entry | None:
        g = cp - 0xE000
        for e in self.entries:
            if e.glyph == g:
                return e
        return None


if __name__ == "__main__":
    ime = IME()
    print(f"词表 {len(ime.entries)} 条｜音节 {len(ime.syllables)} 个")
    for q in ("za3", "za", "yy4 ni5", "yy4ni5", "爱", "雨"):
        cs = ime.candidates(q, 5)
        print(f"\n输入「{q}」→ {len(cs)} 个候选")
        for e in cs[:5]:
            print(f"    {e.zh:<8}{e.form:<10}{e.en:<26}[{e.kind}] U+{e.codepoint:04X}")
    print("\n提示语示例：", ime.syllable_hint("za3 yyo6"))
