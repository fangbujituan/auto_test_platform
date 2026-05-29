@echo off
chcp 65001 >nul

:menu
echo.
echo ========== kiro-gateway Manager ==========
echo   1. Start
echo   2. Stop
echo   3. Restart
echo   4. View Logs
echo   5. Remove Container
echo   6. Health Check
echo   0. Exit
echo ==========================================
echo.

set /p choice="Enter your choice: "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto restart
if "%choice%"=="4" goto logs
if "%choice%"=="5" goto remove
if "%choice%"=="6" goto health
if "%choice%"=="0" goto end

echo Invalid choice!
goto menu

:start
echo Starting kiro-gateway...
docker start kiro-gateway 2>nul
if %errorlevel% neq 0 (
    echo Container not found. Creating new one...
    docker run -d ^
      -p 127.0.0.1:9000:9000 ^
      -e PROXY_API_KEY="sk-12823d840d204ecdb671ede0a358cllms" ^
      -e KIRO_CREDS_FILE="/home/kiro/.aws/sso/cache/kiro-auth-token.json" ^
      -e SERVER_HOST=0.0.0.0 ^
      -e SERVER_PORT=9000 ^
      -v C:\Users\dechao.yan\.aws\sso\cache:/home/kiro/.aws/sso/cache:ro ^
      --name kiro-gateway ^
      ghcr.io/jwadow/kiro-gateway:latest
)
goto menu

:stop
echo Stopping kiro-gateway...
docker stop kiro-gateway
goto menu

:restart
echo Restarting kiro-gateway...
docker restart kiro-gateway
goto menu

:logs
echo Showing logs (Ctrl+C to exit)...
docker logs -f kiro-gateway
goto menu

:remove
echo Removing kiro-gateway container...
docker stop kiro-gateway 2>nul
docker rm kiro-gateway
goto menu

:health
echo Checking health...
curl -s http://localhost:9000/health
echo.
goto menu

:end
echo Bye!
