#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 字典条目装配

把「备料」（音/形/义/位/例，由 hwprep.py 算出）与「撰写结果」（理/辨，由撰写者提供）
合成为成品条目，写入 dict/entries/*.md。

撰写结果的两种来源都支持：
  1. dict/batches/NNN-done.md   撰写者直接在备料文件里把「〔待写〕」替换掉
  2. dict/batches/NNN.json      {"w00000": {"li": "...", "bian": "..."}, ...}
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DICT = ROOT / "dict"
BATCH = DICT / "batches"
ENTRIES = DICT / "entries"
ENTRIES.mkdir(parents=True, exist_ok=True)

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def nchars(t: str) -> int:
    return len(CJK.findall(t))


def load_entries() -> dict[str, dict]:
    lines = (ROOT / "lexicon.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    rows = [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]
    return {r["id"]: r for r in rows}


def parse_batch(path: Path) -> dict[str, dict]:
    """从备料/已完成文件里取出每条的音形义位例，以及理/辨（若有）。"""
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"^###\s+", text, flags=re.M)[1:]
    out = {}
    for b in blocks:
        head = b.splitlines()[0].strip()
        parts = head.split("　")
        if len(parts) < 3:
            parts = head.split()
        wid = parts[0].strip()
        fields: dict[str, str] = {}
        cur = None
        for line in b.splitlines()[1:]:
            m = re.match(r"^\*\*(音|形|义|位|理|辨|例)\*\*\s*(.*)$", line)
            if m:
                cur = m.group(1)
                fields[cur] = m.group(2).strip()
            elif cur:
                fields[cur] += "\n" + line
        out[wid] = fields
    return out


def fill_from_json(fields: dict[str, str], data: dict) -> None:
    for wid, d in data.items():
        if wid in fields:
            if d.get("li"):
                fields[wid]["理"] = d["li"]
            if d.get("bian"):
                fields[wid]["辨"] = d["bian"]


def render_entry(wid: str, r: dict, f: dict) -> str:
    """合成一条成品条目。"""
    li = (f.get("理") or "").strip()
    bian = (f.get("辨") or "").strip()
    li = li.replace("〔待写〕", "").strip()
    bian = bian.replace("〔待写〕", "").strip()
    ex = (f.get("例") or "").strip()
    body = [
        f"### {r['id']}　{r['form']}　{r['zh']}",
        "",
        f"**音**　`{r['syll']}`　读作 {r['spell']}｜{r['ipa']}",
        f"**形**　字形编号 {r['glyph']}｜{r['class_zh']}类",
        f"**义**　{r['def_zh']}",
        f"　　　　{r['def_en']}",
        f"**位**　槽表「{r['slots']}」｜词性 {r['pos']}｜默认换声 {r['voice']}"
        + (f"｜派生式 {r['pattern']}" if r.get("pattern") else ""),
        f"**理**　{li}" if li else "**理**　",
        f"**辨**　{bian}" if bian else "**辨**　",
        "**例**",
        ex,
    ]
    return "\n".join(body) + "\n"


def main() -> int:
    byid = load_entries()
    written = 0
    missing: list[str] = []
    for bp in sorted(BATCH.glob("batch-*.md")):
        if bp.stem.endswith("-done"):
            continue
        fields = parse_batch(bp)
        jp = bp.with_suffix(".json")
        if jp.exists():
            fill_from_json(fields, json.loads(jp.read_text(encoding="utf-8")))
        for wid, f in fields.items():
            r = byid.get(wid)
            if not r:
                continue
            if not (f.get("理") or "").strip().replace("〔待写〕", ""):
                missing.append(wid)
                continue
            (ENTRIES / f"{wid}.md").write_text(render_entry(wid, r, f), encoding="utf-8")
            written += 1
    total = sum(nchars(p.read_text(encoding="utf-8")) for p in ENTRIES.glob("*.md"))
    print(f"已装配 {written} 条 → dict/entries/（合计 {total} 字）")
    if missing:
        print(f"待撰写 {len(missing)} 条（例：{'、'.join(missing[:6])}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
