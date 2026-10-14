@echo off
rem Restart ctfmon so it re-reads the input method list.
rem Written in ASCII on purpose: cmd.exe reads .bat using the OEM codepage,
rem so a UTF-8 .bat with Chinese in it gets mangled and can fail to parse.
setlocal
set RESULT=%~dp0restart_ctfmon_result.txt

echo restart ctfmon > "%RESULT%"
echo time: %DATE% %TIME% >> "%RESULT%"

net session >nul 2>&1
if errorlevel 1 (
    echo result: FAILED - not admin >> "%RESULT%"
    exit /b 1
)
echo admin: yes >> "%RESULT%"

echo --- before --- >> "%RESULT%"
tasklist /fi "imagename eq ctfmon.exe" >> "%RESULT%" 2>&1

taskkill /f /im ctfmon.exe >> "%RESULT%" 2>&1
echo taskkill exit=%errorlevel% >> "%RESULT%"

timeout /t 2 /nobreak >nul

start "" "%SystemRoot%\System32\ctfmon.exe"
timeout /t 3 /nobreak >nul

echo --- after --- >> "%RESULT%"
tasklist /fi "imagename eq ctfmon.exe" >> "%RESULT%" 2>&1

echo result: DONE >> "%RESULT%"
exit /b 0
