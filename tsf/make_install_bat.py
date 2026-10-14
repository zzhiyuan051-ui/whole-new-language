#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成提权安装用的批处理，**按 GBK 保存**。

为什么必须管编码：cmd.exe 读 .bat 用的是系统 OEM 代码页（中文 Windows 上是 GBK）。
用 UTF-8 存 .bat，里面的中文会变成乱码，批处理在解析阶段就可能崩掉 ——
表现是「双击了但什么都没发生」。这个坑踩过。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

BAT = r"""@echo off
setlocal
set HERE=%~dp0
set RESULT=%HERE%install_result.txt
set CLSID={7F3A9C10-2B4D-4E6A-9C11-8A2F0D553E71}
set DLL=%HERE%out\huiwen_ime.dll

echo 洄文输入法 · 提权安装 > "%RESULT%"
echo 时间: %DATE% %TIME% >> "%RESULT%"

net session >nul 2>&1
if errorlevel 1 (
    echo 结果: 失败 - 本进程不是管理员 >> "%RESULT%"
    echo 失败：没有管理员权限。
    echo 详情见 %RESULT%
    pause
    exit /b 1
)
echo 权限: 管理员 >> "%RESULT%"

if not exist "%DLL%" (
    echo 结果: 失败 - 找不到 %DLL% >> "%RESULT%"
    echo 失败：找不到 %DLL%
    echo 详情见 %RESULT%
    pause
    exit /b 1
)
echo DLL: %DLL% >> "%RESULT%"

rem 先反注册，清掉上一次的残留（失败不算错）
regsvr32 /s /u "%DLL%" >nul 2>&1

regsvr32 /s "%DLL%"
if errorlevel 1 (
    echo 结果: 失败 - regsvr32 返回 %errorlevel% >> "%RESULT%"
    echo 失败：regsvr32 返回 %errorlevel%
    echo 详情见 %RESULT%
    pause
    exit /b 1
)
echo regsvr32: 成功 >> "%RESULT%"

set OK=1
reg query "HKLM\SOFTWARE\Classes\CLSID\%CLSID%\InprocServer32" >nul 2>&1
if errorlevel 1 ( echo COM类HKLM: 缺 >> "%RESULT%" & set OK=0 ) else ( echo COM类HKLM: 有 >> "%RESULT%" )

reg query "HKLM\SOFTWARE\Microsoft\CTF\TIP\%CLSID%" >nul 2>&1
if errorlevel 1 ( echo TSF档案HKLM: 缺 >> "%RESULT%" & set OK=0 ) else ( echo TSF档案HKLM: 有 >> "%RESULT%" )

reg query "HKLM\SOFTWARE\Microsoft\CTF\TIP\%CLSID%\LanguageProfile\0x00000804" >nul 2>&1
if errorlevel 1 ( echo 语言档案0804: 缺 >> "%RESULT%" & set OK=0 ) else ( echo 语言档案0804: 有 >> "%RESULT%" )

if "%OK%"=="1" (
    echo 结果: 成功 >> "%RESULT%"
    echo.
    echo ============================================================
    echo  安装成功。
    echo  按 Win+Space（或点任务栏语言栏）选到「洄文输入法」，
    echo  在记事本里敲 za，按 1 上屏。程序内开关：Ctrl+Shift+H
    echo ============================================================
) else (
    echo 结果: 失败 - regsvr32 报成功但注册项不全 >> "%RESULT%"
    echo.
    echo 失败：注册项不全，语言栏不会出现洄文输入法。
    echo 详情见 %RESULT%
)

echo.
echo 结果文件：%RESULT%
echo 按任意键关闭本窗口。
pause >nul
exit /b 0
"""

docs = {
    "install_elevated.bat": BAT,
}

for name, text in docs.items():
    p = HERE / name
    # 关键：GBK 存盘，而不是 UTF-8
    p.write_bytes(text.replace("\n", "\r\n").encode("gbk", errors="replace"))
    print(f"已生成 {name}（GBK，{p.stat().st_size} 字节）")
