# AIレコメンドAPI仕様書

## エンドポイント一覧

### POST /api/ai/recommend/{customer_id}
個別顧客向けAI推奨を生成・保存する。

**リクエストヘッダー**
- Authorization: Bearer {token}

**レスポンス**
```json
{
  "customer_id": "C001",
  "customer_name": "山田 太郎",
  "current_types": ["自動車", "火災"],
  "recommend_types": ["CYBER", "INCOME"],
  "reason": "...",
  "risk_score": 0.75,
  "id": 1
}
```

### GET /api/ai/recommend/{customer_id}
最新のAI推奨結果を取得する。

### GET /api/ai/recommend/summary/{agency_code}
代理店全体の推奨サマリー（未加入種目の集計）を返す。

### POST /api/ai/recommend/bulk/{agency_code}
代理店の全顧客に対して一括でAI推奨を生成する。

## Claudeプロンプト仕様

モデル: claude-sonnet-4-20250514
max_tokens: 1000
レスポンス形式: JSON（recommend_types配列, reason文字列, risk_score数値）

## セキュリティ
- APIキーは backend/.env の ANTHROPIC_API_KEY のみに記載
- フロントエンドからAPIキーを直接参照しない
