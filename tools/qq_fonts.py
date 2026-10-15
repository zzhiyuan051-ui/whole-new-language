#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 QQ(NT) 的 asar 里找出字体栈与字体引用。

用途：想弄清 QQ 客户端到底用哪些字体名、怎么声明字体族，就拆它的 application.asar。
这是一次性的调研工具，**不是**洄文运行链路的一部分。

两个坑（都踩过）：
  1. 数据区偏移是 `16 + header 的字节数`，不是 8 或 12。
  2. asar 里的条目可能带 `unpacked: true` —— 那种文件**不在包内**，
     而在 `app.asar.unpacked/` 目录里。第一版没过滤它，读到的是垃圾。

用法：
  python tools/qq_fonts.py                      # 自动找已安装的 QQ
  python tools/qq_fonts.py --qq "D:\\QQNT\\..."  # 指定 resources/app 目录
"""
from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

# ⚠️ 不要在这里写死本机路径 —— 那会把作者的个人目录带进公开仓库。
# 默认按常见安装位置探测，探测不到就用 --qq 指定。
QQ_CANDIDATES = [
    Path(r"C:\Program Files\Tencent\QQNT"),
    Path(r"C:\Program Files (x86)\Tencent\QQNT"),
    Path.home() / "AppData" / "Local" / "Programs" / "Tencent" / "QQNT",
]


def find_asar(explicit: str | None) -> Path:
    """返回 application.asar 的路径。"""
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p
        cand = p / "application.asar"
        if cand.is_file():
            return cand
        raise SystemExit(f"在 {p} 下找不到 application.asar")

    for root in QQ_CANDIDATES:
        if not root.is_dir():
            continue
        # QQNT 版本目录形如 versions/9.9.27-45758
        for ver in sorted(root.glob("versions/*"), reverse=True):
            cand = ver / "resources" / "app" / "application.asar"
            if cand.is_file():
                print(f"自动探测到：{cand}")
                return cand
    raise SystemExit(
        "未自动找到 QQ 的 application.asar。请用 --qq 指定 resources/app 目录，\n"
        "例如： --qq \"C:\\Program Files\\Tencent\\QQNT\\versions\\<版本>\\resources\\app\"")


def load(path: Path):
    with path.open("rb") as f:
        _a, hdr_size, _b, _c = struct.unpack("<IIII", f.read(16))
        raw = f.read(hdr_size)
    obj, _ = json.JSONDecoder().raw_decode(raw.decode("utf-8", errors="replace"))
    return obj, 16 + hdr_size


def walk(node, prefix=""):
    for name, meta in node.get("files", {}).items():
        p = f"{prefix}/{name}" if prefix else name
        if "files" in meta:
            yield from walk(meta, p)
        else:
            yield p, meta


def main() -> int:
    ap = argparse.ArgumentParser(description="拆 QQ(NT) 的 asar，列出字体栈")
    ap.add_argument("--qq", default=None,
                    help="QQ 的 resources/app 目录，或 application.asar 本身")
    ap.add_argument("--out", default=None, help="报告输出路径（默认 tools/qq_fonts.txt）")
    args = ap.parse_args()

    asar = find_asar(args.qq)
    out_path = Path(args.out) if args.out else \
        Path(__file__).resolve().parent / "qq_fonts.txt"

    header, data_start = load(asar)
    entries = list(walk(header))
    packed = [(p, m) for p, m in entries if not m.get("unpacked")]
    unpacked = [(p, m) for p, m in entries if m.get("unpacked")]
    print(f"包内文件 {len(entries)}：实装 {len(packed)}，unpacked {len(unpacked)}")
    print(f"数据区起点 {data_start}")

    out: list[str] = []
    fonts: dict[str, int] = {}
    refs: list[tuple[str, str]] = []

    with asar.open("rb") as f:
        for p, m in packed:
            size = m.get("size", 0)
            if not p.lower().endswith((".css", ".js", ".json", ".html")):
                continue
            if size == 0 or size > 20 * 1024 * 1024:
                continue
            f.seek(data_start + int(m["offset"]))
            try:
                text = f.read(size).decode("utf-8")
            except UnicodeDecodeError:
                continue
            found = 0
            for mm in re.finditer(r"font-family\s*:\s*([^;}{]{1,160})", text):
                decl = mm.group(1).strip()
                found += 1
                for name in re.findall(r"[\"']([^\"']{1,60})[\"']|\b([A-Za-z\u4e00-\u9fff][\w\- ]{2,40})", decl):
                    n = (name[0] or name[1]).strip()
                    if n and n.lower() not in (
                            "sans-serif", "serif", "monospace", "system-ui", "ui-sans-serif",
                            "ui-monospace", "ui-serif", "emoji", "math", "fangsong",
                            "inherit", "initial", "unset", "auto", "none", "normal"):
                        fonts[n] = fonts.get(n, 0) + 1
            for mm in re.finditer(r"fontFamily\s*[:=]\s*[`\"']([^`\"']{1,160})[`\"']", text):
                found += 1
                for name in re.findall(r"[\"']([^\"']{1,60})[\"']", mm.group(1)):
                    fonts[name.strip()] = fonts.get(name.strip(), 0) + 1
            for r in set(re.findall(r"[\w\-/\.]{2,60}\.(?:ttf|otf|ttc|woff2?)", text, re.I)):
                refs.append((p, r))
            if found:
                out.append(f"--- {p}  ({found} 处)")

    print(f"\n找到 font-family/fontFamily 的文件: {len(out)}")
    print("\n出现最多的字体名（下手点）:")
    for n, c in sorted(fonts.items(), key=lambda x: -x[1])[:35]:
        print(f"   {c:4d}  {n}")

    print(f"\n字体文件引用（{len(refs)} 条，前 12）:")
    for p, r in refs[:12]:
        print(f"   {r}   <- {p}")

    out_path.write_text("\n".join(out + [""] + [f"{c}\t{n}" for n, c in
                                                sorted(fonts.items(), key=lambda x: -x[1])]
                                   + [""] + [f"{r}\t{p}" for p, r in refs]),
                        encoding="utf-8")
    print(f"\n已写入 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
