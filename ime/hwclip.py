#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一张 PIL 图片放进 Windows 剪贴板。

为什么要这个：
  洄文用 Unicode 私用区，**别人没装字体就看不见，装了在 Chromium 程序里也看不见**。
  所以"发给别人"唯一可靠的方式是**发图**。
  有了它：打好字 → 复制为图片 → 在 QQ/微信里 Ctrl+V 直接发，对方一定看得见。

为什么不用 pywin32：这台机器没装，而且为一个功能拉一个依赖不划算。
直接调 user32/kernel32 就够了。

两个必须注意的点（否则会静默失败或崩溃）：
  1. **64 位下必须声明 restype**。GlobalAlloc 返回的是句柄（指针宽度），
     不声明的话 ctypes 默认当 int，高 32 位被截断 → 句柄无效。
  2. 剪贴板格式要同时放 CF_DIB 和注册格式 "PNG"。
     CF_DIB 兼容性最好（QQ/微信/Word 都吃），PNG 保留透明度给新程序。
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from io import BytesIO

from PIL import Image

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CF_DIB = 8
GMEM_MOVEABLE = 0x0002

# —— 句柄宽度必须显式声明（64 位）——
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]

user32.OpenClipboard.restype = wintypes.BOOL
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.CloseClipboard.restype = wintypes.BOOL
user32.RegisterClipboardFormatW.restype = wintypes.UINT
user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]


def _to_dib(img: Image.Image) -> bytes:
    """PIL 存成 BMP，去掉 14 字节文件头，剩下的就是 DIB（剪贴板要的形态）。"""
    buf = BytesIO()
    img.convert("RGB").save(buf, format="BMP")
    return buf.getvalue()[14:]


def _to_png(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _put(fmt: int, data: bytes) -> None:
    h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not h:
        raise OSError(f"GlobalAlloc 失败 ({len(data)} 字节)")
    p = kernel32.GlobalLock(h)
    if not p:
        kernel32.GlobalFree(h)
        raise OSError("GlobalLock 失败")
    try:
        ctypes.memmove(p, data, len(data))
    finally:
        kernel32.GlobalUnlock(h)
    # 交给系统之后就不能再 free —— 所有权转移了
    if not user32.SetClipboardData(fmt, h):
        kernel32.GlobalFree(h)
        raise OSError(f"SetClipboardData(格式 {fmt}) 失败")


def copy_image(img: Image.Image) -> dict:
    """把图片放进剪贴板。返回放进去的格式与字节数，便于如实回报。"""
    dib = _to_dib(img)
    png = _to_png(img)

    if not user32.OpenClipboard(None):
        raise OSError(f"OpenClipboard 失败，错误码 {ctypes.get_last_error()}")
    try:
        if not user32.EmptyClipboard():
            raise OSError("EmptyClipboard 失败")
        _put(CF_DIB, dib)
        fmt_png = user32.RegisterClipboardFormatW("PNG")
        placed = {"CF_DIB": len(dib)}
        if fmt_png:
            _put(fmt_png, png)
            placed["PNG"] = len(png)
    finally:
        user32.CloseClipboard()

    placed["size"] = f"{img.width}x{img.height}"
    return placed


def read_back_dib() -> Image.Image | None:
    """从剪贴板读回 CF_DIB 并还原成图片。用来确认"真的放进去了"，而不是只信返回值。"""
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    if not user32.OpenClipboard(None):
        return None
    try:
        h = user32.GetClipboardData(CF_DIB)
        if not h:
            return None
        p = kernel32.GlobalLock(h)
        if not p:
            return None
        try:
            # DIB 头里的 biSize 之后是宽高（各 4 字节，有符号）
            header = ctypes.string_at(p, 40)
            bi_size = int.from_bytes(header[0:4], "little")
            width = int.from_bytes(header[4:8], "little", signed=True)
            height = int.from_bytes(header[8:12], "little", signed=True)
            bit_count = int.from_bytes(header[14:16], "little")
            total = bi_size + abs(height) * (((width * bit_count // 8) + 3) // 4 * 4)
            raw = ctypes.string_at(p, total)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()

    # 补一个 BMP 文件头，交给 PIL 解码
    import struct
    offset = 14 + bi_size
    file_header = b"BM" + struct.pack("<IHHI", 14 + len(raw), 0, 0, offset)
    return Image.open(BytesIO(file_header + raw))


if __name__ == "__main__":
    # 自检：放一张图进去，再**读回来**核对尺寸与像素
    from PIL import ImageDraw

    test = Image.new("RGB", (240, 90), "#ffffff")
    ImageDraw.Draw(test).text((12, 30), "huiwen clipboard test", fill="#000000")
    placed = copy_image(test)
    print("放入剪贴板:", placed)

    back = read_back_dib()
    if back is None:
        print("✘ 读不回来 —— 剪贴板里没有 CF_DIB")
        raise SystemExit(1)
    print(f"读回 CF_DIB: {back.width}x{back.height}  模式 {back.mode}")
    ok = (back.width, back.height) == (test.width, test.height)
    # 再比一下非白像素数量，确认不是一张空白
    def ink(im):
        g = im.convert("L")
        return sum(1 for v in g.getdata() if v < 200)
    print(f"  非白像素：原图 {ink(test)}  读回 {ink(back)}")
    print("✔ 剪贴板图片写入并读回成功" if ok else "✘ 尺寸不符")
    raise SystemExit(0 if ok else 1)
