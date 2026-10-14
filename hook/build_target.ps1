# 编译测试靶子
#
#     powershell -NoProfile -ExecutionPolicy Bypass -File huiwen/hook/build_target.ps1

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$out  = Join-Path $here 'out'
New-Item -ItemType Directory -Force -Path $out | Out-Null

$cands = @(
    'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat',
    'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat'
)
$vcvars = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $vcvars) { throw '找不到 vcvars64.bat' }

$src = Join-Path $here 'huiwen_target.cpp'
$exe = Join-Path $out  'huiwen_target.exe'
$bat = Join-Path $out  '_build_target.bat'

$lines = @(
    '@echo off',
    "call `"$vcvars`" >nul",
    'if errorlevel 1 exit /b 1',
    "cd /d `"$here`"",
    "cl /nologo /EHsc /O2 /W3 /MT /utf-8 /DUNICODE /D_UNICODE `"$src`" /Fe:`"$exe`" /link /SUBSYSTEM:CONSOLE user32.lib gdi32.lib",
    'exit /b %errorlevel%'
)
Set-Content -Path $bat -Value $lines -Encoding ASCII

Write-Host '正在编译测试靶子…'
& cmd.exe /c $bat
if ($LASTEXITCODE -ne 0) { throw "编译失败，退出码 $LASTEXITCODE" }
$f = Get-Item $exe
Write-Host ("编译成功 → {0}（{1} KB）" -f $f.Name, [int]($f.Length / 1KB))
