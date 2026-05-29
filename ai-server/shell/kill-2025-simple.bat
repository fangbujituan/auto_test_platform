@echo off
echo ========================================
echo Kill ALL processes on port 2025
echo ========================================
echo.

setlocal enabledelayedexpansion
set KILLED=0

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":2025"') do (
    set PID=%%a
    if not "!PID!"=="0" (
        taskkill /F /PID !PID! > nul 2>&1
        if !errorlevel!==0 (
            echo [OK] Killed PID !PID!
            set /a KILLED+=1
        )
    )
)

echo.
if %KILLED%==0 (
    echo [INFO] Port 2025 is not in use
) else (
    echo [DONE] Killed %KILLED% process(es)
)

echo ========================================
pause