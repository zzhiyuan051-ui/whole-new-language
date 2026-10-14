# 洄文输入法 · TSF 文本服务编译脚本
#
# 用法（在仓库根目录）：
#     pwsh huiwen/tsf/build.ps1
# 产物：huiwen/tsf/out/huiwen_ime.dll
#
# 为什么要用 vcvars64：cl.exe 依赖一堆环境变量（INCLUDE/LIB/PATH），
# 单独调 cl.exe 会因为找不到标准头文件而失败。

param(
    # 产物文件名。默认 huiwen_ime.dll。
    # 需要换名是因为：DLL 一旦被 TSF 加载进各个应用进程，文件就被锁住、
    # 覆盖不了。改个名字就能接着编译并用新文件注册（实测被 14 个进程锁着）。
    [string]$Name = 'huiwen_ime.dll'
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $here)
$out  = Join-Path $here 'out'
New-Item -ItemType Directory -Force -Path $out | Out-Null

# 找 vcvars64.bat（优先 VS 2022，其次 VS 18）
$cands = @(
    'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat',
    'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat',
    'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
)
$vcvars = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $vcvars) { throw '找不到 vcvars64.bat，请先安装 Visual Studio Build Tools（含 C++ 工作负载）' }
Write-Host "vcvars: $vcvars"

$src = Join-Path $here 'huiwen_ime.cpp'
$def = Join-Path $here 'huiwen_ime.def'
$dll = Join-Path $out  $Name

# 把编译命令写进 .bat 再执行：直接拼 -Command 会被引号和 % 吃掉
$bat = Join-Path $out ('_build_' + [IO.Path]::GetFileNameWithoutExtension($Name) + '.bat')
$lines = @(
    '@echo off',
    "call `"$vcvars`" >nul",
    'if errorlevel 1 exit /b 1',
    "cd /d `"$here`"",
    "cl /nologo /LD /EHsc /O2 /W3 /MT /utf-8 /DUNICODE /D_UNICODE `"$src`" /Fe:`"$dll`" /link /DEF:`"$def`" ole32.lib oleaut32.lib advapi32.lib user32.lib gdi32.lib",
    'exit /b %errorlevel%'
)
Set-Content -Path $bat -Value $lines -Encoding ASCII

Write-Host '正在编译…'
& cmd.exe /c $bat
$code = $LASTEXITCODE
if ($code -ne 0) { throw "编译失败，退出码 $code" }
if (-not (Test-Path $dll)) { throw "没有产出 $dll" }

$f = Get-Item $dll
Write-Host ("编译成功 → {0}（{1} KB）" -f $f.FullName, [int]($f.Length / 1KB))

# 顺手看一下导出的函数齐不齐
$dumpbin = Get-ChildItem 'C:\Program Files (x86)\Microsoft Visual Studio' -Recurse `
    -Filter 'dumpbin.exe' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -like '*Hostx64\x64*' } | Select-Object -First 1
if ($dumpbin) {
    Write-Host '导出表:'
    & $dumpbin.FullName /EXPORTS $dll 2>$null |
        Select-String -Pattern 'Dll(GetClassObject|CanUnloadNow|RegisterServer|UnregisterServer)' |
        ForEach-Object { '   ' + $_.Line.Trim() }
}
