# CLAUDE.md

## プロジェクト概要
全国損害保険代理店向けWebシステム（デモ環境）
AX損害保険株式会社 代理店Webシステム

## システム構成
- Web/AP: FastAPI (Python) + HTML/CSS/JS
- DB: SQLite
- 帳票: ReportLab（予定）
- バッチ: Pythonスクリプト
- ポート: 8000

## 起動方法
```
python -m uvicorn backend.main:app --reload --port 8000
```

## 完成画面一覧
- login.html：代理店・社員共通ログイン
- staff_login.html：社員専用ログイン（ピンクテーマ）
- dashboard.html：ダッシュボード（代理店・社員共通）
- maturity.html：満期管理（代理店・社員共通）
- customer.html：顧客管理（代理店・社員共通）
- admin.html：権限管理（代理店・社員共通）

## テーマ切替
session.jsのapplyTheme()でdata-theme属性を切替
- 代理店：紺色テーマ
- 社員：ホットピンクテーマ（#FF1493）

## DBテーブル一覧
- users：認証・ユーザー管理
- agencies：代理店マスタ（buka_code含む）
- staff_users：社員ユーザーマスタ
- contracts：契約データ（linked_customer_id含む）
- customers：顧客マスタ（参照Gコード単位）
- roles：ロールマスタ
- features：機能マスタ
- role_permissions：ロール×機能
- staff_roles：社員ロールマスタ
- accidents：事故情報
- maturity_notices：満期案内
- login_attempts：ログイン試行管理
- session_tokens：セッション管理
- password_reset：パスワード初期化
- login_history：ログイン履歴
- policy_types：保険種目マスタ（7種目）

## 保険種目
- AUTO：自動車
- FIRE：火災
- INJURY：傷害
- JIBAI：自賠責
- LIABILITY：賠償責任
- CYBER：サイバーリスク
- INCOME：所得補償

## 代理店ダミーデータ
- A001/admin/password123（管理者）
- A001/staff1/pass001（一般担当）
- B002/agent1/pass456（一般担当）
- C003/user1/pass789（閲覧専用）

## 社員ダミーデータ
- S001/staff123（システム管理者・X001部課）
- S002/staff456（代理店担当者・X001部課）
- S003/staff789（参照専用・Y001部課）

## 参照グループ構成
- グループA：A001・A002・A003・B002・C003（X001部課管轄）
- グループB：B001・B002（Y001部課管轄）
- グループC：C001・C003（Z001部課管轄）

## 顧客名寄せルール
- 必須3項目：性別・生年月日・名（first_name_raw）一致
- AND（電話番号一致 OR 住所一致）
- 参照Gコード単位で独立管理
- バッチ：batch/name_matching_batch.py

## 実装済み機能
- JWT認証・ブルートフォース対策（5回ロック）
- セッションタイムアウト（30分）
- RBACロール管理（管理者/一般担当/閲覧専用）
- 社員/代理店デュアルテーマ
- sessionStorageによるタブ別セッション管理
- 満期管理（アコーディオン・ソート・絞込）
- 顧客管理（名寄せ・7種目加入状況・未加入絞込）
- 満期管理→顧客管理リンク遷移
- ダッシュボードダイレクト検索（名前/TEL/証券番号自動判定）
- ドーナツグラフクリック遷移（未対応絞込）
- 名寄せバッチ処理（夜間想定）
- Playwright自動テスト・Excel証跡自動生成

## テスト成果物
- test/001_UT-ログインテスト/
- test/002_UT-ダッシュボード表示テスト/
- test/003_UT-画面遷移テスト/
- test/004_UT-権限管理テスト/
- test/005_UT-社員認証・セッション競合回避テスト/
- test/006_UT-名寄せバッチ処理テスト/
- test/007_UT-顧客管理保険加入状況テスト/

## 未実装・作業中
- 契約照会画面
- 社員専用：参照グループ設定画面
- 代理店専用：担当者別成績管理画面
- 帳票出力（ReportLab）
- コンタクト履歴入力機能
- 保険金支払状況画面

## 開発ルール
- コメントは日本語
- 変更したら必ずgit push
- テストはtest/NNN_UT-XXXフォルダに格納
- 仕様書とテスト証跡は別Bookで管理
- sessionStorageでセッション管理（localStorageは使わない）

## ディレクトリ構成
```
/frontend   # 画面（HTML/CSS/JS）
/backend    # API（FastAPI）
/batch      # バッチ処理
/reports    # 帳票（ReportLab予定）
/db         # データベース（SQLite）
/test       # テスト仕様書・証跡・Playwrightスクリプト
/docs       # 設計ドキュメント・プレゼン資料
/logs       # バッチ実行ログ
```

## テスト格納ルール
- テストフォルダ命名：連番_テスト種別-対象機能名
  例）001_UT-ログインテスト
- テスト仕様書：テストフォルダ/XXXテスト仕様書.xlsx
- テスト証跡：テストフォルダ/XXXテスト証跡.xlsx
- スクリーンショット：テストフォルダ/screenshots/
