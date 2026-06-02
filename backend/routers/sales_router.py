"""
成績管理APIルーター
代理店ユーザー専用。社員ユーザーからのアクセスは403を返す。
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional
from jose import jwt, JWTError
import sqlite3
import datetime
import os

router = APIRouter()

# JWT設定（main.pyと同一の値。本番環境では環境変数から取得すること）
_SECRET_KEY = "CHANGE_THIS_SECRET_IN_PRODUCTION"
_ALGORITHM  = "HS256"

# データベースファイルのパス
_DB_PATH = os.path.join(os.path.dirname(__file__), "../../db/users.sqlite")

# 保険種目コード一覧
POLICY_TYPES = ["AUTO", "FIRE", "INJURY", "JIBAI", "LIABILITY", "CYBER", "INCOME"]


def _get_db() -> sqlite3.Connection:
    """SQLite接続を取得する（check_same_thread=Falseでスレッド間共有を許可）"""
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


def _require_agency(payload: dict) -> dict:
    """代理店ユーザーのみ許可。社員の場合は403を返す"""
    if payload.get("user_type") == "staff":
        raise HTTPException(status_code=403, detail="代理店ユーザー専用の機能です")
    return payload


def _ensure_sales_targets_table(conn: sqlite3.Connection):
    """sales_targetsテーブルが存在しない場合は自動作成する"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales_targets (
            id            INTEGER  PRIMARY KEY AUTOINCREMENT,
            agency_code   TEXT     NOT NULL,
            staff_code    TEXT     NOT NULL,
            fiscal_year   INTEGER  NOT NULL,
            month         INTEGER  NOT NULL,
            policy_type   TEXT     NOT NULL,
            target_amount INTEGER  NOT NULL DEFAULT 0,
            updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agency_code, staff_code, fiscal_year, month, policy_type)
        )
    """)
    conn.commit()


# ─── Pydanticモデル定義 ──────────────────────────────────────────────

class TargetItem(BaseModel):
    """目標金額の1レコード"""
    month: int
    policy_type: str
    target_amount: int


class SaveTargetsRequest(BaseModel):
    """目標金額一括保存リクエスト"""
    agency_code: str
    staff_code: str
    fiscal_year: int
    targets: List[TargetItem]
    token: str  # フロント互換用（認証はAuthorizationヘッダーを使用）


# ─── エンドポイント ──────────────────────────────────────────────────

@router.get("/sales/staff-list")
def get_staff_list(
    agency_code: str,
    payload: dict = Depends(_verify_token),
):
    """
    担当者一覧を返す（代理店ユーザー専用）

    usersテーブルからagency_code条件でログインIDと氏名を取得し、
    末尾に「代理店合計（ALL）」を追加して返す。
    """
    _require_agency(payload)

    # 自分の代理店コード以外は参照不可
    if agency_code != payload.get("agency_code"):
        raise HTTPException(status_code=403, detail="他代理店のデータにはアクセスできません")

    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT login_id, name FROM users WHERE agency_code = ? AND is_active = 1 ORDER BY id",
            (agency_code,)
        ).fetchall()
        result = [{"staff_code": r["login_id"], "name": r["name"]} for r in rows]
        # 代理店合計を末尾に追加
        result.append({"staff_code": "ALL", "name": "代理店合計"})
        return result
    finally:
        conn.close()


@router.get("/sales/actual")
def get_actual(
    agency_code: str,
    staff_code: str,
    fiscal_year: int,
    payload: dict = Depends(_verify_token),
):
    """
    月別×種目別の実績保険料を集計して返す（代理店ユーザー専用）

    contractsテーブルのannual_premiumをexpiry_dateの年度で集計する。
    staff_code='ALL'の場合は代理店全体を集計する。
    policy_typeが英語コード（AUTO等）以外のデータは集計対象外となり全0を返す。
    """
    _require_agency(payload)

    if agency_code != payload.get("agency_code"):
        raise HTTPException(status_code=403, detail="他代理店のデータにはアクセスできません")

    # 年度範囲（例: 2026年度 = 2026-04-01 〜 2027-03-31）
    date_from = f"{fiscal_year}-04-01"
    date_to   = f"{fiscal_year + 1}-03-31"

    conn = _get_db()
    try:
        # 月別×種目別に集計
        if staff_code == "ALL":
            rows = conn.execute("""
                SELECT
                    CAST(strftime('%m', expiry_date) AS INTEGER) AS month,
                    policy_type,
                    SUM(annual_premium) AS total
                FROM contracts
                WHERE agency_code = ?
                  AND expiry_date >= ?
                  AND expiry_date <= ?
                  AND annual_premium IS NOT NULL
                GROUP BY month, policy_type
            """, (agency_code, date_from, date_to)).fetchall()
        else:
            rows = conn.execute("""
                SELECT
                    CAST(strftime('%m', expiry_date) AS INTEGER) AS month,
                    policy_type,
                    SUM(annual_premium) AS total
                FROM contracts
                WHERE agency_code = ?
                  AND staff_code = ?
                  AND expiry_date >= ?
                  AND expiry_date <= ?
                  AND annual_premium IS NOT NULL
                GROUP BY month, policy_type
            """, (agency_code, staff_code, date_from, date_to)).fetchall()

        # 結果を種目×月の辞書に変換
        data: dict = {pt: {} for pt in POLICY_TYPES}
        data["TOTAL"] = {}

        for r in rows:
            month = str(r["month"])
            pt    = r["policy_type"] if r["policy_type"] in POLICY_TYPES else None
            if pt:
                data[pt][month] = data[pt].get(month, 0) + (r["total"] or 0)
            # TOTAL は全種目（policy_type不問）の合算
            data["TOTAL"][month] = data["TOTAL"].get(month, 0) + (r["total"] or 0)

        return {
            "fiscal_year": fiscal_year,
            "staff_code":  staff_code,
            "data":        data,
        }
    finally:
        conn.close()


@router.get("/sales/targets")
def get_targets(
    agency_code: str,
    staff_code: str,
    fiscal_year: int,
    payload: dict = Depends(_verify_token),
):
    """
    月別×種目別の目標金額を返す（代理店ユーザー専用）

    sales_targetsテーブルが存在しない場合は自動作成してから参照する。
    actualと同じ構造（data.{POLICY_TYPE}.{month}）で返す。
    """
    _require_agency(payload)

    if agency_code != payload.get("agency_code"):
        raise HTTPException(status_code=403, detail="他代理店のデータにはアクセスできません")

    conn = _get_db()
    try:
        _ensure_sales_targets_table(conn)

        rows = conn.execute("""
            SELECT month, policy_type, target_amount
            FROM sales_targets
            WHERE agency_code = ? AND staff_code = ? AND fiscal_year = ?
        """, (agency_code, staff_code, fiscal_year)).fetchall()

        data: dict = {pt: {} for pt in POLICY_TYPES}
        data["TOTAL"] = {}

        for r in rows:
            month = str(r["month"])
            pt    = r["policy_type"]
            if pt in POLICY_TYPES:
                data[pt][month] = r["target_amount"]
                data["TOTAL"][month] = data["TOTAL"].get(month, 0) + r["target_amount"]

        return {
            "fiscal_year": fiscal_year,
            "staff_code":  staff_code,
            "data":        data,
        }
    finally:
        conn.close()


@router.post("/sales/targets")
def save_targets(
    request: SaveTargetsRequest,
    payload: dict = Depends(_verify_token),
):
    """
    月別×種目別の目標金額を一括保存する（代理店管理者専用）

    既存レコードはUPSERT（INSERT OR REPLACE）で上書き。
    updated_atを現在時刻で更新する。
    """
    _require_agency(payload)

    # 管理者（role_id=1）のみ保存可能
    if payload.get("role_id") != 1:
        raise HTTPException(status_code=403, detail="管理者権限が必要です")

    if request.agency_code != payload.get("agency_code"):
        raise HTTPException(status_code=403, detail="他代理店のデータにはアクセスできません")

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_db()
    try:
        _ensure_sales_targets_table(conn)

        saved = 0
        for item in request.targets:
            conn.execute("""
                INSERT OR REPLACE INTO sales_targets
                    (agency_code, staff_code, fiscal_year, month, policy_type, target_amount, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                request.agency_code,
                request.staff_code,
                request.fiscal_year,
                item.month,
                item.policy_type,
                item.target_amount,
                now,
            ))
            saved += 1

        conn.commit()
        return {"status": "ok", "saved": saved}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
