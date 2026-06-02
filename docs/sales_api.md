# 成績管理API設計

## エンドポイント一覧

### GET /api/sales/actual
- 概要：月別×種目別の実績集計を返す
- クエリパラメータ：agency_code, staff_code, fiscal_year, token
- 処理：contractsテーブルのpremiumを集計。staff_code='ALL'は代理店全体。年度判定はfiscal_year/4/1〜fiscal_year+1/3/31
- 返却例：
```json
{
  "fiscal_year": 2026,
  "staff_code": "staff1",
  "data": {
    "AUTO": {"4": 158000, "5": 143000},
    "TOTAL": {"4": 500000}
  }
}
```

### GET /api/sales/targets
- 概要：目標データを返す
- クエリパラメータ：agency_code, staff_code, fiscal_year, token
- 返却：actualと同じ構造

### POST /api/sales/targets
- 概要：目標データを保存（管理者のみ）
- リクエストボディ：agency_code, staff_code, fiscal_year, targets配列
- 処理：INSERT OR REPLACEでUPSERT

### GET /api/sales/staff-list
- 概要：担当者プルダウン用リストを返す
- クエリパラメータ：agency_code, token
- 返却例：
```json
[
  {"staff_code": "admin", "name": "管理者 太郎"},
  {"staff_code": "staff1", "name": "担当 一郎"},
  {"staff_code": "ALL", "name": "代理店合計"}
]
```

## 権限制御
- 社員トークンでのアクセスは全エンドポイント403で拒否
- POST /api/sales/targets は管理者ロールのみ許可
