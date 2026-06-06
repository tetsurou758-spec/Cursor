"""
リスクマップPDF APIルーター
顧客単位・契約単位のリスクマップPDFを生成・保存・取得する。

エンドポイント:
    POST /api/riskmap/customer/{customer_id}  -- 顧客リスクマップ生成
    GET  /api/riskmap/customer/{customer_id}  -- 顧客リスクマップ取得
    POST /api/riskmap/contract/{contract_no}  -- 契約リスクマップ生成
    GET  /api/riskmap/contract/{contract_no}  -- 契約リスクマップ取得
"""

import base64
import os
import sqlite3
from typing import Optional

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
    """riskmap_pdfsテーブルが存在しない場合は作成する"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS riskmap_pdfs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            type         TEXT NOT NULL,
            ref_id       TEXT NOT NULL,
            pdf_data     BLOB NOT NULL,
            generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(type, ref_id)
        )
    """)
    conn.commit()

# ── 顧客リスクマップ ──────────────────────────────────────────────────────────


@router.post("/riskmap/customer/{customer_id}")
def post_customer_riskmap(
    customer_id: str,
    payload: dict = Depends(_verify_token),
):
    """
    顧客IDから加入種目を集計してリスクマップPDFを生成し、
    DBに保存してbase64エンコード済みPDFを返す。
    """
    conn = _get_db()
    try:
        _ensure_table(conn)

        # 顧客情報を取得（last_name + first_name を結合して顧客名とする）
        customer = conn.execute("""
            SELECT last_name, first_name, group_code
            FROM customers
            WHERE customer_id = ?
        """, (customer_id,)).fetchone()

        if not customer:
            raise HTTPException(status_code=404, detail="顧客が見つかりません")

        customer_name  = f"{customer['last_name']} {customer['first_name']}"
        group_code     = customer["group_code"]

        # アクセス制御：代理店ユーザーは参照グループが一致する顧客のみ
        user_type = payload.get("user_type", "agency")
        if user_type != "staff":
            user_grp = payload.get("group_code")
            if user_grp and group_code != user_grp:
                raise HTTPException(status_code=403, detail="参照権限がありません")

        # 加入種目を集計（有効契約のみ、policy_typeは日本語名で格納済み）
        rows = conn.execute("""
            SELECT DISTINCT policy_type
            FROM contracts
            WHERE linked_customer_id = ?
              AND (status IS NULL OR status != '失効')
        """, (customer_id,)).fetchall()

        covered_types = [r["policy_type"] for r in rows if r["policy_type"]]

        # PDF生成
        from reports.generate_riskmap import generate_customer_riskmap
        pdf_bytes = generate_customer_riskmap(customer_name, covered_types)

        # DBに保存（既存は上書き）
        conn.execute("""
            INSERT INTO riskmap_pdfs (type, ref_id, pdf_data, generated_at)
            VALUES ('customer', ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(type, ref_id) DO UPDATE SET
                pdf_data     = excluded.pdf_data,
                generated_at = excluded.generated_at
        """, (customer_id, pdf_bytes))
        conn.commit()

        return {
            "pdf_data": base64.b64encode(pdf_bytes).decode("utf-8"),
            "filename": f"riskmap_customer_{customer_id}.pdf",
        }
    finally:
        conn.close()


@router.get("/riskmap/customer/{customer_id}")
def get_customer_riskmap(
    customer_id: str,
    payload: dict = Depends(_verify_token),
):
    """保存済み顧客リスクマップPDFをbase64で返す（未生成時は404）"""
    conn = _get_db()
    try:
        _ensure_table(conn)

        row = conn.execute("""
            SELECT pdf_data FROM riskmap_pdfs
            WHERE type = 'customer' AND ref_id = ?
        """, (customer_id,)).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="リスクマップが未生成です")

        pdf_bytes = bytes(row["pdf_data"])
        return {
            "pdf_data": base64.b64encode(pdf_bytes).decode("utf-8"),
            "filename": f"riskmap_customer_{customer_id}.pdf",
        }
    finally:
        conn.close()

# ── 契約リスクマップ ──────────────────────────────────────────────────────────


@router.post("/riskmap/contract/{contract_no}")
def post_contract_riskmap(
    contract_no: str,
    payload: dict = Depends(_verify_token),
):
    """
    証券番号からcontract_detailsを取得してリスクマップPDFを生成し、
    DBに保存してbase64エンコード済みPDFを返す。
    """
    conn = _get_db()
    try:
        _ensure_table(conn)

        # 契約情報を取得
        contract = conn.execute("""
            SELECT c.contract_no, c.customer_name, c.policy_type,
                   c.agency_code, ag.group_code, ag.buka_code
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

        # 契約詳細を取得（contract_detailsはcontract_idで紐づく）
        detail_row = conn.execute("""
            SELECT cd.* FROM contract_details cd
            JOIN contracts c ON c.id = cd.contract_id
            WHERE c.contract_no = ?
        """, (contract_no,)).fetchone()
        detail = dict(detail_row) if detail_row else {}

        customer_name = contract["customer_name"]
        policy_type   = contract["policy_type"]

        # PDF生成
        from reports.generate_riskmap import generate_contract_riskmap
        pdf_bytes = generate_contract_riskmap(customer_name, contract_no, policy_type, detail)

        # DBに保存（既存は上書き）
        conn.execute("""
            INSERT INTO riskmap_pdfs (type, ref_id, pdf_data, generated_at)
            VALUES ('contract', ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(type, ref_id) DO UPDATE SET
                pdf_data     = excluded.pdf_data,
                generated_at = excluded.generated_at
        """, (contract_no, pdf_bytes))
        conn.commit()

        return {
            "pdf_data": base64.b64encode(pdf_bytes).decode("utf-8"),
            "filename": f"riskmap_{contract_no}.pdf",
        }
    finally:
        conn.close()


@router.get("/riskmap/contract/{contract_no}")
def get_contract_riskmap(
    contract_no: str,
    payload: dict = Depends(_verify_token),
):
    """保存済み契約リスクマップPDFをbase64で返す（未生成時は404）"""
    conn = _get_db()
    try:
        _ensure_table(conn)

        row = conn.execute("""
            SELECT pdf_data FROM riskmap_pdfs
            WHERE type = 'contract' AND ref_id = ?
        """, (contract_no,)).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="リスクマップが未生成です")

        pdf_bytes = bytes(row["pdf_data"])
        return {
            "pdf_data": base64.b64encode(pdf_bytes).decode("utf-8"),
            "filename": f"riskmap_{contract_no}.pdf",
        }
    finally:
        conn.close()
