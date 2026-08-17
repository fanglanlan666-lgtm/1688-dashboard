@echo off
chcp 65001 >nul
title 1688数字营销工作台 · 本地服务

REM 若看板已在运行，直接打开浏览器即可，避免重复拉起
curl -s -m 3 -o nul http://localhost:8787/ >nul 2>&1
if %errorlevel%==0 (
  echo 看板已在运行（http://localhost:8787/），直接打开浏览器。
  start "" http://localhost:8787/
  timeout /t 2 >nul
  exit /b
)

echo.
echo  ======================================================
echo   1688 数字营销工作台 · 本地联动服务（守护模式）
echo   浏览器将自动打开 http://localhost:8787
echo   守护进程会自愈：server 崩溃自动重启，端口空闲即接管
echo   关闭此窗口不会停止后台守护（日志见 server_guard.log）
echo  ======================================================
echo.
start "" "C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2/node.exe" "C:/Users/Administrator/WorkBuddy/1688业务/dashboard_guard.js"
timeout /t 3 >nul
start "" http://localhost:8787/
echo 服务已启动，稍候数秒后访问 http://localhost:8787/
timeout /t 3 >nul
