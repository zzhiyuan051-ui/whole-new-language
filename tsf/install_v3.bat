@echo off
setlocal
set HERE=%~dp0
set RESULT=%HERE%install_result.txt
set DLL=%HERE%out\huiwen_ime3.dll

echo 洄文输入法 · 安装 v3（带 DllMain 日志 + 图标） > "%RESULT%"
echo 时间: %DATE% %TIME% >> "%RESULT%"

net session >nul 2>&1
if errorlevel 1 (
    echo 结果: 失败 - 不是管理员 >> "%RESULT%"
    exit /b 1
)

if not exist "%DLL%" (
    echo 结果: 失败 - 找不到 %DLL% >> "%RESULT%"
    exit /b 1
)

rem 把之前两个版本都撤掉，避免互相打架
regsvr32 /s /u "%HERE%out\huiwen_ime2.dll" >nul 2>&1
regsvr32 /s /u "%HERE%out\huiwen_ime.dll"  >nul 2>&1

regsvr32 /s "%DLL%"
if errorlevel 1 (
    echo 结果: 失败 - regsvr32 返回 %errorlevel% >> "%RESULT%"
    exit /b 1
)
echo regsvr32: 成功 >> "%RESULT%"

rem 核对 InprocServer32 指向的是不是 v3，以及 IconFile 不再是空串
reg query "HKLM\SOFTWARE\Classes\CLSID\{7F3A9C10-2B4D-4E6A-9C11-8A2F0D553E71}\InprocServer32" /ve >> "%RESULT%" 2>&1
reg query "HKLM\SOFTWARE\Microsoft\CTF\TIP\{7F3A9C10-2B4D-4E6A-9C11-8A2F0D553E71}\LanguageProfile\0x00000804\{7F3A9C11-2B4D-4E6A-9C11-8A2F0D553E72}" >> "%RESULT%" 2>&1
echo 结果: 成功 >> "%RESULT%"
exit /b 0
