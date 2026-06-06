"""
AIレコメンドAPIルーター
Claude APIを使用して顧客への保険加入推奨を生成・管理する。

エンドポイント:
    POST /api/ai/recommend/{customer_id}           -- 個別推奨生成
    GET  /api/ai/recommend/{customer_id}           -- 最新推奨取得
    GET  /api/ai/recommend/summary/{agency_code}   -- 代理店サマリー
    POST /api/ai/recommend/bulk/{agency_code}      -- 一括推奨生成
"""

import datetime
import json
import os
import sqlite3
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Header
from jose import jwt, JWTError

router = APIRouter()

_SECRET_KEY = "CHANGE_THIS_SECRET_IN_PRODUCTION"
_ALGORITHM  = "HS256"
_DB_PATH    = os.path.join(os.path.dirname(__file__), "../../db/users.sqlite")

# 種目コード→種目名の変換マップ
_CODE_TO_NAME = {
    "AUTO":       "自動車",
    "FIRE":       "火災",
    "INJURY":     "傷害",
    "JIBAI":      "自賠責",
    "LIABILITY":  "賠償責任",
    "CYBER":      "サイバーリスク",
    "INCOME":     "所得補償",
}

# 種目名→種目コードの逆変換マップ
_NAME_TO_CODE = {v: k for k, v in _CODE_TO_NAME.items()}


def _get_db() -> sqlite3.Connection:
    """SQLite接続を取得する"""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _verify_token(authorization: Optional[str] = Header(default=None)) -> dict:
    """AuthorizationヘッダーのBearerトークンを検証してペイロードを返す"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="認証トークンがありません")
    token = authorization[len("Bearer "):]
    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="無効または期限切れのトークンです")


def _ensure_table(conn: sqlite3.Connection):
    """ai_recommendationsテーブルが存在しない場合は作成する"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_recommendations (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id      TEXT NOT NULL,
            agency_code      TEXT,
            recommend_types  TEXT NOT NULL,
            reason           TEXT,
            risk_score       REAL,
            is_bulk          INTEGER DEFAULT 0,
            created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def _call_claude_recommend(
    last_name: str,
    first_name: str,
    birth_date: str,
    gender: str,
    current_types: list,
    uncovered_types: list,
) -> dict:
    """
    Claude APIを呼び出して保険推奨JSONを生成して返す。
    エラー時はHTTPException(500)を発生させる。
    """
    current_str   = "、".join(current_types)  if current_types   else "なし"
    uncovered_str = "、".join(uncovered_types) if uncovered_types else "なし"

    prompt = f"""あなたは保険のプロフェッショナルアドバイザーです。
以下の顧客情報と現在の加入状況に基づいて、追加で加入すべき保険種目を推奨してください。

顧客情報：
- 氏名: {last_name} {first_name}
- 生年月日: {birth_date}
- 性別: {gender}

現在の加入種目: {current_str}
未加入種目: {uncovered_str}

以下のJSON形式のみで回答してください（説明文は不要）:
{{
  "recommend_types": ["推奨種目コード1", "推奨種目コード2"],
  "reason": "推奨理由を200字以内で",
  "risk_score": 0.75
}}

種目コード: AUTO=自動車, FIRE=火災, INJURY=傷害, JIBAI=自賠責, LIABILITY=賠償責任, CYBER=サイバーリスク, INCOME=所得補償
recommend_typesには未加入種目の中から推奨するものだけを含めてください。
risk_scoreは0.0〜1.0で、1.0に近いほどリスクが高いことを示します。"""

    try:
        client  = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(message.content[0].text)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="AI推奨の生成に失敗しました")


def _build_recommend_response(row: sqlite3.Row, customer_name: str) -> dict:
    """DBレコードからレスポンス辞書を組み立てる"""
    recommend_types = json.loads(row["recommend_types"]) if isinstance(row["recommend_types"], str) else row["recommend_types"]
    return {
        "id":              row["id"],
        "customer_id":     row["customer_id"],
        "customer_name":   customer_name,
        "recommend_types": recommend_types,
        "reason":          row["reason"],
        "risk_score":      row["risk_score"],
        "created_at":      row["created_at"],
    }


# ── サマリー・一括エンドポイント（/{customer_id}より先に定義してルーティング衝突を回避）──


@router.get("/ai/recommend/summary/{agency_code}")
def get_recommend_summary(
    agency_code: str,
    payload: dict = Depends(_verify_token),
):
    """
    指定代理店の全顧客について最新AI推奨を集計して返す。

    アクセス制御：
    - 代理店ユーザー → 自身の代理店のみ
    - 社員ユーザー   → buka_codeが一致する代理店のみ（role_id=1は全代理店）
    """
    user_type = payload.get("user_type", "agency")
    conn = _get_db()
    try:
        _ensure_table(conn)

        # アクセス制御
        if user_type == "staff":
            role_id   = payload.get("role_id")
            buka_code = payload.get("buka_code")
            if role_id != 1:
                # buka_codeが一致する代理店のみ参照可
                ag = conn.execute(
                    "SELECT 1 FROM agencies WHERE agency_code = ? AND buka_code = ?",
                    (agency_code, buka_code)
                ).fetchone()
                if not ag:
                    raise HTTPException(status_code=403, detail="参照権限がありません")
        else:
            # 代理店ユーザーは自身の代理店のみ
            if payload.get("agency_code") != agency_code:
                raise HTTPException(status_code=403, detail="参照権限がありません")

        # 代理店に紐づく顧客IDリストを取得
        cust_rows = conn.execute("""
            SELECT DISTINCT c.linked_customer_id
            FROM contracts c
            WHERE c.agency_code = ? AND c.linked_customer_id IS NOT NULL
        """, (agency_code,)).fetchall()
        customer_ids = [r["linked_customer_id"] for r in cust_rows]
        total_customers = len(customer_ids)

        if not customer_ids:
            return {
                "agency_code":         agency_code,
                "total_customers":     0,
                "analyzed_customers":  0,
                "recommend_summary":   {},
                "high_risk_customers": [],
            }

        # 各顧客の最新レコメンドを取得
        placeholders = ",".join("?" * len(customer_ids))
        latest_rows = conn.execute(f"""
            SELECT ar.*, cu.last_name, cu.first_name
            FROM ai_recommendations ar
            JOIN customers cu ON cu.customer_id = ar.customer_id
            WHERE ar.customer_id IN ({placeholders})
              AND ar.created_at = (
                  SELECT MAX(ar2.created_at)
                  FROM ai_recommendations ar2
                  WHERE ar2.customer_id = ar.customer_id
              )
        """, customer_ids).fetchall()

        analyzed_customers = len(latest_rows)
        recommend_summary: dict = {}
        high_risk_customers = []

        for row in latest_rows:
            # recommend_typesをパース・集計
            try:
                rtypes = json.loads(row["recommend_types"]) if isinstance(row["recommend_types"], str) else []
            except Exception:
                rtypes = []
            for t in rtypes:
                recommend_summary[t] = recommend_summary.get(t, 0) + 1

            # ハイリスク顧客（risk_score >= 0.7）
            risk_score = row["risk_score"] or 0.0
            if risk_score >= 0.7:
                high_risk_customers.append({
                    "customer_id":   row["customer_id"],
                    "customer_name": f"{row['last_name']} {row['first_name']}",
                    "risk_score":    risk_score,
                })

        # ハイリスク顧客をrisk_score降順・最大10件に絞る
        high_risk_customers = sorted(high_risk_customers, key=lambda x: x["risk_score"], reverse=True)[:10]

        return {
            "agency_code":         agency_code,
            "total_customers":     total_customers,
            "analyzed_customers":  analyzed_customers,
            "recommend_summary":   recommend_summary,
            "high_risk_customers": high_risk_customers,
        }
    finally:
        conn.close()


@router.post("/ai/recommend/bulk/{agency_code}")
def post_recommend_bulk(
    agency_code: str,
    payload: dict = Depends(_verify_token),
):
    """
    指定代理店の全顧客（有効顧客）に対して一括でAI推奨を生成する。
    """
    user_type = payload.get("user_type", "agency")
    conn = _get_db()
    try:
        _ensure_table(conn)

        # アクセス制御（サマリーと同様）
        if user_type == "staff":
            role_id   = payload.get("role_id")
            buka_code = payload.get("buka_code")
            if role_id != 1:
                ag = conn.execute(
                    "SELECT 1 FROM agencies WHERE agency_code = ? AND buka_code = ?",
                    (agency_code, buka_code)
                ).fetchone()
                if not ag:
                    raise HTTPException(status_code=403, detail="参照権限がありません")
        else:
            if payload.get("agency_code") != agency_code:
                raise HTTPException(status_code=403, detail="参照権限がありません")

        # 代理店に紐づく有効顧客IDリストを取得
        cust_rows = conn.execute("""
            SELECT DISTINCT c.linked_customer_id
            FROM contracts c
            WHERE c.agency_code = ?
              AND c.linked_customer_id IS NOT NULL
              AND (c.status IS NULL OR c.status != '失効')
        """, (agency_code,)).fetchall()
        customer_ids = [r["linked_customer_id"] for r in cust_rows]

        bulk_job_id = f"BULK_{agency_code}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        processed = 0
        failed    = 0

        # 全7種目を取得
        all_types_rows = conn.execute("SELECT type_code, type_name FROM policy_types").fetchall()
        all_type_codes = [r["type_code"] for r in all_types_rows]

        for customer_id in customer_ids:
            try:
                # 顧客情報を取得
                customer = conn.execute("""
                    SELECT last_name, first_name, birth_date, gender, group_code
                    FROM customers
                    WHERE customer_id = ?
                """, (customer_id,)).fetchone()
                if not customer:
                    failed += 1
                    continue

                # 有効契約の種目を取得
                contract_rows = conn.execute("""
                    SELECT DISTINCT policy_type
                    FROM contracts
                    WHERE linked_customer_id = ? AND (status IS NULL OR status != '失効')
                """, (customer_id,)).fetchall()
                current_type_names = [r["policy_type"] for r in contract_rows if r["policy_type"]]
                current_codes      = [_NAME_TO_CODE.get(n, n) for n in current_type_names]
                uncovered_codes    = [c for c in all_type_codes if c not in current_codes]

                # Claude API呼び出し
                result = _call_claude_recommend(
                    last_name=customer["last_name"],
                    first_name=customer["first_name"],
                    birth_date=customer["birth_date"] or "",
                    gender=customer["gender"] or "",
                    current_types=current_type_names,
                    uncovered_types=[_CODE_TO_NAME.get(c, c) for c in uncovered_codes],
                )

                recommend_types = result.get("recommend_types", [])
                reason          = result.get("reason", "")
                risk_score      = float(result.get("risk_score", 0.5))

                conn.execute("""
                    INSERT INTO ai_recommendations
                    (customer_id, agency_code, recommend_types, reason, risk_score, is_bulk, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """, (customer_id, agency_code, json.dumps(recommend_types, ensure_ascii=False), reason, risk_score))
                conn.commit()
                processed += 1

            except HTTPException:
                failed += 1
            except Exception:
                failed += 1

        return {
            "bulk_job_id":  bulk_job_id,
            "agency_code":  agency_code,
            "processed":    processed,
            "failed":       failed,
            "message":      "一括推奨生成が完了しました",
        }
    finally:
        conn.close()


# ── 個別顧客エンドポイント ──────────────────────────────────────────────────────


@router.post("/ai/recommend/{customer_id}")
def post_recommend(
    customer_id: str,
    payload: dict = Depends(_verify_token),
):
    """
    顧客IDのAI推奨を生成してai_recommendationsテーブルに保存し、結果を返す。
    """
    conn = _get_db()
    try:
        _ensure_table(conn)

        # 顧客情報を取得
        customer = conn.execute("""
            SELECT last_name, first_name, birth_date, gender, group_code
            FROM customers
            WHERE customer_id = ?
        """, (customer_id,)).fetchone()

        if not customer:
            raise HTTPException(status_code=404, detail="顧客が見つかりません")

        customer_name = f"{customer['last_name']} {customer['first_name']}"
        group_code    = customer["group_code"]

        # アクセス制御
        user_type = payload.get("user_type", "agency")
        if user_type != "staff":
            user_grp = payload.get("group_code")
            if user_grp and group_code != user_grp:
                raise HTTPException(status_code=403, detail="参照権限がありません")

        # 有効契約の種目を取得（日本語名で格納済み）
        contract_rows = conn.execute("""
            SELECT DISTINCT policy_type
            FROM contracts
            WHERE linked_customer_id = ? AND (status IS NULL OR status != '失効')
        """, (customer_id,)).fetchall()
        current_type_names = [r["policy_type"] for r in contract_rows if r["policy_type"]]
        current_codes      = [_NAME_TO_CODE.get(n, n) for n in current_type_names]

        # 全7種目を取得して未加入種目を計算
        all_types_rows = conn.execute("SELECT type_code FROM policy_types").fetchall()
        all_type_codes = [r["type_code"] for r in all_types_rows]
        if not all_type_codes:
            # policy_typesテーブルが空の場合はデフォルト値を使用
            all_type_codes = list(_CODE_TO_NAME.keys())

        uncovered_codes = [c for c in all_type_codes if c not in current_codes]
        uncovered_names = [_CODE_TO_NAME.get(c, c) for c in uncovered_codes]

        # Claude API呼び出し
        result = _call_claude_recommend(
            last_name=customer["last_name"],
            first_name=customer["first_name"],
            birth_date=customer["birth_date"] or "",
            gender=customer["gender"] or "",
            current_types=current_type_names,
            uncovered_types=uncovered_names,
        )

        recommend_types = result.get("recommend_types", [])
        reason          = result.get("reason", "")
        risk_score      = float(result.get("risk_score", 0.5))

        # DBに保存
        cur = conn.execute("""
            INSERT INTO ai_recommendations
            (customer_id, agency_code, recommend_types, reason, risk_score, is_bulk, created_at)
            VALUES (?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
        """, (
            customer_id,
            payload.get("agency_code"),
            json.dumps(recommend_types, ensure_ascii=False),
            reason,
            risk_score,
        ))
        conn.commit()
        new_id = cur.lastrowid

        row = conn.execute("SELECT * FROM ai_recommendations WHERE id = ?", (new_id,)).fetchone()
        return {
            "id":              row["id"],
            "customer_id":     customer_id,
            "customer_name":   customer_name,
            "current_types":   current_type_names,
            "uncovered_types": uncovered_codes,
            "recommend_types": recommend_types,
            "reason":          reason,
            "risk_score":      risk_score,
            "created_at":      row["created_at"],
        }
    finally:
        conn.close()


@router.get("/ai/recommend/{customer_id}")
def get_recommend(
    customer_id: str,
    payload: dict = Depends(_verify_token),
):
    """
    ai_recommendationsテーブルから指定顧客の最新レコードを1件取得して返す。
    レコードが存在しない場合は404を返す。
    """
    conn = _get_db()
    try:
        _ensure_table(conn)

        # 顧客情報を取得
        customer = conn.execute("""
            SELECT last_name, first_name, group_code
            FROM customers
            WHERE customer_id = ?
        """, (customer_id,)).fetchone()

        if not customer:
            raise HTTPException(status_code=404, detail="顧客が見つかりません")

        customer_name = f"{customer['last_name']} {customer['first_name']}"
        group_code    = customer["group_code"]

        # アクセス制御
        user_type = payload.get("user_type", "agency")
        if user_type != "staff":
            user_grp = payload.get("group_code")
            if user_grp and group_code != user_grp:
                raise HTTPException(status_code=403, detail="参照権限がありません")

        # 最新レコードを取得
        row = conn.execute("""
            SELECT * FROM ai_recommendations
            WHERE customer_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (customer_id,)).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="AI推奨が見つかりません")

        return _build_recommend_response(row, customer_name)
    finally:
        conn.close()
