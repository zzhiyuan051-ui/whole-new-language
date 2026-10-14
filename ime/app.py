#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文输入法 · 桌面版

一个能下载就用的洄文输入工具：
  · 输入罗马字音节（za3）或汉字（爱），出候选，选中上屏
  · 上屏的是**洄文字形**
  · 可复制；可导出 PNG／SVG（因为别的程序未必装有洄文字体）
  · 带「字表」「词表」浏览，便于查字

**字形为什么用图片显示，而不是直接把字体交给系统**：
  把字体注册进系统（AddFontResourceEx）这条路在本机**没能验证成功**——
  探针自相矛盾，所以不拿它当交付依据。
  改用 PIL 直接把 GalHuiwen.ttf 渲染成图片贴到界面上：
  这条路已用 300 个字形验证过（占格比例全部正常），确定可用。

边界（要说清楚）：这不是系统级输入法（不做 TSF／键盘钩子），
所以它**不能**在别的程序里直接接管打字；用法是「在这里打好，复制走」。
"""
from __future__ import annotations

import sys
import tkinter as tk
from io import BytesIO
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths                                            # noqa: E402
from engine import IME                                   # noqa: E402

ROOT = paths.data_root()          # 只读数据根（打包后 = exe 的解包目录）
FONT_PATH = paths.font_path()
OUT_DIR = paths.output_dir()      # 用户产物目录（打包后 = 文档/洄文导出）

BG = "#fbfaf7"
CARD = "#ffffff"
INK = "#1b1b1f"
MUTED = "#8a857c"
ACCENT = "#a06a2c"
HILITE = "#f2efe9"


class GlyphImages:
    """按需把字形渲染成 Tk 图片并缓存（PIL 直渲，不依赖系统字体注册）。"""

    def __init__(self, tk_root: tk.Misc):
        self.root = tk_root
        self.fonts: dict[int, ImageFont.FreeTypeFont] = {}
        self.cache: dict[tuple[int, int, str], tk.PhotoImage] = {}
        self.ok = FONT_PATH.exists()

    def font(self, px: int) -> ImageFont.FreeTypeFont:
        if px not in self.fonts:
            self.fonts[px] = ImageFont.truetype(str(FONT_PATH), px)
        return self.fonts[px]

    def image(self, cp: int, px: int, color: str = INK) -> tk.PhotoImage:
        key = (cp, px, color)
        if key in self.cache:
            return self.cache[key]
        size = int(px * 1.22)
        img = Image.new("RGB", (size, size), CARD)
        d = ImageDraw.Draw(img)
        d.text((size // 2, size // 2), chr(cp), font=self.font(px),
               fill=color, anchor="mm")
        buf = BytesIO()
        img.save(buf, format="PPM")          # PPM 是 Tk 原生认得的格式
        photo = tk.PhotoImage(master=self.root, data=buf.getvalue(), format="PPM")
        self.cache[key] = photo
        return photo


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("洄文输入法")
        self.geometry("1120x760")
        self.configure(bg=BG)
        self.minsize(920, 600)

        self.ime = IME()
        self.cands = []
        self.committed = []

        self.f_zh = ("Microsoft YaHei", 11)
        self.f_title = ("Microsoft YaHei", 15, "bold")
        self.f_small = ("Microsoft YaHei", 9)
        self.f_mono = ("Consolas", 15)
        self.f_out = ("Microsoft YaHei", 12)

        self.glyphs = GlyphImages(self)
        self._build_ui()
        self._refresh_hint("")
        if not self.glyphs.ok:
            self.status.config(text=f"⚠ 找不到字体文件：{FONT_PATH}")

    # ------------------------------------------------------------ 界面
    def _build_ui(self) -> None:
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(head, text="洄文输入法", font=self.f_title, bg=BG,
                 fg=INK).pack(side="left")
        tk.Label(head, text=f"　词表 {len(self.ime.entries)} 条"
                            f"｜音节 {len(self.ime.syllables)} 个"
                            f"｜字体 GalHuiwen",
                 font=self.f_small, fg=MUTED, bg=BG).pack(side="left")

        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=14, pady=6)
        tk.Label(row, text="输入", font=self.f_zh, bg=BG, fg=INK).pack(side="left")
        self.var_in = tk.StringVar()
        self.ent = tk.Entry(row, textvariable=self.var_in, font=self.f_mono,
                            width=26, relief="solid", bd=1, bg=CARD)
        self.ent.pack(side="left", padx=8, ipady=3)
        self.ent.focus_set()
        self.ent.bind("<KeyRelease>", lambda e: self._on_type())
        self.ent.bind("<Return>", lambda e: self._commit(0))
        tk.Label(row, text="打 za3＝爱　打「爱」也行　多音节 yy4 di6　"
                           "只打开头 za 看全部候选",
                 font=self.f_small, fg=MUTED, bg=BG).pack(side="left")

        self.lbl_hint = tk.Label(self, text="", font=self.f_small, fg=ACCENT,
                                 bg=BG, anchor="w")
        self.lbl_hint.pack(fill="x", padx=14)

        self.cand_frame = tk.Frame(self, bg=HILITE)
        self.cand_frame.pack(fill="x", padx=14, pady=(4, 8))
        tk.Label(self.cand_frame, text="（输入后这里出候选，按 1–9 或点选）",
                 font=self.f_small, bg=HILITE, fg=MUTED).pack(padx=10, pady=40)

        out = tk.Frame(self, bg=BG)
        out.pack(fill="both", expand=True, padx=14)
        tk.Label(out, text="上屏（洄文）", font=self.f_zh, bg=BG, fg=INK,
                 anchor="w").pack(fill="x")
        wrap = tk.Frame(out, bg=CARD, bd=1, relief="solid")
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, bg=CARD, highlightthickness=0, height=150)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.strip = tk.Frame(self.canvas, bg=CARD)
        self.canvas.create_window((6, 6), window=self.strip, anchor="nw")
        self.strip.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.lbl_zh = tk.Label(out, text="", font=self.f_out, fg="#3b3b42",
                               bg=BG, anchor="w", justify="left", wraplength=1050)
        self.lbl_zh.pack(fill="x", pady=(5, 0))

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", padx=14, pady=10)
        for text, cmd in (("复制为图片", self._copy_image),
                          ("复制洄文", self._copy),
                          ("退一格", self._back),
                          ("清空", self._clear),
                          ("导出 PNG", self._export_png),
                          ("导出 SVG", self._export_svg),
                          ("字表", self._show_chars),
                          ("词表", self._show_words),
                          ("帮助", self._help)):
            tk.Button(btns, text=text, font=self.f_zh, command=cmd,
                      bg=CARD, relief="solid", bd=1).pack(side="left", padx=3)

        self.status = tk.Label(self, text="就绪", font=self.f_small, fg=MUTED,
                               bg=BG, anchor="w")
        self.status.pack(fill="x", padx=14, pady=(0, 10))

    # ------------------------------------------------------------ 候选
    def _on_type(self) -> None:
        q = self.var_in.get()
        self.cands = self.ime.candidates(q, 9)
        self._draw_cands()
        self._refresh_hint(q)

    def _refresh_hint(self, q: str) -> None:
        self.lbl_hint.config(text=self.ime.syllable_hint(q) if q else
                             "提示：洄文用罗马字输入（音节＋声调数字）；也可以直接打汉字反查")

    def _draw_cands(self) -> None:
        for w in self.cand_frame.winfo_children():
            w.destroy()
        if not self.cands:
            tk.Label(self.cand_frame, text="（无候选）", font=self.f_zh,
                     bg=HILITE, fg=MUTED).pack(padx=10, pady=40)
            return
        for k, e in enumerate(self.cands[:9]):
            box = tk.Frame(self.cand_frame, bg=CARD, bd=1, relief="solid")
            box.pack(side="left", padx=3, pady=6, fill="y")
            tk.Label(box, text=str(k + 1), font=self.f_small, fg=ACCENT,
                     bg=CARD).pack()
            pic = self.glyphs.image(e.codepoint, 42)
            gl = tk.Label(box, image=pic, bg=CARD, cursor="hand2")
            gl.image = pic
            gl.pack(padx=7)
            tk.Label(box, text=f"{e.zh}\n{e.form}", font=self.f_small, bg=CARD,
                     fg=INK, justify="center").pack(pady=(0, 5))
            for w in box.winfo_children() + [box]:
                w.bind("<Button-1>", lambda _e, i=k: self._commit(i))
        # 数字键快捷选择
        for i in range(1, 10):
            self.ent.bind(str(i), lambda e, k=i - 1: self._commit(k))
        self.ent.focus_set()

    def _commit(self, k: int) -> None:
        if k >= len(self.cands):
            return
        e = self.cands[k]
        self.committed.append(e)
        self.var_in.set("")
        self.cands = []
        self._draw_cands()
        self._refresh_hint("")
        self._redraw_strip()
        self.status.config(text=f"上屏：{e.zh}（{e.form}）")
        self.ent.focus_set()

    def _redraw_strip(self) -> None:
        for w in self.strip.winfo_children():
            w.destroy()
        for e in self.committed:
            cell = tk.Frame(self.strip, bg=CARD)
            cell.pack(side="left", padx=1, pady=2)
            pic = self.glyphs.image(e.codepoint, 104)
            lbl = tk.Label(cell, image=pic, bg=CARD)
            lbl.image = pic
            lbl.pack()
            tk.Label(cell, text=e.zh, font=self.f_small, bg=CARD,
                     fg=MUTED).pack()
        self.lbl_zh.config(
            text=("逐词对照：" + "／".join(f"{e.zh}（{e.form}）"
                                          for e in self.committed[-10:]))
            if self.committed else "")

    def _back(self) -> None:
        if self.committed:
            self.committed.pop()
            self._redraw_strip()

    def _clear(self) -> None:
        self.committed = []
        self._redraw_strip()
        self.status.config(text="已清空")

    # ------------------------------------------------------------ 导出
    def _copy_image(self) -> None:
        """把上屏内容渲染成图片放进剪贴板 —— 这是发给别人唯一可靠的方式。

        为什么不能直接发文字：洄文用 Unicode 私用区。对方没装字体看不见；
        **就算装了，QQ/微信（Chromium 内核）也不会回退到我们的字体，照样看不见**。
        图片没有这个问题：任何程序、任何人的屏幕都能显示。
        """
        if not self.committed:
            messagebox.showinfo("复制为图片", "先输入并上屏几个词吧")
            return
        try:
            import hwclip
            img = self._render_share_image()
            placed = hwclip.copy_image(img)
        except Exception as exc:                            # noqa: BLE001
            messagebox.showerror("复制为图片", f"失败：{exc}")
            return
        self.status.config(
            text=f"已复制图片 {placed['size']} 到剪贴板 —— "
                 f"在 QQ / 微信里按 Ctrl+V 直接发，对方一定看得见")

    def _render_share_image(self) -> Image.Image:
        """分享用的图：白底、大字形、底下带中文意思，方便对方看懂。"""
        seq = self.committed
        per_row = 6
        size, cap, pad = 168, 46, 36
        cols = min(len(seq), per_row)
        rows = (len(seq) + per_row - 1) // per_row
        W = size * cols + pad * 2
        H = (size + cap) * rows + pad * 2
        img = Image.new("RGB", (W, H), "#ffffff")
        d = ImageDraw.Draw(img)
        big = ImageFont.truetype(str(FONT_PATH), int(size * 0.82))
        try:
            small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
        except Exception:                                   # noqa: BLE001
            small = ImageFont.load_default()
        for k, e in enumerate(seq):
            r, c = divmod(k, per_row)
            x = pad + c * size
            y = pad + r * (size + cap)
            d.text((x + size // 2, y + size // 2), e.char, font=big,
                   fill=INK, anchor="mm")
            d.text((x + size // 2, y + size + 6), f"{e.zh}", font=small,
                   fill="#8a8a94", anchor="ma")
        return img

    def _copy(self) -> None:
        if not self.committed:
            messagebox.showinfo("复制", "先输入并上屏几个词吧")
            return
        txt = "".join(e.char for e in self.committed)
        self.clipboard_clear()
        self.clipboard_append(txt)
        self.status.config(
            text=f"已复制 {len(txt)} 个洄文字符（纯文字）—— 只有装了 GalHuiwen 字体的"
                 f"**原生**程序看得见；要发给别人请用「复制为图片」")

    def _render_row(self) -> Image.Image:
        seq = self.committed
        size, pad, cap = 150, 30, 34
        cols = min(len(seq), 8)
        rows = (len(seq) + 7) // 8
        W = size * cols + pad * 2
        H = (size + cap) * rows + pad * 2
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        big = ImageFont.truetype(str(FONT_PATH), size)
        try:
            small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
        except Exception:                                   # noqa: BLE001
            small = ImageFont.load_default()
        for k, e in enumerate(seq):
            r, c = divmod(k, 8)
            x = pad + c * size
            y = pad + r * (size + cap)
            d.text((x + size // 2, y + size // 2), e.char, font=big,
                   fill=INK, anchor="mm")
            d.text((x + size // 2, y + size + 8), f"{e.zh} {e.form}", font=small,
                   fill=MUTED, anchor="ma")
        return img

    def _export_png(self) -> None:
        if not self.committed:
            messagebox.showinfo("导出", "先输入并上屏几个词吧")
            return
        out = OUT_DIR / "洄文-上屏.png"
        self._render_row().save(out)
        self.status.config(text=f"已导出 {out}")

    def _export_svg(self) -> None:
        if not self.committed:
            messagebox.showinfo("导出", "先输入并上屏几个词吧")
            return
        import base64

        from fontTools.subset import Options, Subsetter
        from fontTools.ttLib import TTFont
        cps = [e.codepoint for e in self.committed]
        f = TTFont(str(FONT_PATH))
        opt = Options()
        opt.layout_features = []
        opt.notdef_outline = True
        sub = Subsetter(options=opt)
        sub.populate(unicodes=cps)
        sub.subset(f)
        tmp = OUT_DIR / "_subset.ttf"
        f.save(str(tmp))
        b64 = base64.b64encode(tmp.read_bytes()).decode()
        size, pad, cap = 150, 30, 34
        cols = min(len(cps), 8)
        rows = (len(cps) + 7) // 8
        W, H = size * cols + pad * 2, (size + cap) * rows + pad * 2
        text = "".join(chr(c) for c in cps)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
               f'viewBox="0 0 {W} {H}">'
               f'<style>@font-face{{font-family:"GH";'
               f'src:url(data:font/ttf;base64,{b64}) format("truetype");}}'
               f'text{{font-family:"GH"}}</style>'
               f'<rect width="100%" height="100%" fill="{BG}"/>'
               f'<text x="{pad}" y="{pad + size * 0.9}" font-size="{size}" '
               f'fill="{INK}">{text}</text></svg>')
        out = OUT_DIR / "洄文-上屏.svg"
        out.write_text(svg, encoding="utf-8")
        self.status.config(text=f"已导出 {out}（内嵌字体，任何机器都能看）")

    # ------------------------------------------------------------ 浏览
    def _chars(self) -> list[dict]:
        import json
        return json.loads(paths.characters_path().read_text(
            encoding="utf-8"))["characters"]

    def _show_chars(self) -> None:
        rows = [(int(c["glyph"]), (c.get("label") or str(c["glyph"])))
                for c in self._chars() if c["status"] == "defined"][:336]
        self._browse("洄文字表（前 336 字）", rows)

    def _show_words(self) -> None:
        es = sorted(self.ime.entries, key=lambda e: (e.kind != "root", e.form))
        self._browse("洄文词表（3000 条）",
                     [(e.codepoint, f"{e.zh} {e.form}") for e in es])

    def _browse(self, title: str, rows: list) -> None:
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("980x680")
        win.configure(bg=BG)
        tk.Label(win, text=title, font=self.f_title, bg=BG, fg=INK).pack(pady=8)
        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        per, px = 12, 62
        for i in range(0, len(rows), per):
            line = tk.Frame(inner, bg=BG)
            line.pack(anchor="w", pady=2, padx=6)
            for cp, label in rows[i:i + per]:
                cell = tk.Frame(line, bg=CARD, bd=1, relief="solid")
                cell.pack(side="left", padx=2)
                pic = self.glyphs.image(int(cp), px)
                lbl = tk.Label(cell, image=pic, bg=CARD)
                lbl.image = pic
                lbl.pack()
                tk.Label(cell, text=label, font=self.f_small, bg=CARD, fg=MUTED,
                         wraplength=110).pack(padx=3)
        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _help(self) -> None:
        messagebox.showinfo("洄文输入法 · 帮助", (
            "【怎么打】\n"
            "· 打音节：za3 → 爱　（yy4 → 雨；yy4 di6 → 雨具）\n"
            "· 打前缀：za → 列出所有 za 开头的音节\n"
            "· 打汉字：爱 → 反查出洄文词\n"
            "· 按 1–9 选候选，回车选第一个，也可以直接点方块\n\n"
            "【上屏的是什么】\n"
            "洄文字形（私用区码位 U+E000 起）。\n"
            "本程序自带字体、用 PIL 直接渲染，所以在这里一定看得见。\n"
            "复制到别的程序后，那边需要装 GalHuiwen.ttf 才显示得出。\n"
            "要发给没装字体的人，用「导出 PNG」或「导出 SVG」。\n\n"
            "【这不是系统级输入法】\n"
            "它不会在别的程序里接管打字。用法是：在这里打好，复制走。"))


def _crash_report(exc: BaseException) -> None:
    """把异常写进文件。

    窗口版（--windowed）的 exe **没有 stderr**：异常会被 PyInstaller 吞掉，
    或者弹一个没人点的对话框，看起来就是「程序卡住」。
    所以任何异常都必须落盘，否则没法排查。
    """
    import traceback
    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        out = paths.output_dir() / "崩溃报告.txt"
        out.write_text(f"洄文输入法 崩溃报告\n\n{text}", encoding="utf-8")
    except Exception:                                       # noqa: BLE001
        out = None
    # 有控制台就也打一份
    try:
        if sys.stderr is not None:
            sys.stderr.write(text)
    except Exception:                                       # noqa: BLE001
        pass
    # 最后尝试弹窗告知用户报告位置（窗口版才有意义）
    try:
        import tkinter.messagebox as mb
        mb.showerror("洄文输入法 出错了",
                     f"{type(exc).__name__}: {exc}\n\n"
                     + (f"详细报告已写到：\n{out}" if out else "无法写报告文件"))
    except Exception:                                       # noqa: BLE001
        pass
    _ = text


def _screenshot_mode() -> None:
    """无人值守地截一张真实界面图。

    为什么需要它：GUI 进程会占住调用方的输出管道，直接启动就挂住；
    而「自检通过」只证明窗口**能构造**，不证明**长这样**。
    这个模式重建窗口、自动打字上屏、截屏、退出，不进 mainloop。
    """
    import time

    from PIL import ImageGrab

    app = App()
    # 先把窗口摆到屏幕左上角、并调矮一点：否则窗口底部会超出可截范围，
    # 截出来的图会缺掉按钮那一行（这个坑踩过）。
    app.geometry("1100x880+20+20")
    app.attributes("-topmost", True)
    app.update()
    # 打几个词上屏
    for q in ("za3", "yi6", "yo6"):
        app.var_in.set(q)
        app._on_type()
        app.update()
        app._commit(0)
        app.update()
    # 输入框里留一个「za」让候选条有内容
    app.var_in.set("za")
    app._on_type()
    app.update()
    app.lift()
    app.update_idletasks()
    time.sleep(1.2)                      # 等窗口管理器把窗口画出来
    app.update()
    # 用 Windows 的 GetWindowRect 拿窗口的**真实屏幕矩形**。
    # 靠 Tk 的 winfo_rootx/rooty 推断会偏（实测偏上约 40px，导致底部被裁）。
    import ctypes
    from ctypes import wintypes
    hwnd = int(app.wm_frame(), 16)
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    box = (rect.left, rect.top, rect.right, rect.bottom)
    img = ImageGrab.grab(bbox=box, all_screens=True)
    out = paths.output_dir() / "界面截图.png"
    img.save(out)
    print(f"界面截图 → {out}（{img.width}x{img.height}，窗口矩形 {box}）", flush=True)
    app.destroy()
    print(f"界面截图 → {out}（{img.width}x{img.height}）", flush=True)


def _test_share_mode() -> None:
    """验证「复制为图片」整条链路，结果写文件。

    为什么要有它：窗口版 exe 没有控制台，打包后没法用 print 验证。
    这个模式会真的走一遍 —— 上屏 → 渲染 → 写剪贴板 → **读回** → 比对像素，
    而不是只调一次 API 就说"成功"。
    """
    import hwclip

    out = paths.output_dir() / "分享图自检.txt"
    lines: list[str] = []

    def say(s: str) -> None:
        lines.append(s)

    ok = True
    try:
        app = App()
        app.withdraw()
        app.update_idletasks()

        # 直接用引擎反查填入「我爱你」，避免依赖界面状态
        for zh in ("我", "爱", "你"):
            ent = app.ime.candidates(zh, 1)
            if not ent:
                say(f"✘ 反查不到「{zh}」")
                ok = False
                break
            app.committed.append(ent[0])
            say(f"  上屏 {zh} -> U+{ent[0].codepoint:04X}  {ent[0].char}")

        if ok:
            img = app._render_share_image()
            say(f"  渲染分享图 {img.width}x{img.height}")
            placed = hwclip.copy_image(img)
            say(f"  写入剪贴板: {placed}")

            back = hwclip.read_back_dib()
            if back is None:
                say("✘ 剪贴板里读不回 CF_DIB")
                ok = False
            else:
                say(f"  读回 {back.width}x{back.height}")

                def ink(im):
                    g = im.convert("L")
                    return sum(1 for v in g.get_flattened_data() if v < 200)

                a, b = ink(img), ink(back)
                say(f"  非白像素：原图 {a}  读回 {b}")
                if (back.width, back.height) != (img.width, img.height) or a != b:
                    say("✘ 尺寸或像素不一致")
                    ok = False
        app.destroy()
    except BaseException as exc:                            # noqa: BLE001
        import traceback
        say("✘ 异常：" + repr(exc))
        say(traceback.format_exc())
        ok = False

    say("")
    say("分享图链路：全部通过" if ok else "分享图链路：失败")
    out.write_text("\n".join(lines), encoding="utf-8")
    sys.exit(0 if ok else 1)


def main() -> None:
    try:
        # 窗口版 exe 没有控制台，自检结果写文件（供打包后验证用）
        if "--selftest" in sys.argv:
            import selftest
            ok = selftest.run(report=paths.output_dir() / "自检报告.txt", quiet=True)
            sys.exit(0 if ok else 1)
        if "--screenshot" in sys.argv:
            _screenshot_mode()
            return
        if "--test-share" in sys.argv:
            _test_share_mode()
            return
        App().mainloop()
    except SystemExit:
        raise
    except BaseException as exc:                            # noqa: BLE001
        _crash_report(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
