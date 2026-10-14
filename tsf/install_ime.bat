@echo off
rem ============================================================================
rem  洄文输入法（系统级）· 安装
rem
rem  为什么要提权：注册 Windows 输入法要写 HKLM\SOFTWARE\Microsoft\CTF\TIP，
rem  这是 Windows 的安全边界，普通权限拿不到（实测错误码 5 拒绝访问）。
rem  所以这个脚本会自己请求管理员权限 —— 你只需要在弹出的 UAC 窗口点「是」。
rem
rem  用法：右键「以管理员身份运行」，或直接双击（会自动弹 UAC）。
rem ============================================================================
setlocal

rem 若当前不是管理员，就用 runas 重新拉起自己（会弹 UAC）。
rem 提权后的窗口必须留着：直接 exit 会把那扇窗口关掉，用户只看见一闪。
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 需要管理员权限来注册输入法，正在请求提权...
    echo 请在弹出的窗口里点「是」。点「否」或关掉，语言栏里就不会出现洄文输入法。
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
    echo.
    echo 若刚才点了「是」，请看提权后的那扇窗口里写的是成功还是失败。
    echo 按任意键关闭本窗口。
    pause
    exit /b
)

set HERE=%~dp0
echo ============================================================
echo  洄文输入法（TSF 系统级）· 安装（已提权）
echo ============================================================
echo.

rem 1) 编译（若还没有 dll）
if not exist "%HERE%out\huiwen_ime.dll" (
    echo [1/3] 编译 DLL ...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%build.ps1"
    if errorlevel 1 ( echo 编译失败 & pause & exit /b 1 )
) else (
    echo [1/3] DLL 已存在，跳过编译
)

rem 2) 注册。不用 Python：提权后的窗口环境不一定找得到 Python，
rem 而且语言栏认的是 HKLM 里的 TSF 档案，必须用 regsvr32 调 DllRegisterServer。
echo [2/3] 注册到 TSF ...
regsvr32 /s "%HERE%out\huiwen_ime.dll"
if errorlevel 1 (
    echo regsvr32 失败。语言栏不会出现「洄文输入法」。
    echo 请把本窗口里的文字留着，不要关掉。
    pause
    exit /b 1
)
echo regsvr32 返回成功。

rem 3) 验证。语言栏只认 HKLM 里的档案；HKCU 有了也不算装上。
echo.
echo [3/3] 验证语言栏认的那条注册表 ...
reg query "HKLM\SOFTWARE\Microsoft\CTF\TIP\{7F3A9C10-2B4D-4E6A-9C11-8A2F0D553E71}" >nul 2>&1
if errorlevel 1 (
    echo 失败：HKLM 里没有洄文输入法档案。
    echo 语言栏不会出现它。请把本窗口文字留着。
    pause
    exit /b 1
)
echo HKLM 档案已写入。
if exist "%HERE%out\hwimetool.exe" "%HERE%out\hwimetool.exe" verify

echo.
echo ============================================================
echo  安装结束。请按 Win+Space（或点任务栏语言栏）选到「洄文输入法」，
echo  然后在记事本里敲 za，按 1 上屏，应出现洄文字形。
echo  程序内开关：Ctrl+Shift+H
echo ============================================================
pause
