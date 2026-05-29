from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError
from typing import Optional
import bcrypt
import sqlite3
import datetime
import os

app = FastAPI(title="AX損害保険 代理店システムAPI")

# フロントエンドからのリクエストを許可するCORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT設定（本番環境では環境変数から取得すること）
SECRET_KEY = "CHANGE_THIS_SECRET_IN_PRODUCTION"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60

# データベースファイルのパス
DB_PATH = os.path.join(os.path.dirname(__file__), "../db/users.sqlite")


class LoginRequest(BaseModel):
    """ログインリクエストのスキーマ"""
    agency_code: str  # 代理店コード
    login_id: str     # ログインID
    password: str     # パスワード


def get_db_connection() -> sqlite3.Connection:
    """SQLite接続を取得する"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def find_user(agency_code: str, login_id: str):
    """代理店コードとログインIDでユーザーを検索する。存在しない場合はNoneを返す"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE agency_code = ? AND login_id = ?",
            (agency_code, login_id),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def create_access_token(data: dict) -> str:
    """JWTアクセストークンを生成する"""
    payload = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload["exp"] = expire
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(authorization: str = Header(default=None)) -> dict:
    """AuthorizationヘッダーのBearerトークンを検証してペイロードを返す"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="認証トークンがありません")
    token = authorization[len("Bearer "):]
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="無効または期限切れのトークンです")


@app.post("/api/login")
def login(request: LoginRequest):
    """
    ログイン認証エンドポイント

    認証成功時: JWTトークンとユーザー名を返す
    認証失敗時: 401エラーを返す
    """
    # 代理店コードとログインIDでユーザーを検索する
    user = find_user(request.agency_code, request.login_id)

    # ユーザーが存在しない、またはパスワードが不一致の場合は認証失敗
    if not user or not bcrypt.checkpw(request.password.encode(), user["password_hash"].encode()):
        raise HTTPException(
            status_code=401,
            detail="代理店コード、ログインID、またはパスワードが正しくありません",
        )

    # 認証成功：JWTトークンを生成して返す
    token = create_access_token({
        "agency_code": user["agency_code"],
        "login_id":    user["login_id"],
        "name":        user["name"],
    })

    return {
        "access_token": token,
        "token_type":   "bearer",
        "name":         user["name"],
    }


@app.get("/api/maturity")
def get_maturity(
    payload:           dict           = Depends(verify_token),
    date_from:         Optional[str]  = Query(default=None, description="満期年月日FROM (YYYY-MM-DD)"),
    date_to:           Optional[str]  = Query(default=None, description="満期年月日TO (YYYY-MM-DD)"),
    staff_code:        Optional[str]  = Query(default=None),
    policy_type:       Optional[str]  = Query(default=None),
    renewal_status:    Optional[str]  = Query(default=None),
    followcall_status: Optional[str]  = Query(default=None),
):
    """
    満期管理エンドポイント

    JWTの代理店コードをもとに満期3カ月前〜翌3カ月の契約を取得する。
    検索パラメータで絞り込みが可能。
    """
    agency_code = payload["agency_code"]
    today       = datetime.date.today()

    # デフォルト検索範囲：満期3カ月前〜翌3カ月
    if date_from is None:
        date_from = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        date_from = (date_from.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        date_from = (date_from.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        date_from = date_from.isoformat()
    if date_to is None:
        m = today.month + 3
        y = today.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        date_to = datetime.date(y, m, 28).isoformat()

    sql = """
        SELECT
            c.id, c.agency_code, c.contract_no, c.customer_name,
            c.renewal_month, c.status,
            c.customer_id, c.policy_number, c.policy_type,
            c.expiry_date, c.annual_premium,
            c.staff_code, c.contact_method, c.contact_info, c.memo,
            c.has_accident, c.has_change,
            c.followcall_status, c.renewal_status,
            c.renewed_policy_number, c.renewed_premium,
            c.upsell_status, c.lapse_status,
            mn.notice_date, mn.notice_type
        FROM contracts c
        LEFT JOIN maturity_notices mn ON mn.contract_id = c.id
        WHERE c.agency_code = ?
          AND c.expiry_date IS NOT NULL
          AND c.expiry_date BETWEEN ? AND ?
    """
    params = [agency_code, date_from, date_to]

    if staff_code:
        sql += " AND c.staff_code = ?"
        params.append(staff_code)
    if policy_type:
        sql += " AND c.policy_type = ?"
        params.append(policy_type)
    if renewal_status:
        sql += " AND c.renewal_status = ?"
        params.append(renewal_status)
    if followcall_status:
        sql += " AND c.followcall_status = ?"
        params.append(followcall_status)

    sql += " ORDER BY c.expiry_date"

    conn = get_db_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        contracts = [dict(r) for r in rows]
        return {"contracts": contracts, "total": len(contracts)}
    finally:
        conn.close()


@app.get("/api/dashboard")
def get_dashboard(payload: dict = Depends(verify_token)):
    """
    ダッシュボードデータを返す

    JWTトークンから代理店コードを取得し、
    今月・翌月の更改件数をステータス別に集計して返す
    """
    agency_code = payload["agency_code"]
    today       = datetime.date.today()
    cur_month   = today.strftime("%Y-%m")

    # 翌月を算出する（12月の場合は翌年1月になる）
    if today.month == 12:
        nxt_month = f"{today.year + 1}-01"
    else:
        nxt_month = f"{today.year}-{today.month + 1:02d}"

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        def aggregate(month: str) -> dict:
            """指定月のステータス別件数を集計して返す"""
            cur.execute("""
                SELECT status, COUNT(*) AS cnt
                FROM contracts
                WHERE agency_code = ? AND renewal_month = ?
                GROUP BY status
            """, (agency_code, month))
            rows  = {r["status"]: r["cnt"] for r in cur.fetchall()}
            done  = rows.get("completed", 0)
            pend  = rows.get("pending",   0)
            total = done + pend
            return {
                "month":     month,
                "completed": done,
                "pending":   pend,
                "total":     total,
                "rate":      round(done / total * 100, 1) if total > 0 else 0,
            }

        return {
            "agency_code":   agency_code,
            "login_id":      payload.get("login_id", ""),
            "name":          payload.get("name", ""),
            "current_month": aggregate(cur_month),
            "next_month":    aggregate(nxt_month),
        }
    finally:
        conn.close()
