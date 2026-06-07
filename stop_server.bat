@echo off
chcp 65001 > nul
echo [停止] AX損保 APIサーバーを停止します...
taskkill /IM python.exe /F > nul 2>&1
taskkill /IM python3.exe /F > nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /PID %%a /F > nul 2>&1
)
echo 停止完了。
timeout /t 2 /nobreak > nul
