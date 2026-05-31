# バッチ処理

## name_matching_batch.py — 名寄せバッチ

### 処理概要

`contracts` テーブルの未名寄せ契約（`linked_customer_id IS NULL`）を対象に、
同一参照グループ内で名寄せ判定を行い、`customers` テーブルを生成・更新する。

### 処理フロー

```
① contracts から未名寄せ契約を取得
   条件: linked_customer_id IS NULL
         AND contractor_last_name / gender / birth_date が揃っている

② 各契約の contractor_* 情報で名寄せ判定
   find_same_customer():
   - 同一 group_code 内で検索
   - 必須3項目: 性別・生年月日・名（first_name/first_name_raw）が一致
   - AND（電話番号一致 OR 住所一致）

③ 名寄せ結果に応じて処理
   [一致あり] contracts.linked_customer_id を既存顧客IDで更新
              customers.updated_at を更新
   [一致なし] customers に新規レコードを登録（名をマスク保存）
              contracts.linked_customer_id を新顧客IDで更新

④ 処理結果を logs/name_matching_YYYYMMDD_HHMMSS.log に記録

⑤ グループ別・代理店別の顧客数・契約数を出力
```

### 実行方法

```bash
# プロジェクトルート（Cursor/）から実行
python batch/name_matching_batch.py
```

### 出力例

```
2026-05-31 23:00:01 [INFO] ============================================================
2026-05-31 23:00:01 [INFO] 名寄せバッチ 開始
2026-05-31 23:00:01 [INFO] DB: .../db/users.sqlite
2026-05-31 23:00:01 [INFO] ============================================================
2026-05-31 23:00:01 [INFO] 処理対象契約: 5件
2026-05-31 23:00:01 [INFO]   [新規登録] BATCH-A001-0001 → customer_id=27 (山田 ○郎 / G:A)
2026-05-31 23:00:01 [INFO]   [紐付け]  BATCH-A001-0002 → customer_id=3  (山本 ○一 / G:A)
...
2026-05-31 23:00:01 [INFO] 【処理結果サマリー】
2026-05-31 23:00:01 [INFO]   処理対象契約件数 :     5 件
2026-05-31 23:00:01 [INFO]   新規顧客登録     :     3 件
2026-05-31 23:00:01 [INFO]   既存顧客紐付け   :     2 件
2026-05-31 23:00:01 [INFO]   エラー件数       :     0 件
```

### ログファイル

```
logs/
└── name_matching_YYYYMMDD_HHMMSS.log
```

---

## Windowsタスクスケジューラでの夜間自動実行設定

毎日深夜0時に自動実行する手順。

### 手順

**1. タスクスケジューラを開く**

```
スタートメニュー → 検索: 「タスクスケジューラ」→ 起動
```

**2. 右ペイン「タスクの作成」をクリック**

**3. 全般タブ**

| 項目 | 値 |
|---|---|
| 名前 | AX_名寄せバッチ |
| 説明 | 名寄せバッチ夜間実行（毎日00:00） |
| セキュリティオプション | ユーザーがログオンしているかどうかに関わらず実行する |

**4. トリガータブ → 「新規」**

| 項目 | 値 |
|---|---|
| タスクの開始 | スケジュールに従う |
| 設定 | 毎日 |
| 開始 | 00:00:00 |

**5. 操作タブ → 「新規」**

| 項目 | 値 |
|---|---|
| 操作 | プログラムの開始 |
| プログラム/スクリプト | `C:\Users\<user>\AppData\Local\Programs\Python\Python3xx\python.exe` |
| 引数の追加 | `batch\name_matching_batch.py` |
| 開始（作業フォルダ） | `C:\Users\yoshi\OneDrive\ドキュメント\Cursor` |

> Pythonのパス確認: `where python`

**6. 条件タブ（任意）**

「コンピューターをAC電源で使用している場合のみタスクを開始する」のチェックを外す

**7. 「OK」で保存**

パスワードの入力を求められる場合は、Windowsのログインパスワードを入力。

### 動作確認

タスクスケジューラ上でタスクを右クリック → 「実行」で即時テスト実行できる。
