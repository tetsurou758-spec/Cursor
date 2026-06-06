"""
意向確認APIルーター
契約単位の意向確認データを登録・取得・更新する。

エンドポイント:
    GET  /api/intentions/unrecorded-count/{agency_code}  -- 未記録件数取得
    GET  /api/intentions/contract/{policy_no}            -- 証券番号で1件取得
    GET  /api/intentions/{agency_code}                   -- 一覧取得（絞込・ページング）
    POST /api/intentions                                 -- 新規登録
    PUT  /api/intentions/{id}                            -- 更新
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from jose import jwt, JWTError
from pydantic import BaseModel

router = APIRouter()

_SECRET_KEY = "CHANGE_THIS_SECRET_IN_PRODUCTION"
_ALGORITHM  = "HS256"
_DB_PATH    = os.path.join(os.path.dirname(__file__), "../../db/users.sqlite")


def _get_db():
    """SQLite接続を取得する"""
    import sqlite3
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


def _check_agency_access(payload: dict, agency_code: str):
    """代理店アクセス権限チェック（代理店ユーザーは自代理店のみ、社員はbuka_codeで判定）"""
    user_type = payload.get("user_type", "agency")
    if user_type == "staff":
        role_id   = payload.get("role_id")
        buka_code = payload.get("buka_code")
        if role_id != 1:
            conn = _get_db()
            try:
                row = conn.execute(
                    "SELECT 1 FROM agencies WHERE agency_code = ? AND buka_code = ?",
                    (agency_code, buka_code)
                ).fetchone()
                if not row:
                    raise HTTPException(status_code=403, detail="参照権限がありません")
            finally:
                conn.close()
    else:
        if payload.get("agency_code") != agency_code:
            raise HTTPException(status_code=403, detail="参照権限がありません")


# Pydanticモデル定義
class IntentionCreateRequest(BaseModel):
    """意向確認新規登録リクエストのスキーマ"""
    contract_id:           Optional[int] = None
    policy_no:             str
    agency_code:           str
    customer_name:         str
    staff_code:            Optional[str] = None
    policy_type:           Optional[str] = None
    customer_needs:        Optional[str] = None
    proposed_products:     Optional[str] = None
    compared_products:     Optional[str] = None
    recommendation_reason: Optional[str] = None
    final_product:         Optional[str] = None
    customer_confirmed:    Optional[int] = 0
    confirmed_at:          Optional[str] = None
    lapse_reason:          Optional[str] = None
    lapse_detail:          Optional[str] = None
    status:                Optional[str] = "未記録"


class IntentionUpdateRequest(BaseModel):
    """意向確認更新リクエストのスキーマ（すべてオプション）"""
    contract_id:           Optional[int] = None
    policy_no:             Optional[str] = None
    agency_code:           Optional[str] = None
    customer_name:         Optional[str] = None
    staff_code:            Optional[str] = None
    policy_type:           Optional[str] = None
    customer_needs:        Optional[str] = None
    proposed_products:     Optional[str] = None
    compared_products:     Optional[str] = None
    recommendation_reason: Optional[str] = None
    final_product:         Optional[str] = None
    customer_confirmed:    Optional[int] = None
    confirmed_at:          Optional[str] = None
    lapse_reason:          Optional[str] = None
    lapse_detail:          Optional[str] = None
    status:                Optional[str] = None


# ── 未記録件数取得 ─────────────────────────────────────────────────────────────

@router.get("/intentions/unrecorded-count/{agency_code}")
def get_unrecorded_count(
    agency_code: str,
    payload: dict = Depends(_verify_token),
):
    """
    代理店の意向確認未記録件数を返す。
    intention_confirmationsに存在しないcontractsの件数として算出する。
    """
    _check_agency_access(payload, agency_code)

    conn = _get_db()
    try:
        row = conn.execute("""
            SELECT COUNT(*) as count
            FROM contracts c
            LEFT OUTER JOIN intention_confirmations i ON c.contract_no = i.policy_no
            WHERE c.agency_code = ?
              AND (i.id IS NULL OR i.status = '未記録')
        """, (agency_code,)).fetchone()

        return {"count": row["count"] if row else 0, "agency_code": agency_code}
    finally:
        conn.close()


# ── 証券番号で1件取得 ──────────────────────────────────────────────────────────

@router.get("/intentions/contract/{policy_no}")
def get_intention_by_policy_no(
    policy_no: str,
    payload:   dict = Depends(_verify_token),
):
    """
    証券番号で意向確認データを1件取得する。
    存在しない場合は空テンプレートを返す（id=null）。
    """
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT * FROM intention_confirmations WHERE policy_no = ?",
            (policy_no,)
        ).fetchone()

        if row:
            return dict(row)
        else:
            # データがない場合は空テンプレートを返す
            return {
                "id":                    None,
                "policy_no":             policy_no,
                "status":                "未記録",
                "contract_id":           None,
                "agency_code":           None,
                "customer_name":         None,
                "staff_code":            None,
                "policy_type":           None,
                "customer_needs":        None,
                "proposed_products":     None,
                "compared_products":     None,
                "recommendation_reason": None,
                "final_product":         None,
                "customer_confirmed":    0,
                "confirmed_at":          None,
                "lapse_reason":          None,
                "lapse_detail":          None,
                "created_at":            None,
                "updated_at":            None,
            }
    finally:
        conn.close()


# ── 一覧取得（絞込・ページング） ───────────────────────────────────────────────

@router.get("/intentions/{agency_code}")
def get_intentions(
    agency_code:  str,
    status:       Optional[str] = Query(default=None, description="ステータス絞込"),
    policy_type:  Optional[str] = Query(default=None, description="保険種目絞込"),
    staff_code:   Optional[str] = Query(default=None, description="担当者コード絞込"),
    page:         int           = Query(default=1,  ge=1),
    limit:        int           = Query(default=20, ge=1, le=100),
    payload: dict = Depends(_verify_token),
):
    """
    代理店の意向確認一覧を返す（絞込・ページネーション対応）。
    contractsテーブルを基準にLEFT JOINして、意向未記録の契約も含める。
    未記録件数もあわせて返す。
    """
    _check_agency_access(payload, agency_code)

    conn = _get_db()
    try:
        # contractsを基準にLEFT JOINで組み立てる
        sql = """
            SELECT
              c.id              AS contract_id,
              c.contract_no     AS policy_no,
              c.agency_code,
              c.policy_type,
              c.expiry_date,
              cu.last_name || ' ' || cu.first_name AS customer_name,
              c.staff_code,
              COALESCE(i.status, '未記録') AS status,
              i.id              AS intention_id,
              i.customer_needs,
              i.lapse_reason,
              i.confirmed_at,
              i.updated_at
            FROM contracts c
            LEFT JOIN customers cu ON cu.customer_id = c.linked_customer_id
            LEFT OUTER JOIN intention_confirmations i ON c.contract_no = i.policy_no
            WHERE c.agency_code = ?
        """
        params = [agency_code]

        # statusフィルタ（COALESCE後の値で絞り込む）
        if status and status != 'all':
            sql += " AND COALESCE(i.status, '未記録') = ?"
            params.append(status)
        if policy_type:
            sql += " AND c.policy_type = ?"
            params.append(policy_type)
        if staff_code:
            sql += " AND c.staff_code = ?"
            params.append(staff_code)

        # 未記録を先頭・次いで記録済・最後に確認済、同一ステータス内は満期日昇順
        sql += """
            ORDER BY
              CASE COALESCE(i.status, '未記録')
                WHEN '未記録' THEN 1
                WHEN '記録済' THEN 2
                WHEN '確認済' THEN 3
                ELSE 4
              END,
              c.expiry_date ASC
        """

        all_rows = conn.execute(sql, params).fetchall()
        total    = len(all_rows)

        offset = (page - 1) * limit
        paged  = all_rows[offset:offset + limit]

        # 未記録件数：intention_confirmationsに存在しない契約の件数
        unrecorded_row = conn.execute("""
            SELECT COUNT(*) as count
            FROM contracts c
            LEFT OUTER JOIN intention_confirmations i ON c.contract_no = i.policy_no
            WHERE c.agency_code = ?
              AND (i.id IS NULL OR i.status = '未記録')
        """, (agency_code,)).fetchone()
        unrecorded_count = unrecorded_row["count"] if unrecorded_row else 0

        return {
            "total":            total,
            "unrecorded_count": unrecorded_count,
            "page":             page,
            "limit":            limit,
            "intentions":       [dict(r) for r in paged],
        }
    finally:
        conn.close()


# ── 新規登録 ──────────────────────────────────────────────────────────────────

@router.post("/intentions", status_code=201)
def create_intention(
    request: IntentionCreateRequest,
    payload: dict = Depends(_verify_token),
):
    """意向確認データを新規登録する。"""
    _check_agency_access(payload, request.agency_code)

    conn = _get_db()
    try:
        cur = conn.execute("""
            INSERT INTO intention_confirmations (
                contract_id, policy_no, agency_code, customer_name,
                staff_code, policy_type, customer_needs, proposed_products,
                compared_products, recommendation_reason, final_product,
                customer_confirmed, confirmed_at, lapse_reason, lapse_detail, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.contract_id,
            request.policy_no,
            request.agency_code,
            request.customer_name,
            request.staff_code,
            request.policy_type,
            request.customer_needs,
            request.proposed_products,
            request.compared_products,
            request.recommendation_reason,
            request.final_product,
            request.customer_confirmed,
            request.confirmed_at,
            request.lapse_reason,
            request.lapse_detail,
            request.status,
        ))
        conn.commit()
        return {"message": "登録しました", "id": cur.lastrowid}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── 更新 ──────────────────────────────────────────────────────────────────────

@router.put("/intentions/{id}")
def update_intention(
    id:      int,
    request: IntentionUpdateRequest,
    payload: dict = Depends(_verify_token),
):
    """
    意向確認データを部分更新する。
    updated_atも同時にlocaltime現在時刻へ更新する。
    """
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT id, agency_code FROM intention_confirmations WHERE id = ?", (id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="意向確認データが見つかりません")

        _check_agency_access(payload, row["agency_code"])

        fields, params = [], []
        if request.contract_id is not None:
            fields.append("contract_id = ?"); params.append(request.contract_id)
        if request.policy_no is not None:
            fields.append("policy_no = ?"); params.append(request.policy_no)
        if request.agency_code is not None:
            fields.append("agency_code = ?"); params.append(request.agency_code)
        if request.customer_name is not None:
            fields.append("customer_name = ?"); params.append(request.customer_name)
        if request.staff_code is not None:
            fields.append("staff_code = ?"); params.append(request.staff_code)
        if request.policy_type is not None:
            fields.append("policy_type = ?"); params.append(request.policy_type)
        if request.customer_needs is not None:
            fields.append("customer_needs = ?"); params.append(request.customer_needs)
        if request.proposed_products is not None:
            fields.append("proposed_products = ?"); params.append(request.proposed_products)
        if request.compared_products is not None:
            fields.append("compared_products = ?"); params.append(request.compared_products)
        if request.recommendation_reason is not None:
            fields.append("recommendation_reason = ?"); params.append(request.recommendation_reason)
        if request.final_product is not None:
            fields.append("final_product = ?"); params.append(request.final_product)
        if request.customer_confirmed is not None:
            fields.append("customer_confirmed = ?"); params.append(request.customer_confirmed)
        if request.confirmed_at is not None:
            fields.append("confirmed_at = ?"); params.append(request.confirmed_at)
        if request.lapse_reason is not None:
            fields.append("lapse_reason = ?"); params.append(request.lapse_reason)
        if request.lapse_detail is not None:
            fields.append("lapse_detail = ?"); params.append(request.lapse_detail)
        if request.status is not None:
            fields.append("status = ?"); params.append(request.status)

        if not fields:
            raise HTTPException(status_code=400, detail="更新する項目がありません")

        # updated_atをローカル時刻で更新
        fields.append("updated_at = datetime('now','localtime')")
        params.append(id)

        conn.execute(
            f"UPDATE intention_confirmations SET {', '.join(fields)} WHERE id = ?",
            params
        )
        conn.commit()
        return {"message": "更新しました"}
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
