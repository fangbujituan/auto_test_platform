@echo off
chcp 65001 >nul
echo Starting kiro-gateway...

docker run -d ^
  -p 127.0.0.1:9000:9000 ^
  -e PROXY_API_KEY="sk-12823d840d204ecdb671ede0a358cllms" ^
  -e KIRO_CREDS_FILE="/home/kiro/.aws/sso/cache/kiro-auth-token.json" ^
  -e SERVER_HOST=0.0.0.0 ^
  -e SERVER_PORT=9000 ^
  -v C:\Users\dechao.yan\.aws\sso\cache:/home/kiro/.aws/sso/cache:ro ^
  --name kiro-gateway ^
  ghcr.io/jwadow/kiro-gateway:latest

if %errorlevel% equ 0 (
    echo.
    echo kiro-gateway started successfully!
    echo Health check: http://localhost:9000/health
    echo.
    echo Useful commands:
    echo   View logs:  docker logs -f kiro-gateway
    echo   Stop:       docker stop kiro-gateway
    echo   Restart:    docker restart kiro-gateway
) else (
    echo.
    echo Failed to start kiro-gateway.
    echo If container already exists, run: docker rm kiro-gateway
)

pause
