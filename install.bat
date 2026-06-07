@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ============================================================
echo   AX損害保険 代理店Webシステム  インストーラー
echo   Pistols Project  -  Demo Environment Setup
echo ============================================================
echo.

REM ---- 作業ディレクトリをこのBATファイルの場所に固定 ----
cd /d "%~dp0"

REM ============================================================
REM  [STEP 1] Python インストール確認
REM ============================================================
echo [STEP 1/5] Python 確認中...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [エラー] Python が見つかりません。
    echo  https://www.python.org/downloads/ からPython 3.10以上をインストールして
    echo  「Add Python to PATH」にチェックを入れてから再実行してください。
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo          %%v
echo          OK

REM ============================================================
REM  [STEP 2] Git インストール確認 & クローン/プル
REM ============================================================
echo.
echo [STEP 2/5] リポジトリ取得中...

REM すでにgit管理下（インストーラー自体がリポジトリ内）かどうか確認
git rev-parse --git-dir > nul 2>&1
if %errorlevel% == 0 (
    echo          既存リポジトリを検出 - git pull で最新化します...
    git pull origin main
    if %errorlevel% neq 0 (
        echo          [警告] git pull に失敗しました（ローカル変更がある場合は手動で解決してください）
    ) else (
        echo          OK - 最新コードに更新しました
    )
) else (
    REM 新規クローン
    git --version > nul 2>&1
    if %errorlevel% neq 0 (
        echo  [エラー] Git が見つかりません。
        echo  https://git-scm.com/download/win からGitをインストールしてください。
        pause
        exit /b 1
    )
    set REPO_URL=https://github.com/tetsurou758-spec/Cursor.git
    echo          クローン先: %~dp0
    echo          リポジトリ: !REPO_URL!
    echo.
    git clone !REPO_URL! .
    if %errorlevel% neq 0 (
        echo  [エラー] git clone に失敗しました。URLとネットワーク接続を確認してください。
        pause
        exit /b 1
    )
    echo          OK - クローン完了
)

REM ============================================================
REM  [STEP 3] Pythonパッケージ インストール
REM ============================================================
echo.
echo [STEP 3/5] Pythonパッケージをインストール中...
echo          （初回は数分かかる場合があります）
echo.
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo  [エラー] pip install に失敗しました。
    echo  手動で実行: pip install -r requirements.txt
    pause
    exit /b 1
)
echo          OK - パッケージインストール完了

REM ============================================================
REM  [STEP 4] DB初期化
REM ============================================================
echo.
echo [STEP 4/5] データベース初期化中...

REM generated_seed.py があれば使う（export_seed.py で生成済みの現状データ）
REM なければ init_db.py でフレッシュなダミーデータを生成
if exist "db\generated_seed.py" (
    echo          generated_seed.py を使用 - エクスポート済みデータで復元します
    python db/generated_seed.py
) else (
    echo          init_db.py を使用 - 初期ダミーデータを生成します
    python db/init_db.py
)

if %errorlevel% neq 0 (
    echo  [エラー] DB初期化に失敗しました。
    pause
    exit /b 1
)
echo          OK - データベース準備完了

REM ============================================================
REM  [STEP 5] .env ファイル確認
REM ============================================================
echo.
echo [STEP 5/5] 環境設定確認...

if not exist "backend\.env" (
    echo.
    echo  [注意] backend\.env が見つかりません。
    echo  AIレコメンド機能を使用する場合は以下の内容で作成してください:
    echo.
    echo    OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    echo.
    echo  backend\.env を作成しない場合でも、AI機能以外は正常に動作します。
    echo.
    REM .env なしでも起動は続行
) else (
    echo          OK - backend\.env 確認済み
)

REM ============================================================
REM  完了
REM ============================================================
echo.
echo ============================================================
echo   インストール完了！
echo ============================================================
echo.
echo  次のステップ:
echo    start_demo.bat  - サーバー起動 + ブラウザ自動オープン
echo.
echo  ログイン情報 (デモ):
echo    代理店: A001 / admin / password123
echo    社員:   S001 / staff123
echo.

set /p STARTDEMO="このままデモを起動しますか？ (y/n): "
if /i "!STARTDEMO!"=="y" (
    call start_demo.bat
) else (
    echo 手動で start_demo.bat を実行してください。
    pause
)
