"""
手数料管理APIルーター
代理店単位の手数料データを取得・更新する。

エンドポイント:
    GET /api/commissions/workflow/{agency_code}  -- ワークフロー進捗取得
    GET /api/commissions/summary/{agency_code}   -- 手数料サマリー取得
    GET /api/commissions/{agency_code}           -- 月別×保険会社別データ取得
    PUT /api/commissions/{id}                    -- 手数料データ更新
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

# ワークフローステップ定義（順序が進捗を表す）
WORKFLOW_STEPS = ['作成中', '自己査定待ち', '初級確認待ち', '給与担当者送付待ち', '完了']


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
            # role_id=1以外はbuka_codeで管轄確認
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
        # 代理店ユーザーは自代理店のみ
        if payload.get("agency_code") != agency_code:
            raise HTTPException(status_code=403, detail="参照権限がありません")


# Pydanticモデル定義
class CommissionUpdateRequest(BaseModel):
    """手数料データ更新リクエストのスキーマ（すべてオプション）"""
    first_year_amount: Optional[int] = None
    renewal_amount:    Optional[int] = None
    other_amount:      Optional[int] = None
    status:            Optional[str] = None


# ── ワークフロー進捗取得 ────────────────────────────────────────────────────────

@router.get("/commissions/workflow/{agency_code}")
def get_commission_workflow(
    agency_code: str,
    payload: dict = Depends(_verify_token),
):
    """
    代理店のワークフロー進捗を返す。
    最新データのstatusを代表値として使用し、ステップの完了状態を判定する。
    """
    _check_agency_access(payload, agency_code)

    conn = _get_db()
    try:
        # 最新月のstatusを取得（fiscal_year降順・month降順で最初の1件）
        row = conn.execute("""
            SELECT status FROM commissions
            WHERE agency_code = ?
            ORDER BY fiscal_year DESC, month DESC
            LIMIT 1
        """, (agency_code,)).fetchone()

        # データが存在しない場合は先頭ステップを現在ステップとする
        current_status = row["status"] if row else WORKFLOW_STEPS[0]

        # current_statusがWORKFLOW_STEPSに含まれない場合は先頭を使用
        if current_status not in WORKFLOW_STEPS:
            current_status = WORKFLOW_STEPS[0]

        current_idx = WORKFLOW_STEPS.index(current_status)

        steps = [
            {
                "name": step,
                "done": i < current_idx,  # 現在ステップより前は完了扱い
            }
            for i, step in enumerate(WORKFLOW_STEPS)
        ]

        return {
            "current_step": current_status,
            "steps": steps,
        }
    finally:
        conn.close()


# ── 手数料サマリー取得 ─────────────────────────────────────────────────────────

@router.get("/commissions/summary/{agency_code}")
def get_commission_summary(
    agency_code:  str,
    fiscal_year:  int           = Query(..., description="会計年度（必須）"),
    month:        Optional[int] = Query(default=None, description="月（省略時は年度合計）"),
    payload: dict = Depends(_verify_token),
):
    """
    代理店の手数料サマリーを返す。
    monthを省略した場合は年度全体の合計。保険会社別内訳も付与する。
    """
    _check_agency_access(payload, agency_code)

    conn = _get_db()
    try:
        # 保険会社別集計
        if month is not None:
            rows = conn.execute("""
                SELECT insurer_name,
                       SUM(first_year_amount) as first_year,
                       SUM(renewal_amount)    as renewal,
                       SUM(other_amount)      as other,
                       SUM(first_year_amount+renewal_amount+other_amount) as total,
                       MAX(status)            as status
                FROM commissions
                WHERE agency_code = ? AND fiscal_year = ? AND month = ?
                GROUP BY insurer_name
                ORDER BY total DESC
            """, (agency_code, fiscal_year, month)).fetchall()
        else:
            rows = conn.execute("""
                SELECT insurer_name,
                       SUM(first_year_amount) as first_year,
                       SUM(renewal_amount)    as renewal,
                       SUM(other_amount)      as other,
                       SUM(first_year_amount+renewal_amount+other_amount) as total,
                       MAX(status)            as status
                FROM commissions
                WHERE agency_code = ? AND fiscal_year = ?
                GROUP BY insurer_name
                ORDER BY total DESC
            """, (agency_code, fiscal_year)).fetchall()

        by_insurer = [dict(r) for r in rows]

        # 店舗合計を計算
        store_total = sum(r["total"]      or 0 for r in by_insurer)
        first_year  = sum(r["first_year"] or 0 for r in by_insurer)
        renewal     = sum(r["renewal"]    or 0 for r in by_insurer)
        other       = sum(r["other"]      or 0 for r in by_insurer)

        return {
            "fiscal_year":  fiscal_year,
            "month":        month,
            "store_total":  store_total,
            "first_year":   first_year,
            "renewal":      renewal,
            "other":        other,
            "by_insurer":   by_insurer,
        }
    finally:
        conn.close()


# ── 月別×保険会社別データ取得 ─────────────────────────────────────────────────

@router.get("/commissions/{agency_code}")
def get_commissions(
    agency_code: str,
    fiscal_year: int  = Query(..., description="会計年度（必須）"),
    payload: dict     = Depends(_verify_token),
):
    """
    代理店の月別×保険会社別の手数料データを全件返す。
    """
    _check_agency_access(payload, agency_code)

    conn = _get_db()
    try:
        rows = conn.execute("""
            SELECT * FROM commissions
            WHERE agency_code = ? AND fiscal_year = ?
            ORDER BY month, insurer_name
        """, (agency_code, fiscal_year)).fetchall()

        return {"commissions": [dict(r) for r in rows]}
    finally:
        conn.close()


# ── 手数料データ更新 ──────────────────────────────────────────────────────────

@router.put("/commissions/{id}")
def update_commission(
    id:      int,
    request: CommissionUpdateRequest,
    payload: dict = Depends(_verify_token),
):
    """
    手数料データを部分更新する。
    updated_atも同時にlocaltime現在時刻へ更新する。
    """
    conn = _get_db()
    try:
        # 対象レコードを取得し、アクセス権限も確認
        row = conn.execute(
            "SELECT id, agency_code FROM commissions WHERE id = ?", (id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="手数料データが見つかりません")

        _check_agency_access(payload, row["agency_code"])

        fields, params = [], []
        if request.first_year_amount is not None:
            fields.append("first_year_amount = ?"); params.append(request.first_year_amount)
        if request.renewal_amount is not None:
            fields.append("renewal_amount = ?"); params.append(request.renewal_amount)
        if request.other_amount is not None:
            fields.append("other_amount = ?"); params.append(request.other_amount)
        if request.status is not None:
            fields.append("status = ?"); params.append(request.status)

        if not fields:
            raise HTTPException(status_code=400, detail="更新する項目がありません")

        # updated_atをローカル時刻で更新
        fields.append("updated_at = datetime('now','localtime')")
        params.append(id)

        conn.execute(f"UPDATE commissions SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()

        return {"message": "更新しました", "id": id}
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
