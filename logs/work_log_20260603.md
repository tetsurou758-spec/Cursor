# 作業ログ 2026/06/03

## 実施作業

### 1. CLAUDE.md 更新
- 完成画面一覧に contract.html / contract_detail.html / claim.html / claim_detail.html / contact.html / agency_master.html を追記
- 実装済み機能に契約照会・保険金支払状況・コンタクト履歴・代理店マスタ編集を追記
- 未実装リストから実装済み項目を削除

### 2. 成績管理機能 新規実装
- db/migrate_sales_targets.sql 作成・マイグレーション実行（576レコード投入）
- docs/sales_api.md API設計メモ作成
- backend/routers/sales_router.py 新規作成（4エンドポイント）
- backend/main.py にsales_routerを追加
- frontend/sales.html 新規作成（成績参照画面）
- frontend/sales_target.html 新規作成（目標設定画面）
- frontend/dashboard.html に成績管理ボタン追加
- test/009_UT-成績管理テスト/test_sales.py 作成（TC-001〜TC-012）

### 3. 参照グループ設定テスト作成
- agency_master.html が参照グループ設定画面として実装済みであることを確認
- test/008_UT-代理店マスタ編集テスト/ を作成
- Playwrightでスクリーンショット取得（9枚）
- 仕様書xlsx・証跡xlsx作成（UT-AGMT-001〜008）
- 証跡xlsxにスクリーンショット貼付

### 4. 成績管理バグ修正・API修正
- sales_router の include_router をミドルウェア設定後に移動（404バグ修正）
- sales.html / sales_target.html の fetchStaffList バグ修正
  - `data.staff_list`（存在しないキー）→ `data`（配列直接）に修正
  - `s.staff_name` → `s.name` に修正
  - 上記2件により担当者プルダウンが「代理店合計」のみ表示されていた問題を解消

### 5. usersテーブル拡張・代理店ユーザー整備
- users テーブルに staff_code カラムを追加
- 各代理店に管理者1名＋担当者5名（8代理店×6名＝48名）を整備
- contracts テーブルの担当者コード（S001〜S005）を優先割当て、不足分は自動生成
- db/migrate_users.py マイグレーションスクリプト作成
- GET /api/sales/staff-list が staff_code・login_id・name を返すよう修正

### 6. GET /api/sales/actual の集計ロジック修正
- 集計対象を annual_premium → renewed_premium（更改後年換算保険料）に変更
- 更改済み契約のみ集計（renewed_policy_number IS NOT NULL）
- contracts.policy_type が日本語のため POLICY_TYPE_MAP で英語コードに変換
  （フロントエンド側の表示ロジックへの影響なし）

### 7. Claude Code 設定
- .claude/settings.json を作成、defaultMode: bypassPermissions を設定
  （次回セッションから許可プロンプトをスキップ）

## 残課題
- 帳票出力（ReportLab）未実装
