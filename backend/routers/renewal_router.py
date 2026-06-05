"""
更改おすすめプラン通知書APIルーター
renewal_recommend_plansテーブルからPDFをBLOBで取得して返す
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import Response
from typing import Optional
from jose import jwt, JWTError
import sqlite3
import os

router = APIRouter()

_SECRET_KEY = "CHANGE_THIS_SECRET_IN_PRODUCTION"
_ALGORITHM  = "HS256"
_DB_PATH    = os.path.join(os.path.dirname(__file__), "../../db/users.sqlite")


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _verify_token(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="認証トークンがありません")
    token = authorization[len("Bearer "):]
    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="無効または期限切れのトークンです")


@router.get("/renewal-notice/{contract_no}")
def get_renewal_notice(
    contract_no: str,
    payload: dict = Depends(_verify_token),
):
    """
    更改おすすめプラン通知書PDFを返す。

    renewal_recommend_plansテーブルからBLOBを取得してapplication/pdfで返す。
    アクセス制御：ログインユーザーが参照可能な代理店の契約のみ許可。
    """
    conn = _get_db()
    try:
        # 契約の所属代理店・グループを確認
        contract = conn.execute("""
            SELECT c.agency_code, ag.group_code, ag.buka_code
            FROM contracts c
            JOIN agencies ag ON ag.agency_code = c.agency_code
            WHERE c.contract_no = ?
        """, (contract_no,)).fetchone()

        if not contract:
            raise HTTPException(status_code=404, detail="契約が見つかりません")

        # アクセス制御
        user_type = payload.get("user_type", "agency")
        if user_type == "staff":
            role_id   = payload.get("role_id")
            buka_code = payload.get("buka_code")
            if role_id != 1 and contract["buka_code"] != buka_code:
                raise HTTPException(status_code=403, detail="参照権限がありません")
        else:
            group_code = payload.get("group_code")
            if group_code and contract["group_code"] != group_code:
                raise HTTPException(status_code=403, detail="参照権限がありません")

        # PDFを取得
        row = conn.execute(
            "SELECT pdf_data FROM renewal_recommend_plans WHERE contract_no = ?",
            (contract_no,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="更改おすすめプラン通知書がまだ作成されていません")

        pdf_bytes = bytes(row["pdf_data"])
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="renewal_{contract_no}.pdf"',
                "Cache-Control": "private, max-age=300",
            },
        )
    finally:
        conn.close()


@router.get("/renewal-notice/{contract_no}/exists")
def check_renewal_notice_exists(
    contract_no: str,
    payload: dict = Depends(_verify_token),
):
    """更改おすすめプラン通知書の存在確認（フロント表示制御用）"""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT id, generated_at FROM renewal_recommend_plans WHERE contract_no = ?",
            (contract_no,)
        ).fetchone()
        return {"exists": row is not None, "generated_at": row["generated_at"] if row else None}
    finally:
        conn.close()
