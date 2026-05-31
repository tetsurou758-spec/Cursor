# 作業ログ 2026-05-31（第6セッション）― 名寄せバッチ改修・顧客連携・全契約名寄せ対応

---

## 実施概要

名寄せバッチの精度向上（contractor_first_name_raw対応・最新連絡先優先）、  
contracts テーブルの customer_id 廃止と linked_customer_id への一本化、  
満期管理→顧客詳細画面の遷移機能実装、  
全1,530件の契約に contractor 情報を付与して名寄せ完全対応を実施した。

---

## 作業1：名寄せバッチ改修（contractor_first_name_raw対応）

### db/init_db.py
- `contracts` テーブルに `contractor_first_name_raw TEXT`（名・マスク前）カラムを追加
- 顧客契約（CUST-*）の INSERT に `first_name_raw`（本名）を登録

### batch/name_matching_batch.py
| 変更点 | 内容 |
|---|---|
| `contractor_first_name_raw` 取得 | SELECT に追加、WHERE 条件にも追加 |
| match_key 生成 | マスク済み名 → **本名（first_name_raw）ベース**に修正 |
| `find_same_customer` | first_name（マスク）→ **first_name_raw** で照合するよう修正 |
| 連絡先情報の取得ルール | 同一顧客の複数契約のうち **expiry_date が最新の契約の連絡先を優先** するよう変更 |
| グループ化処理 | `group_contracts_by_customer()` 関数を追加。顧客キーでグループ化後、expiry_date 降順ソートで primary 契約を決定 |
| 営業情報 | email / family_structure / hobbies / assets_info はバッチでは NULL 維持（UI入力項目） |

**修正前との比較（全件解消）：**

| 項目 | 修正前 | 修正後 |
|---|---|---|
| first_name_raw | マスク済みと同値 | 本名 |
| match_key | マスク済み名ベース | **本名ベース（init と一致）** |
| 複数契約の連絡先 | 処理順最初の契約 | **expiry_date 最新の契約を優先** |

---

## 作業2：contracts.customer_id 廃止・linked_customer_id 一本化

### 問題
`contracts.customer_id`（TEXT型、例："CUST-A001-001"）と  
`customers.customer_id`（INTEGER型）が型・値とも不一致で JOIN 不能だった。

### 対応

**db/init_db.py**
- `CREATE TABLE contracts` から `customer_id TEXT` カラムを削除
- MATURITY_CONTRACTS の INSERT から `customer_id` を除外

**backend/main.py**
- `GET /api/maturity` の SELECT を `c.customer_id` → `c.linked_customer_id` に修正
- `GET /api/customers/{customer_id}` に `policy_summary` / `held_agencies` / `multi_agency` / `contract_count` を付与（顧客一覧と同形式のレスポンスに統一）

### 修正後の確認
- `linked_customer_id` あり: **65件**（正常紐付き）
- JOIN で顧客名取得: ✅ 正常動作

---

## 作業3：満期管理 → 顧客詳細画面 遷移機能

### frontend/maturity.html
- 顧客名セルを `linked_customer_id` がある場合のみクリック可能なリンクに変更
- 遷移先: `customer.html?customer_id={linked_customer_id}&expand=true`
- `.customer-link` スタイル追加（`pointer` / ホバー時アンダーライン・色変化）

### frontend/customer.html
URLパラメータ `customer_id` / `expand` を受け取る処理を追加：

| 条件 | 動作 |
|---|---|
| `?customer_id=N&expand=true` あり | 該当顧客1件のみ表示・契約詳細を自動展開・ヘッダーが「← 満期管理に戻る」に切り替わり・検索フォームを非表示 |
| パラメータなし | 通常の一覧表示（変更なし） |

---

## 作業4：UI修正

### frontend/js/theme.css
- agency テーマの顧客管理画面「加入状況 ○」を `var(--accent)`（ゴールド、見づらい） → `#1a1a2e`（黒）に変更
- staff テーマはピンク（`var(--primary)`）を維持

---

## 作業5：バグ修正（満期管理 500 エラー）

### 原因
`uvicorn --reload` が `backend/main.py` の変更を検知せず、  
旧プロセス（`c.customer_id` を参照した古いコード）が3プロセス並走し  
DB から `customer_id` 列が削除済みなのに旧コードが応答していた。

### 対応
- `taskkill` で旧プロセス（PID: 23804 / 16612 / 1404）を全て強制終了
- 新プロセスで uvicorn を再起動
- `GET /api/maturity` が 200 OK で 572件を返すことを確認

---

## 作業6：満期管理サンプル16件に contractor 情報を追加

MATURITY_CONTRACTS 各契約に以下を設定：

| フィールド | 設定内容 |
|---|---|
| `contractor_last_name` | 顧客名の姓 |
| `contractor_first_name` | 名のマスク済み（○〇） |
| `contractor_first_name_raw` | 名の本名 |
| `contractor_gender` | M / F |
| `contractor_birth_date` | 適切な年代の生年月日（1958〜1990年） |
| `contractor_address` | 代理店所在地に対応した住所（東京/大阪/名古屋） |
| `contractor_tel` | 連絡先電話番号 |

**名寄せバッチ実行結果：** 16件新規登録・16件全紐付け・エラー0件

---

## 作業7：全契約（バルク1,449件）への contractor 情報自動生成

### 背景
バルク契約（ダッシュボード用）には `contractor_*` が全件 NULL のため  
名寄せ対象外（`linked_customer_id = NULL`）だった。

### 実装

**db/init_db.py に追加した関数・データ：**

| 追加内容 | 説明 |
|---|---|
| `FIRST_NAME_GENDER` | 名前→性別マッピング（FIRST_NAMES 全20種類に対応） |
| `_ADDR_CONFIG` | 代理店グループ→住所プレフィックス・区名リスト（東京8区/大阪8区/名古屋8区） |
| `make_contractor_info(customer_name, agency_code)` | 氏名の MD5 ハッシュから contractor_* を**確定的に生成**する関数 |

**同一氏名 = 同一 contractor 情報** の保証により、同じ名前の複数契約が名寄せで正しく1人の顧客に統合される。

**生成ルール：**

| 項目 | 生成方法 |
|---|---|
| 性別 | `FIRST_NAME_GENDER` マッピングで正確に判定 |
| 生年月日 | 1945〜1995年、月・日は hash の上位ビットで算出 |
| 電話番号 | 070/080/090 から hash で選択 + hash で4桁×2 |
| 住所 | 代理店グループの都市 + hash で区名・番地を決定 |

### 名寄せバッチ実行結果

| 項目 | 結果 |
|---|---|
| 処理対象契約 | **1,465件**（バルク1,449 + M-*16） |
| 顧客候補グループ | **870グループ** |
| 新規顧客登録 | **870名** |
| 契約紐付け | **1,465件全件** |
| エラー | 0件 |

**最終DB統計：**

| グループ | 顧客数 | 契約数 | 紐付き |
|---|---|---|---|
| A | 339名 | 599件 | 599件 |
| B | 304名 | 511件 | 511件 |
| C | 253名 | 420件 | 420件 |
| **合計** | **896名** | **1,530件** | **1,530件（0件未紐付け）** |

---

## 本日のコミット履歴

```
c821966 Add: バルク契約1,449件に contractor情報を自動生成・全契約を名寄せ対象化
33dc399 Add: 満期管理サンプル契約16件に契約者情報を追加・名寄せ対象化
58da89b Fix: staffテーマのheld-colorをピンクに戻す（agencyのみ黒に変更）
8deb5c1 Fix: 顧客管理画面の加入状況○をゴールドから黒に変更
74cabe6 Fix: contracts.customer_id廃止・linked_customer_idに一本化＋満期管理→顧客詳細リンク追加
093f942 Fix: 名寄せバッチ改修・contractor_first_name_rawカラム追加
2c0a0d1 Add: 名寄せバッチ（batch/name_matching_batch.py）
f32306b Fix: admin.htmlセクション見出しをvar(--detail-label-color)に変更（agency=黒/staff=ピンク）
f0d97ac Fix: dashboard.htmlセクション見出しをvar(--detail-label-color)に変更（agency=黒/staff=ピンク）
6f94166 Fix: maturity.html詳細ラベルをvar(--detail-label-color)に変更（agency=黒/staff=ピンク）
cbfc7ba Fix: 顧客詳細ラベル色をテーマ別に分離
8d9eef9 Fix: 全画面共通の見出し・ラベル色をvar(--label-color)に統一
a94caab Fix: 顧客管理画面の保険加入状況カラム整列と見出し色修正
7960fb7 Fix: 顧客管理・満期管理画面の見出しラベル色とフォント改善
dbcad69 Add: 顧客管理システム（group_codeキー設計・名寄せ機能・顧客一覧画面）
```

---

## 更新後フォルダ構成（差分）

```
Cursor/
├── db/
│   ├── init_db.py       ★更新：customer_id削除・contractor_first_name_raw追加・
│   │                            make_contractor_info()追加・バルク契約contractor情報付与
│   └── users.sqlite     ★更新：全1,530件linked_customer_id紐付け済み・顧客896名
│
├── batch/
│   └── name_matching_batch.py  ★更新：first_name_rawベースmatch_key・
│                                       最新expiry連絡先優先・グループ化処理
│
├── backend/
│   └── main.py          ★更新：/api/maturityにlinked_customer_id追加・
│                                /api/customers/{id}にpolicy_summary付与
│
├── frontend/
│   ├── maturity.html    ★更新：顧客名リンク化（linked_customer_idある場合のみ）
│   ├── customer.html    ★更新：URLパラメータcustomer_id/expand対応・
│   │                            満期管理からの単一顧客表示モード追加
│   └── js/
│       └── theme.css    ★更新：agencyテーマのheld-color ゴールド→黒
│
└── logs/
    └── 2026-05-31_作業ログ.md  ★本ファイル
```

---

## 残課題・次回以降の作業候補

| 優先 | 内容 |
|---|---|
| 高 | 契約照会システム（frontend/contract.html + GET /api/contracts） |
| 中 | 保険金支払状況（frontend/claim.html + GET /api/claims） |
| 中 | バッチ処理追加（renewal_notice.py など） |
| 低 | PDF帳票出力（reports/） |
| 低 | SECRET_KEY 環境変数化・本番パスワード変更 |

---

---

# 追記：第7セッション（2026-06-01）― 契約照会機能全実装・各種機能拡張・バグ修正

チーム名：**Pistols**（マルチエージェント部隊）

---

## 作業1：テスト仕様書・証跡Excel作成（006・007）

### test/006_UT-名寄せバッチ処理テスト/
- `名寄せテスト仕様書.xlsx`：UT-NAMEYOSE-001〜003（同一G統合・異G別顧客・名寄せキー正当性）
- `名寄せテスト証跡.xlsx`：Sheet1 customers全件ダンプ・Sheet2 contracts_linked・Sheet3〜5 画面証跡

### test/007_UT-顧客管理保険加入状況テスト/
- `加入状況テスト仕様書.xlsx`：UT-CUSTOMER-001〜003（加入状況表示・DB突合・画面遷移）
- `加入状況テスト証跡.xlsx`：Sheet1 羽生グループA契約突合・Sheet2〜4 画面証跡

### Playwrightで全6枚のスクリーンショットを自動取得・Excelに自動挿入
| スクリーンショット | 確認内容 |
|---|---|
| NAMEYOSE-001 | 羽生○弦 グループA 1件（A001+A002バッジ） |
| NAMEYOSE-002 | 羽生○弦 全グループ 2件（社員S001ログイン・ピンクテーマ） |
| NAMEYOSE-003 | 大谷○平 グループA 1件（A001+A003バッジ） |
| CUSTOMER-001 | 保険加入状況 車○火○自賠○・傷－賠責－サイバー－所得－ |
| CUSTOMER-002 | 保有契約3件展開（自動車・自賠責・火災） |
| CUSTOMER-003 | 満期管理→顧客管理遷移（← 満期管理に戻るリンク確認） |

---

## 作業2：検索・ナビ機能拡張

### backend/main.py
- `GET /api/customers` に `not_insured_types`（未加入種目AND絞込）・`tel`・`contract_no` パラメータ追加
- `GET /api/maturity` の日付空=全件対応・`customer_name`・`contract_no` パラメータ追加
- `GET /api/dashboard` に `total_contracts`（月別件数）を追加

### frontend/customer.html
- 保有種目ドロップダウン → **未加入種目チェックボックス7種（AND条件）** に変更
- 検索バーに「電話番号」「証券番号」入力欄を追加（部分一致）
- URLパラメータ `search_name`/`search_tel`/`search_contract` 対応

### frontend/maturity.html
- 顧客氏名テキスト検索欄を追加
- クリアボタン押下後に全件再検索するバグ修正
- 初期表示を全件（日付フィルタなし）に変更
- URLパラメータ `customer_name`/`tel`/`contract_no`/`renewal_status`/`expiry_month` 対応

### frontend/dashboard.html
- ダイレクト検索エリア追加
  - 入力値自動判定：数字始まり→電話番号、全角始まり→名前、その他→証券番号
  - 「顧客へGo!」→ customer.html、「契約照会へGo!」→ direct-search API経由
- ドーナツグラフクリックで満期管理（未対応絞込・該当月）へ遷移
- グラフ月ラベルに総契約件数バッジを表示

---

## 作業3：契約照会機能の全実装（エージェントA/B/C並列）

### Agent A（設計）: DB新設
- `db/migrate_contract_details.sql`：contract_details テーブルDDL
- `db/seed_contract_details.py`：全1,530件のダミーデータINSERT（7種目×2〜3パターンローテーション）

### Agent B（バックエンド）: API実装（backend/main.py に追加）
| エンドポイント | 機能 |
|---|---|
| `GET /api/contracts/search` | 証券番号/顧客名/電話番号/種目・ページング・ソート |
| `GET /api/contracts/direct-search` | 入力値自動判定→0件/1件/複数で振り分け |
| `GET /api/contracts/{contract_no}` | 詳細＋contract_details LEFT OUTER JOIN |

※FastAPIのパス解決順に注意し `search`・`direct-search` を `{contract_no}` より前に定義

### Agent C（フロントエンド）: 画面新規作成
- `frontend/contract.html`：契約照会一覧（検索・ページネーション・種目バッジ）
- `frontend/contract_detail.html`：契約詳細（基本情報・契約者情報・6種目別詳細カード）

### 関連対応
- `maturity.html` 証券番号を `contract_detail.html` へのリンクに変更（`&from=maturity`）
- `dashboard.html`「契約照会へGo!」を `/api/contracts/direct-search` と連携
  - 1件→詳細画面・複数→一覧画面・0件→インラインメッセージ
- `contract.html` ナビボタンを `href="#"` → `href="contract.html"` に修正
- `specs/contract_api.md` 作成（API設計メモ・画面遷移図）

---

## 作業4：各種バグ修正

### 証券番号表記統一
- 全画面で「契約番号」を「**証券番号**」に統一
- `contract_detail.html` の `contract_no`（証券番号）と `policy_number`（保険会社証券番号）を区別

### M系契約データ修正（`db/update_m_contract_details.py`）
- **原因1**：seed スクリプトのパターンローテーション（id%3）で `auto_vehicle_amount=null` 等が発生
- **原因2**：contract_detail.html の `yen()` をTEXT型フィールドに誤適用 → `¥NaN` 表示バグ
- **修正**：
  - M系16件に固有のリアルな値を直接設定（ヴォクシー/アルファード/ランクル等）
  - `liab_coverage_limit`・`cyber_*`・`jibai_coverage_limit`・`inj_surgery_benefit` を `val(esc())` に修正

### esc() TypeError バグ（contract_detail.html）
- **原因**：`auto_nfl_grade`（INTEGER）を `esc()` に渡すと `(14 || '').replace(...)` → `14.replace()` → TypeError
- **修正**：`esc()` の先頭に `String(s)` 変換を追加（null チェック後）
- **影響範囲**：自動車保険の詳細表示が全件「サーバーエラー」になっていた

```javascript
// 旧（バグ）
function esc(s) { return (s || '').replace(...) }
// 新（修正後）
function esc(s) { if (s == null) return ''; return String(s).replace(...) }
```

---

## 作業5：機能改善

### 契約詳細画面の戻るボタン（遷移元対応）
- URL パラメータ `?from=xxx` で遷移元を明示
- `FROM_MAP` テーブルで `from値 → {href, ラベル}` をマッピング（新画面追加は1行のみ）

| from 値 | 戻り先 |
|---|---|
| `maturity` | ← 満期管理に戻る |
| `customer` | ← 顧客管理に戻る |
| `contract` | ← 契約照会一覧に戻る |
| `dashboard` | ← ダッシュボードに戻る |
| 未指定 | ← 満期管理に戻る（デフォルト） |

### ダッシュボード インフォグラフィックス 3列化
- 「先月・今月・翌月」の3ドーナツ表示に拡張
- 先月：スレートグレー（#94a3b8）、今月：primary、翌月：accent
- レスポンシブ：≤1100px → 2列、≤700px → 1列

### ダッシュボード 母数・完了率バグ修正
- **原因1**：`total_contracts` に月フィルタが欠落 → 全期間の全契約件数になっていた
- **原因2**：`total = done + pend` で `落ち` や status未設定件数が母数から除外されていた
- **修正**：`month_total`（該当月の満期件数）を統一母数として使用

| 集計（A001・6月現在） | 先月5月 | 今月6月 | 翌月7月 |
|---|---|---|---|
| 母数 | 247件 | 325件 | 0件 |
| 更改済 | 29件 | 126件 | 0件 |
| 完了率 | 11.7% | 38.8% | 0% |

---

## 第7セッション コミット履歴

```
5698f20 Fix: ダッシュボードの母数・完了率を該当月の満期件数ベースに修正
6add2fd Add: ダッシュボードのインフォグラフィックスを「先月・今月・翌月」3列に拡張
b1d5f7b Add: 契約詳細画面の戻るボタンを遷移元画面に動的対応
a9e0a3f Fix: contract_detail.htmlのesc()TypeErrorでサーバーエラーが出る不具合を修正
2fd5319 Fix: 契約詳細画面の¥NaNバグ修正・M系契約データを本物らしい値に更新
63b7cf1 Fix: 証券番号リンク追加・「契約番号」を「証券番号」に統一
8389e10 Fix: ダッシュボードの契約照会ボタンをcontract.htmlへ遷移するよう修正
d66a4d0 Move: contract_api.mdをdocs/からspecs/へ移動
103bcb6 Add: 契約照会機能の全実装（一覧・詳細・API・ダイレクト検索連携）
567fccc Add: docsフォルダ作成・CLAUDE.md完全更新
4ace6fc Fix: 顧客検索に電話番号・証券番号欄追加、ダイレクト検索判定ロジック改善
4242c97 Add: 検索・ナビ機能拡張（顧客/満期/ダッシュボード）
442625d Add: 006/007テスト証跡にPlaywrightスクリーンショットを挿入
e972c89 Add: 006/007テスト仕様書・証跡Excel作成（名寄せ・加入状況）
```

---

## 第7セッション終了時点の完成画面一覧

| 画面 | ファイル | 状態 |
|---|---|---|
| ログイン（代理店） | login.html | ✅ 完成 |
| ログイン（社員） | staff_login.html | ✅ 完成 |
| ダッシュボード | dashboard.html | ✅ 完成（先月/今月/翌月・ダイレクト検索） |
| 満期管理 | maturity.html | ✅ 完成（証券番号リンク・全件検索） |
| 顧客管理 | customer.html | ✅ 完成（未加入絞込・証券番号リンク） |
| 契約照会一覧 | contract.html | ✅ 新規完成 |
| 契約詳細 | contract_detail.html | ✅ 新規完成（6種目別表示） |
| 権限管理 | admin.html | ✅ 完成 |

## 残課題

| 優先 | 内容 |
|---|---|
| 中 | 保険金支払状況画面（frontend/claim.html） |
| 中 | コンタクト履歴入力機能 |
| 低 | 帳票出力（ReportLab） |
| 低 | SECRET_KEY 環境変数化・本番パスワード変更 |
| 低 | test/008_UT-契約照会テスト/ 作成 |
