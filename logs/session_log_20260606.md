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
# 作業ログ 2026-06-06

**プロジェクト：** AX損害保険株式会社 代理店Webシステム（デモ環境）
**担当：** Pistols チーム（Claude Sonnet 4.6）
**作業時間：** 終日

---

## 本日の作業サマリー

### 1. 更改おすすめプラン通知書PDF機能の実装（未実装→完成）

**概要：** 満期管理画面の帳票リンクから更改通知書PDFをiframeモーダルで表示する機能を新規実装。

**実装内容：**
- `renewal_recommend_plans` テーブル（BLOB方式）をDBに追加
- ReportLab + Font Awesome SVG（svglib）でPDF生成スクリプト作成
  - 保険種目アイコン（SVG埋め込み）
  - 現在のご契約・3プラン対比表（プランA/B/C）
  - UPマーク（↑）付きの値上がり項目ハイライト
- `GET /api/renewal-notice/{contract_no}` APIエンドポイント追加
- 満期管理画面に iframeモーダル追加（BearerトークンをfetchでBlobURL化）
- シードスクリプトで1,465件のPDFをDB投入

**技術的な解決事項：**
- Font Awesome TTF（woff2→TTF変換）→ CFFアウトライン問題でReportLab非対応
- `svglib` でSVGファイルを直接埋め込む方式に変更
- 日本語パス（ドキュメント）でsvglibのURLエンコードが失敗 → `BytesIO` 経由で回避
- SVGアイコンが `icons/solid/` サブフォルダを想定していたが実際は `icons/` 直下だったため修正

**対応ファイル：**
- `db/migrate_renewal_recommend.sql`
- `db/seed_renewal_recommend.py`
- `reports/generate_renewal_notice.py`
- `backend/routers/renewal_router.py`
- `backend/main.py`
- `frontend/maturity.html`

---

### 2. バグ修正：更改通知書 failed to fetch / 担当者名 undefined

- **failed to fetch：** PDF fetchURLが相対パス `/api/...` になっていた → `API_BASE` ベースの絶対パスに修正
- **担当者名 undefined：** APIは `name` フィールドで返すが `s.staff_name` で参照 → `s.name` に修正

---

### 3. ダッシュボードアイコンを Font Awesome Free に統一

**背景：** 既存のインラインSVGアイコンの著作権懸念を解消するため、Font Awesome 6 Free（CC BY 4.0）に統一。

| 箇所 | 旧アイコン | 新アイコン |
|---|---|---|
| 顧客管理 | 手書き人物SVG | `fa-users` |
| 満期管理 | 手書き時計SVG | `fa-calendar-check` |
| 契約照会 | 手書きファイルSVG | `fa-file-contract` |
| 保険金支払 | ¥マーク | `fa-hand-holding-dollar` |
| 成績管理 | 折れ線グラフSVG | `fa-chart-line` |
| お知らせ | ベルSVG | `fa-bell` |
| TODO | チェックSVG | `fa-list-check` |
| コンタクト | 吹き出しSVG | `fa-comments` |

---

### 4. 成績管理画面（sales.html）の大規模バグ修正・UI改善

#### バグ修正（合計5件）

| # | バグ内容 | 原因 | 修正内容 |
|---|---|---|---|
| 1 | 月別保険料が全件0円 | `renewed_premium IS NOT NULL` でほぼ全件除外 | `renewal_status='更改済'` に変更 |
| 2 | 集計マトリクスが全件— | `actualData.actuals` キー名ミス | `actualData.data` に修正 |
| 3 | 月キーのミスマッチ | `"05"` ゼロ埋め vs API返却の `"5"` | `String(m)` に変更 |
| 4 | 代理店合計で— | `staff_code` 未送信 → API 422エラー | `__all__` 時は `'ALL'` を送信 |
| 5 | 担当者選択時に担当者名 undefined | `s.staff_name` 参照ミス | `s.name` に修正 |

#### UI改善

- 種目ラベルから英字括弧削除（`自動車(AUTO)` → `自動車`）
- 種目列をセンタリング
- セル内表示改善：「当年度」削除、目標/実績 左詰め・金額右詰め、バーチャート位置変更
- 目標を Bold 化
- データなし月もセル高さ統一（常に4行構造）
- フォントサイズ 0.78rem → 0.70rem（大きな金額の行折り返し防止）

---

### 5. 2026年度成績目標値シードデータ投入

- **対象：** A001・A003・B001・B002・C003 全代理店
- **目標値：** 2026年度契約の `annual_premium × 1.0`（更改前保険料そのまま）
- **粒度：** 担当者別 + 代理店合計（ALL）
- **件数：** 138件
- **スクリプト：** `db/seed_sales_targets_2026.py`

---

### 6. 目標設定画面（sales_target.html）の大規模バグ修正・UI改善

#### バグ修正（合計4件）

| # | バグ内容 | 原因 | 修正内容 |
|---|---|---|---|
| 1 | 前年度実績が全て— | `actualData.actuals` / `targetData.targets` キー名ミス | `.data` に修正 |
| 2 | 月キーのミスマッチ | `mStr = padStart(2,'0')` | `String(m)` に変更 |
| 3 | 代理店合計で取得失敗 | `staff_code` 未送信 | `'ALL'` を送信 |
| 4 | 次年度目標に入力できない | 目標設定率 onblur で `prev=0 × rate = 0` が目標を上書き | `prev<=0` の場合は return で保護 |

#### UI改善

- 種目ラベルから英字括弧削除、センタリング
- 見出し・入力値の文字色を黒に統一（プレースホルダーと区別）
- 前年度実績を左詰め・金額右詰め
- 次年度目標を通貨フォーマット（`¥xxx,xxx`）表示
  - focus時：数値のみ表示で入力しやすく
  - blur時：`¥xxx,xxx` 再フォーマット
- gridレイアウトで全行の列を完全統一
- 前年度実績を disabled input 化（右端揃え・背景グレー・色#333・Bold）
- 目標設定率 onblur 後フォーカスを次年度目標inputへ自動移動
- 円未満切捨て実装
- フォントサイズ 0.78rem → 0.70rem

---

## 本日のコミット一覧

| コミットID | 内容 |
|---|---|
| e3e50d9 | feat: 更改おすすめプラン通知書PDF機能を実装 |
| a90b936 | fix: 更改通知書failed to fetch・担当者名undefined を修正 |
| e65f933 | fix: SVGアイコンが表示されない問題を修正 |
| a7b8895 | feat: ダッシュボードアイコンをFont Awesome Freeに統一 |
| 2155277 | fix: 成績管理の月別保険料が0円になる問題を修正 |
| 5532c29 | fix: 成績集計をrenewed_premiumのみに戻す |
| 8bac7fe | fix: 成績管理の集計マトリクスが全て—になる問題を修正 |
| 74edbd3 | fix: staff_code未送信問題を修正 |
| 4296fa5 | fix: 種目ラベルから英字括弧を削除・進捗バー改善 |
| a298a63 | fix: 種目列をセンタリング |
| 54dc3d4 | feat: 2026年度成績目標値シードを追加 |
| 0a2b87d | fix: 当年度目標が0円になる問題を修正・倍率1.0に変更 |
| d256130 | fix: 成績管理セル表示を改善 |
| 28a97ad | fix: 目標設定画面の3問題を修正 |
| 6cf7739 | fix/feat: 目標設定画面の入力UIを再設計 |
| 39d5b1b | fix: 見出し・入力値の文字色を黒に変更 |
| 2f33c7e | fix: 前年度実績のフォント色・サイズ・左詰めを統一 |
| b87373a | feat: 目標設定画面の表示書式を改善 |
| aea024d | fix: gridレイアウトでズレを修正 |
| 01270d4 | fix: 目標設定・参照画面のレイアウト改善 |
| 10e18fb | fix: 参照画面の目標をBOLD化・見出し左詰め・金額右詰め |
| 75fa258 | fix: フォント縮小・前年度実績をinput化 |

---

## 残課題

- なし（本日予定作業はすべて完了）

## CLAUDE.mdの未実装リスト更新状況

- 帳票出力（ReportLab）→ **完成**（更改おすすめプラン通知書PDF）
