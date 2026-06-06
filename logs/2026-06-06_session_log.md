# 作業ログ 2026-06-06（セッション）

**プロジェクト**: AX損害保険株式会社 代理店Webシステム（デモ環境）  
**担当**: Pistols チーム  
**記録日時**: 2026-06-06

---

## 実施作業一覧

### 1. セキュリティ対応（dotenv・.gitignore）

| 項目 | 内容 |
|------|------|
| `.gitignore` 更新 | `backend/.env` / `*.env` を追跡対象外に設定 |
| `requirements.txt` 作成 | 全依存パッケージを明示（anthropic含む） |
| `backend/.env` 作成 | ANTHROPIC_API_KEY の格納先を整備 |
| `backend/main.py` 修正 | `load_dotenv(dotenv_path=backend/.env)` を先頭に追加 |

---

### 2. contract_details テーブル カラム刷新

**マイグレーション**: `db/migrate_contract_details_v2.sql`

| 種目 | 削除カラム | 追加カラム |
|------|-----------|-----------|
| 自賠責 | `jibai_coverage_limit` | `jibai_injury_limit` / `jibai_death_limit` |
| 賠償責任 | `liab_coverage_limit` / `liab_deductible` / `liab_jidan_flg` / `liab_coverage_scope` | `liab_bodily_limit_per_person` / `liab_bodily_limit_per_accident` / `liab_property_limit` |
| 所得補償 | （新規） | `income_monthly_benefit` / `income_deductible_days` / `income_benefit_period` / `income_coverage_type` / `income_occupation_type` / `income_monthly_income` |

**影響ファイル**:
- `backend/main.py` — `get_contract_detail` のSELECT句を新カラム名に修正
- `frontend/contract_detail.html` — `renderJibai` / `renderLiability` / `renderIncome` 関数を新カラム対応に更新

---

### 3. リスクマップPDF機能

**新規ファイル**:
- `reports/generate_riskmap.py` — ReportLab Wedge を使った7種目ピザチャートPDF生成
- `backend/routers/riskmap_router.py` — 顧客単位・契約単位リスクマップAPI

**エンドポイント**:
| メソッド | URL | 機能 |
|---------|-----|------|
| POST | `/api/riskmap/customer/{customer_id}` | 顧客リスクマップPDF生成・保存 |
| GET  | `/api/riskmap/customer/{customer_id}` | 顧客リスクマップPDF取得 |
| POST | `/api/riskmap/contract/{contract_no}` | 契約リスクマップPDF生成・保存 |
| GET  | `/api/riskmap/contract/{contract_no}` | 契約リスクマップPDF取得 |

**対応画面**: `frontend/customer.html` / `frontend/contract_detail.html` にリスクマップボタン追加

---

### 4. 遅延帳票（XLSX）管理機能

**新規ファイル**:
- `batch/report_batch.py` — `受付中` の帳票リクエストを処理してXLSX生成
- `frontend/report_list.html` — 帳票管理画面（ステータスバッジ・30秒自動更新・ダウンロード・削除）

**エンドポイント**:
| メソッド | URL | 機能 |
|---------|-----|------|
| POST | `/api/reports/request` | 帳票リクエスト登録 |
| GET  | `/api/reports/list` | 帳票一覧取得 |
| GET  | `/api/reports/{no}/download` | 帳票ダウンロード（RFC5987対応） |
| DELETE | `/api/reports/{no}` | 帳票削除 |

**帳票出力ボタン追加画面**: `customer.html` / `maturity.html` / `sales.html`

---

### 5. TODOリスト機能

**新規ファイル**: `frontend/todo_list.html`

**エンドポイント**:
| メソッド | URL | 機能 |
|---------|-----|------|
| GET  | `/api/todos` | TODO一覧取得（ステータス・担当者絞込） |
| POST | `/api/todos` | TODO新規作成 |
| PUT  | `/api/todos/{id}` | TODO更新 |
| DELETE | `/api/todos/{id}` | TODO削除（管理者のみ） |
| GET  | `/api/todos/staff-list` | 担当者プルダウン用一覧 |

**担当者コード**: `agency_code + " " + staff_code` の複合キー（"A001 S005"形式）で一意管理  
→ 同じstaff_codeが別代理店で存在する場合の名前混同を解消

---

### 6. ダッシュボード 10ボタン・2行レイアウト化

**行1（5個）**: 顧客管理 / 満期管理 / 契約照会 / 保険金支払状況 / 帳票管理  
**行2（5個）**: 成績管理 / TODOリスト / 手数料管理（準備中） / 意向確認（準備中） / AIレコメンド

**準備中モーダル**: 🚧アイコン付きモーダル（alert不使用・モーダル外クリックで閉じる）  
**代理店のみ表示**: 成績管理・AIレコメンド（社員ログイン時は非表示）

---

### 7. AIレコメンド機能（Claude API連携）

**新規ファイル**:
- `backend/routers/ai_router.py` — Claude API連携・推奨生成・DB保存
- `frontend/ai_recommend.html` — AIレコメンド管理画面
- `db/migrate_ai_recommendations.sql` — ai_recommendations テーブル定義
- `docs/ai_recommend_api.md` — API仕様書

**エンドポイント**:
| メソッド | URL | 機能 |
|---------|-----|------|
| POST | `/api/ai/recommend/{customer_id}` | 個別顧客AI推奨生成 |
| GET  | `/api/ai/recommend/{customer_id}` | 最新推奨取得 |
| GET  | `/api/ai/recommend/summary/{agency_code}` | 代理店推奨サマリー集計 |
| POST | `/api/ai/recommend/bulk/{agency_code}` | 全顧客一括推奨生成 |

**使用モデル**: `claude-opus-4-5`  
**セキュリティ**: APIキーは `backend/.env` のみ管理・フロントエンドから直接参照不可

---

### 8. 共通ヘッダーデザイン刷新

**修正内容** (`frontend/js/theme.css`):
- 中央タイトル固定 (`.header-center-title`)
- 戻るボタンと非クリックバッジの視覚的区別 (`.btn-back` / `.page-badge`)
- 全画面で統一されたヘッダー構成

---

## バグ修正一覧

| # | 画面 | 症状 | 原因 | 修正 |
|---|------|------|------|------|
| 1 | 契約詳細 | 500エラー | 旧カラム名（`jibai_coverage_limit`等）をSELECTしていた | 新カラム名に修正 |
| 2 | リスクマップ | 500エラー | `customer_name`カラム不存在（実際は`last_name`+`first_name`） | カラム名修正 |
| 3 | 帳票ダウンロード | UnicodeEncodeError | 日本語ファイル名をContent-Dispositionに直接記述 | RFC5987形式に変更 |
| 4 | 帳票リクエスト | 422エラー | `search_params`の型がstrだがfrontendがdictで送信 | `Optional[dict]`に修正 |
| 5 | TODO担当者 | 別人の名前が表示 | `staff_code`のみ（S005等）でルックアップ、代理店をまたいで衝突 | 複合キー（"A001 S005"）形式に統一 |
| 6 | AIレコメンド | 500エラー | `load_dotenv()`パス未指定でAPIキー未読み込み | `backend/.env`を明示指定 |
| 7 | AIレコメンド | 500エラー | モデル名`claude-sonnet-4-20250514`が無効 | `claude-opus-4-5`に修正 |
| 8 | サーバー | 旧コードで動作 | 複数のPythonプロセスが起動中 | 全プロセス終了・再起動で解消 |

---

## コミット履歴（本セッション分）

```
5742be0 fix: AIレコメンドAPIキー読み込み修正・TODO担当者複合キー化
f67c3db fix: ダッシュボードボタン10個レイアウトを仕様通りに修正
e2fac33 feat: AIレコメンド機能・リスクマップ・帳票管理・TODOリスト等を追加実装
```

---

## 新規ファイル一覧

| ファイル | 種別 | 説明 |
|---------|------|------|
| `backend/routers/riskmap_router.py` | API | リスクマップPDF生成API |
| `backend/routers/ai_router.py` | API | AIレコメンドAPI（Claude連携） |
| `reports/generate_riskmap.py` | 帳票 | ピザチャートPDF生成 |
| `frontend/report_list.html` | 画面 | 帳票管理画面 |
| `frontend/todo_list.html` | 画面 | TODOリスト画面 |
| `frontend/ai_recommend.html` | 画面 | AIレコメンド管理画面 |
| `db/migrate_contract_details_v2.sql` | DB | contract_detailsカラム変更 |
| `db/migrate_ai_recommendations.sql` | DB | ai_recommendationsテーブル新設 |
| `docs/ai_recommend_api.md` | 設計書 | AIレコメンドAPI仕様書 |
| `requirements.txt` | 設定 | Python依存パッケージ一覧 |
| `backend/.env` | 設定 | 環境変数（git管理外） |

---

## 残課題・今後の作業

| 優先度 | 項目 | 備考 |
|--------|------|------|
| 高 | AIレコメンド動作確認 | モデル名修正・APIキー修正後に再テスト要 |
| 高 | Agent Eによる自動テスト | `test/010_UT-AIレコメンドテスト/` 作成 |
| 中 | 手数料管理画面 | 現在は「準備中」モーダルのみ |
| 中 | 意向確認画面 | 現在は「準備中」モーダルのみ |
| 低 | db/users.sqlite LFS化 | GitHubの50MB警告対応（83MB） |

---

*Generated by Claude Sonnet 4.6 on 2026-06-06*
