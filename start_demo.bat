@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ============================================================
echo   AX損害保険 代理店Webシステム  デモ起動
echo   Pistols Project  -  Demo Launcher
echo ============================================================
echo.

REM ---- 作業ディレクトリをこのBATファイルの場所に固定 ----
cd /d "%~dp0"

REM ============================================================
REM  [1/3] 既存プロセス解放
REM ============================================================
echo [1/3] ポート8000 クリア中...
taskkill /IM python.exe /F > nul 2>&1
taskkill /IM python3.exe /F > nul 2>&1
timeout /t 2 /nobreak > nul

REM まだ残っていたら強制解放
netstat -ano | findstr ":8000" | findstr "LISTENING" > nul 2>&1
if %errorlevel% == 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
        taskkill /PID %%a /F > nul 2>&1
    )
    timeout /t 2 /nobreak > nul
)

netstat -ano | findstr ":8000" | findstr "LISTENING" > nul 2>&1
if %errorlevel% == 0 (
    echo  [エラー] ポート8000を解放できませんでした。手動で確認してください。
    pause
    exit /b 1
)
echo          OK - ポート8000 空き確認

REM ============================================================
REM  [2/3] APIサーバー起動（バックグラウンド）
REM ============================================================
echo.
echo [2/3] APIサーバー起動中...
start "AX損保APIサーバー" /min cmd /c "python -m uvicorn backend.main:app --reload --port 8000 2>&1 | tee logs\server.log"

REM サーバーが立ち上がるまで待機（最大15秒）
echo          起動待機中...
set RETRY=0
:WAIT_LOOP
timeout /t 2 /nobreak > nul
set /a RETRY+=1
netstat -ano | findstr ":8000" | findstr "LISTENING" > nul 2>&1
if %errorlevel% == 0 goto SERVER_UP
if %RETRY% geq 7 (
    echo  [警告] サーバーの起動確認がタイムアウトしました。
    echo         ブラウザを開きますが、少し待ってからリロードしてください。
    goto OPEN_BROWSER
)
goto WAIT_LOOP

:SERVER_UP
echo          OK - APIサーバー起動確認 (http://localhost:8000)

REM ============================================================
REM  [3/3] ブラウザ自動オープン
REM ============================================================
:OPEN_BROWSER
echo.
echo [3/3] ブラウザを起動します...

REM login.html（代理店ログイン）
set LOGIN_URL=http://localhost:8000/../frontend/login.html
REM ※ FastAPIはfrontend/をStaticFilesでマウントしていないため、file://で開く
set LOGIN_PATH=%~dp0frontend\login.html
set STAFF_PATH=%~dp0frontend\staff_login.html

REM デフォルトブラウザで開く
start "" "%LOGIN_PATH%"
timeout /t 1 /nobreak > nul
start "" "%STAFF_PATH%"

echo          代理店ログイン  : %LOGIN_PATH%
echo          社員ログイン    : %STAFF_PATH%
echo.
echo ============================================================
echo   サーバー稼働中  http://localhost:8000
echo   APIドキュメント http://localhost:8000/docs
echo ============================================================
echo.
echo  ログイン情報 (デモ):
echo    代理店ログイン: A001 / admin / password123  （管理者）
echo                   A001 / staff1 / pass001       （一般担当）
echo                   B002 / agent1 / pass456       （一般担当）
echo                   C003 / user1 / pass789        （閲覧専用）
echo    社員ログイン:   S001 / staff123               （システム管理者）
echo                   S002 / staff456               （代理店担当者）
echo                   S003 / staff789               （参照専用）
echo.
echo  サーバーを停止するには、「AX損保APIサーバー」ウィンドウを閉じるか
echo  stop_server.bat を実行してください。
echo.
pause
