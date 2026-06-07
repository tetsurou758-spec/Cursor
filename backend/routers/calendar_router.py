"""
ダッシュボードカレンダーAPIルーター

エンドポイント:
    GET /api/dashboard/calendar  -- 今月・翌月のカレンダーイベント取得
"""

import datetime
import os
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from jose import jwt, JWTError

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


@router.get("/dashboard/calendar")
def get_calendar_events(
    year:  int = Query(default=None),
    month: int = Query(default=None),
    payload: dict = Depends(_verify_token),
):
    """
    指定年月のカレンダーイベントを返す。
    - 満期イベント: expiry_date の14日前を表示日とする
    - TODOイベント: due_date をそのまま表示日とする
    対象はベース月から3ヶ月分（先月・今月・翌月）を一度に返す。
    フロントは先月をベース月としてリクエストする。
    """
    # デフォルトは先月（先月起点で3ヶ月分）
    today = datetime.date.today()
    base_year  = year  if year  else today.year
    base_month = month if month else today.month

    def _add_months(y: int, m: int, delta: int):
        """年月に月数を加算してタプルで返す"""
        total = (y - 1) * 12 + m + delta
        return ((total - 1) // 12 + 1, (total - 1) % 12 + 1)

    def _month_start(y: int, m: int):
        return datetime.date(y, m, 1)

    def _month_end(y: int, m: int):
        """翌月1日の前日＝当月末日"""
        ny, nm = _add_months(y, m, 1)
        return datetime.date(ny, nm, 1) - datetime.timedelta(days=1)

    # 3ヶ月分の範囲（先月〜翌々月末 = ベース月から3ヶ月）
    range_start = _month_start(base_year, base_month)
    range_end   = _month_end(*_add_months(base_year, base_month, 2))

    # 満期イベントは expiry_date - 14日 が対象範囲内のもの
    # つまり expiry_date が (range_start + 14日) 〜 (range_end + 14日) の範囲
    expiry_from = range_start + datetime.timedelta(days=14)
    expiry_to   = range_end   + datetime.timedelta(days=14)

    user_type   = payload.get("user_type", "agency")
    agency_code = payload.get("agency_code", "")
    login_id    = payload.get("login_id", "")   # 代理店担当者ID
    staff_code  = payload.get("staff_code", "")  # 社員コード

    conn = _get_db()
    try:
        events: dict = {}  # key: "YYYY-MM-DD", value: {maturity:[], todo:[]}

        def _ensure_day(d: str):
            if d not in events:
                events[d] = {"maturity": [], "todo": []}

        # ── 満期イベント ──────────────────────────────────────────
        if user_type == "agency":
            # 代理店ユーザー: 自代理店・担当者コードで絞り込み
            maturity_rows = conn.execute("""
                SELECT contract_no, customer_name, policy_type, expiry_date, staff_code
                FROM contracts
                WHERE agency_code = ?
                  AND expiry_date BETWEEN ? AND ?
                  AND (status IS NULL OR status NOT IN ('失効','更改済'))
                ORDER BY expiry_date
            """, (agency_code, expiry_from.isoformat(), expiry_to.isoformat())).fetchall()
        else:
            # 社員ユーザー: buka_code管轄代理店全体
            buka_code = payload.get("buka_code", "")
            role_id   = payload.get("role_id", 0)
            if role_id == 1:
                # システム管理者は全代理店
                maturity_rows = conn.execute("""
                    SELECT contract_no, customer_name, policy_type, expiry_date, staff_code
                    FROM contracts
                    WHERE expiry_date BETWEEN ? AND ?
                      AND (status IS NULL OR status NOT IN ('失効','更改済'))
                    ORDER BY expiry_date
                """, (expiry_from.isoformat(), expiry_to.isoformat())).fetchall()
            else:
                maturity_rows = conn.execute("""
                    SELECT c.contract_no, c.customer_name, c.policy_type, c.expiry_date, c.staff_code
                    FROM contracts c
                    JOIN agencies a ON c.agency_code = a.agency_code
                    WHERE a.buka_code = ?
                      AND c.expiry_date BETWEEN ? AND ?
                      AND (c.status IS NULL OR c.status NOT IN ('失効','更改済'))
                    ORDER BY c.expiry_date
                """, (buka_code, expiry_from.isoformat(), expiry_to.isoformat())).fetchall()

        for row in maturity_rows:
            try:
                expiry_dt  = datetime.date.fromisoformat(row["expiry_date"])
                notice_dt  = expiry_dt - datetime.timedelta(days=14)
                notice_key = notice_dt.isoformat()
                # カレンダー表示範囲内のみ追加
                if range_start <= notice_dt <= range_end:
                    _ensure_day(notice_key)
                    events[notice_key]["maturity"].append({
                        "contract_no":   row["contract_no"],
                        "customer_name": row["customer_name"] or "",
                        "policy_type":   row["policy_type"]   or "",
                        "expiry_date":   row["expiry_date"],
                        "staff_code":    row["staff_code"]     or "",
                    })
            except Exception:
                continue

        # ── TODOイベント ──────────────────────────────────────────
        if user_type == "agency":
            todo_rows = conn.execute("""
                SELECT id, title, due_date, status, staff_code
                FROM todos
                WHERE agency_code = ?
                  AND due_date BETWEEN ? AND ?
                  AND status != '完了'
                ORDER BY due_date
            """, (agency_code, range_start.isoformat(), range_end.isoformat())).fetchall()
        else:
            buka_code = payload.get("buka_code", "")
            role_id   = payload.get("role_id", 0)
            if role_id == 1:
                todo_rows = conn.execute("""
                    SELECT id, title, due_date, status, staff_code
                    FROM todos
                    WHERE due_date BETWEEN ? AND ?
                      AND status != '完了'
                    ORDER BY due_date
                """, (range_start.isoformat(), range_end.isoformat())).fetchall()
            else:
                todo_rows = conn.execute("""
                    SELECT t.id, t.title, t.due_date, t.status, t.staff_code
                    FROM todos t
                    JOIN agencies a ON t.agency_code = a.agency_code
                    WHERE a.buka_code = ?
                      AND t.due_date BETWEEN ? AND ?
                      AND t.status != '完了'
                    ORDER BY t.due_date
                """, (buka_code, range_start.isoformat(), range_end.isoformat())).fetchall()

        for row in todo_rows:
            try:
                due_key = row["due_date"]
                if due_key:
                    _ensure_day(due_key)
                    events[due_key]["todo"].append({
                        "id":         row["id"],
                        "title":      row["title"] or "",
                        "due_date":   row["due_date"],
                        "status":     row["status"] or "",
                        "staff_code": row["staff_code"] or "",
                    })
            except Exception:
                continue

        return {
            "base_year":  base_year,
            "base_month": base_month,
            "events":     events,
        }

    finally:
        conn.close()
