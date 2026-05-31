# 契約照会API 設計メモ

## エンドポイント一覧

### GET /api/contracts/search
契約検索（ページング・ソート対応）

**クエリパラメータ**
| パラメータ | 型 | 説明 |
|---|---|---|
| q | str | 汎用検索（証券番号/顧客名/電話番号のOR） |
| policy_no | str | 証券番号（部分一致） |
| customer_name | str | 顧客名（部分一致） |
| customer_tel | str | 電話番号（部分一致） |
| policy_type | str | 保険種目（完全一致） |
| agency_code | str | 代理店コード（社員ユーザー絞込用） |
| page | int | ページ番号（default: 1） |
| limit | int | 1ページ件数（default: 50, max: 200） |
| sort_by | str | ソートキー（expiry_date/contract_no/policy_type/customer_name/annual_premium） |
| sort_order | str | 昇降順（asc/desc） |

**レスポンス**
```json
{
  "total": 124,
  "page": 1,
  "limit": 50,
  "contracts": [
    {
      "id": 1,
      "contract_no": "CUST-A001-0001-01",
      "agency_code": "A001",
      "agency_name": "A001代理店",
      "customer_name": "羽生 ○弦",
      "contractor_last_name": "羽生",
      "contractor_first_name": "○弦",
      "contractor_tel": "090-1207-9400",
      "policy_type": "自動車",
      "policy_number": null,
      "expiry_date": "2027-12-07",
      "annual_premium": 135000,
      "renewal_status": "未対応",
      "linked_customer_id": 1
    }
  ]
}
```

---

### GET /api/contracts/direct-search
ダイレクト検索（入力値を自動判定して振り分け）

**判定ロジック**
- 数字始まり → 電話番号検索（contractor_tel LIKE）
- 全角文字始まり → 顧客名検索（customer_name LIKE）
- それ以外 → 証券番号検索（contract_no LIKE）

**クエリパラメータ**
| パラメータ | 型 | 説明 |
|---|---|---|
| q | str | 検索クエリ（必須） |

**レスポンス（0件）**
```json
{ "redirect": "none", "count": 0 }
```

**レスポンス（1件）**
```json
{ "redirect": "detail", "contract_no": "CUST-A001-0001-01", "count": 1 }
```

**レスポンス（複数件）**
```json
{ "redirect": "list", "q": "羽生", "count": 3 }
```

**フロントエンド連携（dashboard.html）**
- `redirect === "detail"` → `contract_detail.html?contract_no=XXXX`
- `redirect === "list"` → `contract.html?q=XXXX`
- `redirect === "none"` → インライン「該当なし」メッセージ

---

### GET /api/contracts/{contract_no}
契約詳細（contract_details LEFT OUTER JOIN）

**パスパラメータ**
| パラメータ | 型 | 説明 |
|---|---|---|
| contract_no | str | 証券番号（完全一致） |

**レスポンス**
```json
{
  "contract": {
    "id": 2,
    "contract_no": "CUST-A001-0001-01",
    "agency_code": "A001",
    "agency_name": "A001代理店",
    "customer_name": "羽生 ○弦",
    "policy_type": "自動車",
    "expiry_date": "2027-12-07",
    "annual_premium": 135000,
    "product_name": "THEクルマの保険",
    "auto_taininsho": "無制限",
    "auto_taibutsusho": "無制限",
    "auto_jinshin": "5,000万円",
    "auto_nfl_grade": 12,
    "auto_car_name": "プリウス",
    ...
  }
}
```

---

## テーブル構成

### contracts（既存）
主要カラム: id, contract_no, agency_code, customer_name, policy_type,
           expiry_date, annual_premium, renewal_status, linked_customer_id,
           contractor_last_name, contractor_first_name, contractor_tel,
           contractor_birth_date, contractor_address

### contract_details（新設）
contract_id（UNIQUE FK → contracts.id）に対し1対1で種目別詳細を格納。
policy_type の値で種目別カラムを使い分ける。

---

## アクセス制御
全エンドポイント共通：

| ユーザー種別 | role_id | アクセス範囲 |
|---|---|---|
| agency | - | 自代理店のgroup_code配下の契約のみ |
| staff | 1 | 全代理店の契約 |
| staff | 2/3 | 同一buka_codeの代理店の契約のみ |

---

## 画面遷移図
```
dashboard.html
  │ 顧客へGo! → customer.html
  │ 契約照会へGo! → /api/contracts/direct-search
  │   1件 → contract_detail.html?contract_no=XXXX
  │   複数 → contract.html?q=XXXX
  │   0件 → インラインメッセージ
  │
  └ グラフクリック → maturity.html?renewal_status=未対応&expiry_month=YYYY-MM

maturity.html
  └ 証券番号リンク → contract_detail.html?contract_no=XXXX

contract.html（一覧）
  └ 証券番号リンク → contract_detail.html?contract_no=XXXX

contract_detail.html（詳細）
  └ ← 一覧に戻る → contract.html
```
