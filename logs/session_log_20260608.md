# 作業セッションログ 2026-06-08

## 対象システム
AX損害保険株式会社 代理店Webシステム（Pistolsプロジェクト）

---

## 実施作業一覧

### 1. DB現状スナップショット生成スクリプト作成
**コミット:** `48f15c7`

**背景:**
「現時点のDBに格納されている値でDBの初期値が登録されるpyは作ってあるか？」という質問から着手。
`init_db.py` は `random.seed(42)` で固定ダミーデータをゼロから生成するスクリプトであり、
現在のDB状態を再現する仕組みは存在しなかったため新規作成。

**`db/export_seed.py`（新規）**
- `users.sqlite`（21テーブル）/ `insurance.db`（1テーブル）の全データを読み取り
- `db/generated_seed.py` として再現スクリプトを自動生成（2157KB）
- BLOBが大量な `renewal_recommend_plans` / `riskmap_pdfs` / `report_requests` は除外
- パスワードはbcryptハッシュのまま含む（平文は保存されていないため安全）
- 実行すると `password123` 等の既存パスワードでそのままログイン可能な状態を再現

**`db/generated_seed.py`（自動生成）**
- `export_seed.py` 実行によって生成されたDB再現スクリプト本体
- 全22テーブル・全レコードを `executemany` でバルクINSERT

---

### 2. 別PC向けインストーラー作成
**コミット:** `48f15c7`

**`install.bat`（新規）**

| ステップ | 内容 |
|---------|------|
| STEP 1 | Python インストール確認（未インストール時は案内メッセージ） |
| STEP 2 | git pull（既存リポジトリ検出時）/ git clone（新規端末）自動判定 |
| STEP 3 | `pip install -r requirements.txt` でパッケージ一括インストール |
| STEP 4 | `generated_seed.py` 優先 → なければ `init_db.py` でDB初期化 |
| STEP 5 | `backend/.env` 未存在時に注意メッセージ（OPENAI_API_KEY設定案内） |
| 完了後 | 「デモ起動しますか？(y/n)」で `start_demo.bat` を自動呼び出し |

---

### 3. デモ起動ランチャー作成
**コミット:** `48f15c7`

**`start_demo.bat`（新規）**

| ステップ | 内容 |
|---------|------|
| 1/3 | 既存Pythonプロセス終了・ポート8000解放（最大待機あり） |
| 2/3 | uvicornをバックグラウンドで起動（最大15秒・2秒間隔でポート確認） |
| 3/3 | `frontend/login.html` と `frontend/staff_login.html` をデフォルトブラウザで自動オープン |

- サーバーログは `logs/server.log` に出力
- 起動後にデモアカウント情報（代理店4件・社員3件）を表示

**`stop_server.bat`（新規）**
- uvicornプロセスをKill・ポート8000を強制解放

---

## 作成ファイル一覧

| ファイル | 種別 | 概要 |
|---------|------|------|
| `db/export_seed.py` | 新規 | 現在のDB状態をgenerated_seed.pyに書き出す |
| `db/generated_seed.py` | 自動生成 | DB再現シードスクリプト（22テーブル・2157KB） |
| `install.bat` | 新規 | 別PC向けセットアップ一括インストーラー |
| `start_demo.bat` | 新規 | サーバー起動 + ブラウザ2画面自動オープン |
| `stop_server.bat` | 新規 | サーバー停止 |

---

## 除外テーブル（BLOBが大量のため）

| テーブル | 理由 |
|---------|------|
| `renewal_recommend_plans` | 更改おすすめプランPDF BLOBが1465件 |
| `riskmap_pdfs` | リスクマップPDF BLOB |
| `report_requests` | 帳票ファイルBLOB |
| `sqlite_sequence` | SQLite内部管理テーブル |

---

## 別PC での利用手順

```
1. install.bat を実行
   → git clone + pip install + DB初期化 を自動実行

2. （任意）backend/.env に OPENAI_API_KEY を設定

3. start_demo.bat を実行
   → サーバー起動 + ブラウザ2画面（代理店/社員）自動オープン

4. ログイン
   代理店: A001 / admin / password123
   社員:   S001 / staff123
```

---

*出力日時: 2026-06-08*
*担当AI: Claude Sonnet 4.6*
