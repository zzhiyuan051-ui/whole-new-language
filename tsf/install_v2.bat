@echo off
setlocal
set HERE=%~dp0
set RESULT=%HERE%install_result.txt
set DLL=%HERE%out\huiwen_ime2.dll

echo 洄文输入法 · 安装带日志的版本 > "%RESULT%"
echo 时间: %DATE% %TIME% >> "%RESULT%"

net session >nul 2>&1
if errorlevel 1 (
    echo 结果: 失败 - 不是管理员 >> "%RESULT%"
    pause
    exit /b 1
)
echo 权限: 管理员 >> "%RESULT%"

if not exist "%DLL%" (
    echo 结果: 失败 - 找不到 %DLL% >> "%RESULT%"
    pause
    exit /b 1
)

rem 先把旧的注册撤掉，避免两个档案打架
regsvr32 /s /u "%HERE%out\huiwen_ime.dll" >nul 2>&1
echo 旧版反注册: 已尝试 >> "%RESULT%"

regsvr32 /s "%DLL%"
if errorlevel 1 (
    echo 结果: 失败 - regsvr32 返回 %errorlevel% >> "%RESULT%"
    pause
    exit /b 1
)
echo regsvr32: 成功 >> "%RESULT%"

reg query "HKLM\SOFTWARE\Microsoft\CTF\TIP\{7F3A9C10-2B4D-4E6A-9C11-8A2F0D553E71}" >nul 2>&1
if errorlevel 1 (
    echo 结果: 失败 - HKLM 里没有档案 >> "%RESULT%"
) else (
    echo TSF档案HKLM: 有 >> "%RESULT%"
    echo 结果: 成功 >> "%RESULT%"
)

echo.
echo 完成，结果见 %RESULT%
exit /b 0
