#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文输入法 · 自检（可在窗口版 exe 里跑，结果写文件）

`--windowed` 打包的 exe 没有控制台，所以自检结果写进文本文件，
外部按文件内容判断通过与否。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths                                            # noqa: E402


def run(report: Path | None = None, quiet: bool = False) -> bool:
    lines: list[str] = []

    def say(s: str) -> None:
        lines.append(s)
        if not quiet:
            print(s, flush=True)

    fails: list[str] = []

    def check(cond: bool, label: str, extra: str = "") -> None:
        say(f"[{'通过' if cond else '失败'}] {label}" + (f"　{extra}" if extra else ""))
        if not cond:
            fails.append(label)

    say(f"洄文输入法 · 自检　（打包模式：{paths.is_frozen()}）")
    say(f"数据目录：{paths.data_root()}")
    say(f"产物目录：{paths.output_dir()}")
    say("")

    # 数据文件
    for label, p in (("词表 lexicon.tsv", paths.lexicon_path()),
                     ("字符表 characters.json", paths.characters_path()),
                     ("音节表 syllabary.tsv", paths.syllabary_path()),
                     ("字体 GalHuiwen.ttf", paths.font_path())):
        check(p.exists(), f"数据文件存在：{label}",
              f"{p.stat().st_size // 1024} KB" if p.exists() else str(p))

    from app import App                                    # noqa: E402

    app = App()
    app.update()
    check(len(app.ime.entries) == 3000, "词表 3000 条", f"{len(app.ime.entries)}")
    check(len(app.ime.syllables) == 624, "音节 624 个", f"{len(app.ime.syllables)}")

    # 打字 → 候选
    app.var_in.set("za3")
    app._on_type()
    app.update()
    check(bool(app.cands) and app.cands[0].zh == "爱", "输入 za3 首选「爱」",
          app.cands[0].zh if app.cands else "无候选")

    # 上屏
    for q in ("za3", "yi6", "yo6"):
        app.var_in.set(q)
        app._on_type()
        app._commit(0)
        app.update()
    got = "".join(e.char for e in app.committed)
    # 期望值从引擎查，不硬编码码位：
    # 码位是分配出来的（按字形编号排序依次分私用区），硬编码会在重新分配时失效
    # —— 之前就因此误报过一次。
    want = "".join(app.ime.candidates(q, 1)[0].char for q in ("za3", "yi6", "yo6"))
    check(got == want, "上屏「我爱你」码位与引擎一致",
          " ".join(f"U+{ord(c):04X}" for c in got))
    cps = [ord(c) for c in got]
    check(all(0xE000 <= c <= 0xF8FF for c in cps),
          "上屏码位全在 BMP 私用区内（GDI 的前提）",
          f"U+{min(cps):04X}..U+{max(cps):04X}")

    # 导出
    app._export_png()
    png = paths.output_dir() / "洄文-上屏.png"
    check(png.exists() and png.stat().st_size > 1000, "导出 PNG 成功",
          f"{png.stat().st_size // 1024} KB" if png.exists() else "未生成")

    app._export_svg()
    svg = paths.output_dir() / "洄文-上屏.svg"
    check(svg.exists() and "base64" in svg.read_text(encoding="utf-8"),
          "导出 SVG（内嵌子集字体）成功",
          f"{svg.stat().st_size // 1024} KB" if svg.exists() else "未生成")

    # 汉字反查 / 前缀补全
    app.var_in.set("雨具")
    app._on_type()
    check(bool(app.cands) and app.cands[0].zh == "雨具", "汉字反查「雨具」")
    app.var_in.set("za")
    app._on_type()
    check(len(app.cands) >= 3, "前缀补全「za」出多个候选", f"{len(app.cands)} 个")

    app.destroy()

    say("")
    say("自检全部通过。" if not fails else f"自检失败 {len(fails)} 项：{fails}")

    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("\n".join(lines), encoding="utf-8")
    return not fails


if __name__ == "__main__":
    out = paths.output_dir() / "自检报告.txt"
    ok = run(report=out)
    print(f"报告 → {out}")
    sys.exit(0 if ok else 1)
