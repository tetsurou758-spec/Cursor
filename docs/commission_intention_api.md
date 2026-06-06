# 手数料管理・意向確認 API仕様書

## 手数料管理API

### GET /api/commissions/summary/{agency_code}
手数料サマリー取得
クエリ: fiscal_year(int), month(int, 省略時は年度合計)

### GET /api/commissions/{agency_code}
月別×保険会社別一覧取得
クエリ: fiscal_year(int)

### PUT /api/commissions/{id}
手数料更新（金額・ステータス変更）

### GET /api/commissions/workflow/{agency_code}
ワークフロー進捗取得

## 意向確認API

### GET /api/intentions/{agency_code}
意向確認一覧
クエリ: status, policy_type, staff_code, page, limit

### GET /api/intentions/contract/{policy_no}
証券番号で1件取得（なければ空テンプレート返却）

### POST /api/intentions
新規登録

### PUT /api/intentions/{id}
更新

### GET /api/intentions/unrecorded-count/{agency_code}
未記録件数取得（ダッシュボードバッジ用）
