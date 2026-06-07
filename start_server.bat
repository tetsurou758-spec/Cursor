@echo off
chcp 65001 > nul
echo ============================================
echo  AX損保 APIサーバー 起動スクリプト
echo ============================================

echo.
echo [1/3] 既存のPythonプロセスを終了中...
taskkill /IM python.exe /F > nul 2>&1
taskkill /IM python3.exe /F > nul 2>&1
timeout /t 2 /nobreak > nul

REM ポート8000が解放されたか確認
netstat -ano | findstr ":8000" | findstr "LISTENING" > nul 2>&1
if %errorlevel% == 0 (
    echo [警告] ポート8000がまだ使用中です。強制解放します...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
        taskkill /PID %%a /F > nul 2>&1
    )
    timeout /t 2 /nobreak > nul
)

echo [2/3] ポート8000 クリア確認...
netstat -ano | findstr ":8000" | findstr "LISTENING" > nul 2>&1
if %errorlevel% == 0 (
    echo [エラー] ポート8000を解放できませんでした。手動で確認してください。
    pause
    exit /b 1
) else (
    echo         OK - ポート8000は空きです
)

echo [3/3] APIサーバーを起動します...
echo.
cd /d "%~dp0"
python -m uvicorn backend.main:app --reload --port 8000

pause
