#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 词表编译器

合成唯一真相源 lexicon.tsv：
  各场草稿（词根）+ fwords.tsv（虚词）+ drafts/derived.tsv（派生词）

列：id 词形 音节 优雅式 IPA 编号i 字形场f 类号 类名 中文词 英文词 词性 槽表 换声
    来源 派生式 字形编号 中英定义

字形编号（glyph）：0 起顺序分配，到 GLYPH_TARGET（默认 15000）为止；
  0..N-1 是「已定义字符」（有音、有义），其余是**备用字形**（有形、无义无音）。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import hwglyph as G
import syllabary as S
import valence as V

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DRAFTS = HERE / "drafts"

DOMAIN_ZH = {d[0]: d[1] for d in S.DOMAINS}
DOMAIN_CLASS = {d[0]: k for k, d in enumerate(S.DOMAINS)}
POS_OK = {"n", "v", "a", "d"}
POS_FUNC = {"prt", "num", "q"}
GLYPH_TARGET = 15000

FIELDS = ["id", "form", "syll", "spell", "ipa", "index", "field", "class_no",
          "class_zh", "zh", "en", "pos", "slots", "voice", "kind", "pattern",
          "glyph", "family", "codepoint", "def_zh", "def_en"]

# Unicode 私用区（BMP 内）：U+E000–U+F8FF，共 6400 个码位。
# 只用 BMP 内的原因是 GDI 拒收跨出 BMP 的字体（见 main() 里的说明）。
PUA_BASE = 0xE000
PUA_END = 0xF8FF


def load_rows(path: Path) -> list[list[str]]:
    rows = []
    for ln, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 6:
            raise SystemExit(f"{path.name}:{ln} 字段数 {len(parts)} ≠ 6 → {line!r}")
        rows.append([p.strip() for p in parts])
    return rows


def spell_of(form: str) -> str:
    """把「音节串」渲染成优雅式：逐音节查音节表的 spell 列。"""
    sy = {c["syll"]: c["spell"] for c in S.all_syllables()}
    return "·".join(sy.get(s, s) for s in form.split())


def ipa_of(form: str) -> str:
    sy = {c["syll"]: c["ipa"] for c in S.all_syllables()}
    return "".join(sy.get(s, "?") for s in form.split())


def record(form: str, zh: str, en: str, pos: str, dz: str, de: str,
           di: int | None, kind: str, pattern: str = "") -> dict:
    if pos in POS_FUNC:
        slots, voice = "—", "虚"
    else:
        slots, voice = "".join(V.derive(zh, en, pos)), V.default_voice(pos)
    cls = DOMAIN_CLASS.get(S.DOMAIN_ORDER[di]) if di is not None else 13
    return {
        "form": form, "syll": form.replace(" ", ""), "spell": spell_of(form),
        "ipa": ipa_of(form), "class_no": cls,
        "class_zh": DOMAIN_ZH[S.DOMAIN_ORDER[di]] if di is not None else "虚词",
        "zh": zh, "en": en, "pos": pos, "slots": slots, "voice": voice,
        "kind": kind, "pattern": pattern, "def_zh": dz, "def_en": de,
    }


def main() -> int:
    blk, sy = S.blocks()
    problems: list[str] = []
    recs: list[dict] = []
    seen_zh: dict[str, str] = {}

    # ---- 1) 单音节词根（前 20 场）
    for di, did in enumerate(S.DOMAIN_ORDER):
        cell = blk[did]
        if not cell:
            continue
        path = DRAFTS / f"domain_{di+1:02d}_{did}.tsv"
        if not path.exists():
            problems.append(f"[缺场] {did} 无草稿 {path.name}")
            continue
        rows = load_rows(path)
        want = [c["syll"] for c in cell]
        got = [r[0] for r in rows]
        if got != want:
            problems.append(f"[音节不符] {did}: 期望 {want[:3]}… 实得 {got[:3]}…")
        for r in rows:
            recs.append(record(r[0], r[1], r[2], r[3], r[4], r[5], di, "root"))

    # ---- 2) 虚词
    fw = HERE / "fwords.tsv"
    if fw.exists():
        for r in load_rows(fw):
            recs.append(record(r[0], r[1], r[2], r[3], r[4], r[5], None, "function"))

    # ---- 3) 派生词（词形为双音节；场属继承词根所在场）
    dv = DRAFTS / "derived.tsv"
    dommap: dict[str, str] = {}
    patmap: dict[str, str] = {}
    dm = DRAFTS / "derived_domain.json"
    if dm.exists():
        dommap = json.loads(dm.read_text(encoding="utf-8"))
    pm = DRAFTS / "derived_pattern.json"
    if pm.exists():
        patmap = json.loads(pm.read_text(encoding="utf-8"))
    if dv.exists():
        for r in load_rows(dv):
            code = dommap.get(r[0])
            di = S.DOMAIN_ORDER.index(code) if code in S.DOMAIN_ORDER else None
            recs.append(record(r[0], r[1], r[2], r[3], r[4], r[5], di, "derived",
                               patmap.get(r[0], "")))
    else:
        problems.append("[缺派生] drafts/derived.tsv 不存在（先跑 hwderive.py）")

    # ---- 4) 查重
    for r in recs:
        key = r["zh"]
        if key in seen_zh:
            problems.append(f"[重复-中文词] {key!r}：{seen_zh[key]} 与 {r['kind']}")
        else:
            seen_zh[key] = r["kind"]
        if len(r["def_zh"]) > 24:
            problems.append(f"[定义过长] {r['zh']}: {len(r['def_zh'])} 字")
        if r["pos"] not in POS_OK | POS_FUNC:
            problems.append(f"[词性] {r['zh']}: {r['pos']!r}")

    # ---- 5) 词形查重（音节序列不得重复）
    forms = Counter(r["form"] for r in recs)
    for f, n in forms.items():
        if n > 1:
            problems.append(f"[重复-词形] {f!r} 出现 {n} 次")

    # ---- 6) 编号与字形
    #   编号按语义类**分块**分配：同类聚在连续区间，且 index % 20 == class_no
    #   （否则字形中央格画的类号会与词的语义类不符——字形与词表必须对得上）
    recs.sort(key=lambda r: (r["class_no"], 0 if r["kind"] == "root"
                             else 1 if r["kind"] == "function" else 2, r["form"]))
    cursors = {c: c for c in range(len(S.DOMAINS))}
    for r in recs:
        c = r["class_no"]
        r["index"] = cursors[c]
        r["field"] = r["index"] % 16
        r["glyph"] = r["index"]
        r["id"] = f"w{r['index']:05d}"
        cursors[c] = cursors[c] + len(S.DOMAINS)
    if max(r["glyph"] for r in recs) >= GLYPH_TARGET:
        ids = [r["glyph"] for r in recs]
        problems.append(f"[编号溢出] 最大字形编号 {max(ids)} ≥ {GLYPH_TARGET}")
    for r in recs:
        if r["glyph"] % len(S.DOMAINS) != r["class_no"]:
            problems.append(f"[字形与类不符] {r['zh']}: glyph {r['glyph']} "
                            f"mod {len(S.DOMAINS)} ≠ class {r['class_no']}")

    # ---- 6b) 家族纹（辨识度维度）
    #   字形只有 3 边框 × 20 标记 = 60 种骨架，3000 个词挤在里面；
    #   用四角预留格画 8 种「家族纹」，并把「长得像」的字分到不同家族。
    #   分配用贪心：每个字放进「与已有成员最不像」的家族。
    import hwcharset as CS
    fam = CS.assign_families([r["glyph"] for r in recs])
    for r in recs:
        r["family"] = fam.get(r["glyph"], 0)

    # ---- 6c) 码位（Unicode 私用区）
    #   为什么不能写成「码位 = 0xE000 + 字形编号」：
    #   已定义的 3000 个字**散布**在 0..7713（按语义类分块编号，块内留空给备用字），
    #   所以编号不是连续的。直接相加会让码位跨到 U+FFFF 之外，
    #   而 **GDI 拒收任何码位越出 BMP 的字体**（实测：U+3400 起 15000 个字通过，
    #   U+E000 起 15000 个被拒，差别只在末码位 U+6E97 vs U+11A97）。
    #   因此按编号排序后**依次分配** U+E000 起的连续私用区码位。
    for rank, r in enumerate(sorted(recs, key=lambda x: x["glyph"])):
        r["codepoint"] = PUA_BASE + rank
    if PUA_BASE + len(recs) - 1 > PUA_END:
        problems.append(f"[码位越界] 需要 {len(recs)} 个私用区码位，"
                        f"但 U+{PUA_BASE:04X}–U+{PUA_END:04X} 只有 "
                        f"{PUA_END - PUA_BASE + 1} 个")

    lines = ["\t".join(FIELDS)]
    for r in recs:
        lines.append("\t".join(str(r[f]) for f in FIELDS))
    (ROOT / "lexicon.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ROOT / "lexicon.json").write_text(
        json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 7) 字符总表（15000 字形）：已定义字符 + 备用字形
    used = [{"glyph": r["glyph"], "label": f'{r["syll"]} {r["zh"]}',
             "class_no": r["class_no"], "kind": r["kind"]} for r in recs]
    defined = len(used)
    spare = [{"glyph": i, "label": str(i), "class_no": i % G.CLASS_COUNT,
              "kind": "spare"} for i in range(defined, GLYPH_TARGET)]
    (ROOT / "characters.json").write_text(
        json.dumps({"defined": used, "spare": spare,
                    "glyph_space": G.GLYPH_SPACE, "target": GLYPH_TARGET},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    kc = Counter(r["kind"] for r in recs)
    print(f"词表 {len(recs)} 条：词根 {kc['root']}｜虚词 {kc['function']}｜派生 {kc['derived']}")
    print(f"字符表 {GLYPH_TARGET} 个字形：已定义 {defined}｜备用 {len(spare)}"
          f"（字形空间 {G.GLYPH_SPACE}）")
    print(f"音节占用 {len({s for r in recs for s in r['form'].split()})} / {len(sy)}"
          f"｜语义类 {len(S.DOMAINS)}")
    if problems:
        print(f"\n校验问题 {len(problems)} 项（前 20）：")
        for p in problems[:20]:
            print("  -", p)
    else:
        print("校验：全部通过")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
