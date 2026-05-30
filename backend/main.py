from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError
from typing import Optional, List
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

# 社員ロール別の利用可能機能リスト
STAFF_PERMISSIONS = {
    1: ["PAYMENT_VIEW", "CUSTOMER_EDIT", "MATURITY_VIEW", "REPORT_VIEW", "USER_ADMIN"],
    2: ["CUSTOMER_EDIT", "MATURITY_VIEW", "REPORT_VIEW", "USER_ADMIN"],
    3: [],
}


class LoginRequest(BaseModel):
    """代理店ログインリクエストのスキーマ"""
    agency_code: str
    login_id: str
    password: str


class StaffLoginRequest(BaseModel):
    """社員ログインリクエストのスキーマ"""
    staff_code: str
    password: str


class UserCreateRequest(BaseModel):
    """ユーザー登録リクエストのスキーマ"""
    login_id: str
    password: str
    name: str
    role_id: int
    is_active: int = 1


class UserUpdateRequest(BaseModel):
    """ユーザー更新リクエストのスキーマ"""
    name: Optional[str] = None
    password: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[int] = None


def get_db_connection() -> sqlite3.Connection:
    """SQLite接続を取得する（check_same_thread=Falseでスレッド間共有を許可）"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def find_user(agency_code: str, login_id: str):
    """代理店コードとログインIDでユーザーを検索し、代理店・ロール情報もJOINして返す"""
    conn = get_db_connection()
    try:
        return conn.execute("""
            SELECT u.*, ag.group_code, ag.agency_name,
                   r.role_name
            FROM users u
            LEFT JOIN agencies ag ON u.agency_id = ag.agency_id
            LEFT JOIN roles r ON u.role_id = r.role_id
            WHERE u.agency_code = ? AND u.login_id = ? AND u.is_active = 1
        """, (agency_code, login_id)).fetchone()
    finally:
        conn.close()


def find_staff_user(staff_code: str):
    """社員番号で社員ユーザーを検索し、ロール情報もJOINして返す"""
    conn = get_db_connection()
    try:
        return conn.execute("""
            SELECT su.*, sr.role_name
            FROM staff_users su
            LEFT JOIN staff_roles sr ON su.role_id = sr.role_id
            WHERE su.staff_code = ? AND su.is_active = 1
        """, (staff_code,)).fetchone()
    finally:
        conn.close()


def get_user_permissions(role_id: int) -> List[str]:
    """ロールIDから利用可能なfeature_codeリストを取得する"""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT feature_code FROM role_permissions WHERE role_id = ?", (role_id,)
        ).fetchall()
        return [r["feature_code"] for r in rows]
    finally:
        conn.close()


def get_staff_managed_agencies(role_id: int, buka_code: str) -> List[str]:
    """社員ロールに応じた管轄代理店コードリストを返す"""
    conn = get_db_connection()
    try:
        if role_id == 1:
            rows = conn.execute("SELECT agency_code FROM agencies").fetchall()
        else:
            rows = conn.execute(
                "SELECT agency_code FROM agencies WHERE buka_code = ?", (buka_code,)
            ).fetchall()
        return [r["agency_code"] for r in rows]
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


def require_admin(payload: dict = Depends(verify_token)) -> dict:
    """管理者ロール（role_id=1）のみアクセスを許可する"""
    if payload.get("role_id") != 1:
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return payload


@app.post("/api/login")
def login(request: LoginRequest):
    """
    代理店ログイン認証エンドポイント

    認証成功時: JWTトークン・ユーザー情報・利用可能機能リストを返す
    JWTにはuser_type:agency・role_id・agency_id・group_codeを含める
    """
    user = find_user(request.agency_code, request.login_id)

    if not user or not bcrypt.checkpw(request.password.encode(), user["password_hash"].encode()):
        raise HTTPException(
            status_code=401,
            detail="代理店コード、ログインID、またはパスワードが正しくありません",
        )

    role_id    = user["role_id"]
    agency_id  = user["agency_id"]
    group_code = user["group_code"]

    token = create_access_token({
        "user_type":   "agency",
        "agency_code": user["agency_code"],
        "login_id":    user["login_id"],
        "name":        user["name"],
        "role_id":     role_id,
        "agency_id":   agency_id,
        "group_code":  group_code,
    })

    permissions = get_user_permissions(role_id)

    return {
        "access_token": token,
        "token_type":   "bearer",
        "name":         user["name"],
        "role_id":      role_id,
        "role_name":    user["role_name"],
        "agency_id":    agency_id,
        "group_code":   group_code,
        "permissions":  permissions,
    }


@app.post("/api/staff/login")
def staff_login(request: StaffLoginRequest):
    """
    社員ログイン認証エンドポイント

    社員番号+パスワードで認証。
    JWTにはuser_type:staff・staff_id・staff_code・buka_code・role_idを含める。
    認証成功時にrole情報・管轄代理店リスト・権限リストも返す。
    """
    staff = find_staff_user(request.staff_code)

    if not staff or not bcrypt.checkpw(request.password.encode(), staff["password"].encode()):
        raise HTTPException(
            status_code=401,
            detail="社員番号またはパスワードが正しくありません",
        )

    role_id   = staff["role_id"]
    buka_code = staff["buka_code"]

    token = create_access_token({
        "user_type":  "staff",
        "staff_id":   staff["staff_id"],
        "staff_code": staff["staff_code"],
        "name":       staff["name"],
        "buka_code":  buka_code,
        "role_id":    role_id,
    })

    permissions      = STAFF_PERMISSIONS.get(role_id, [])
    managed_agencies = get_staff_managed_agencies(role_id, buka_code)

    return {
        "access_token":     token,
        "token_type":       "bearer",
        "staff_code":       staff["staff_code"],
        "name":             staff["name"],
        "role_id":          role_id,
        "role_name":        staff["role_name"],
        "buka_code":        buka_code,
        "permissions":      permissions,
        "managed_agencies": managed_agencies,
    }


@app.get("/api/permissions")
def get_permissions(payload: dict = Depends(verify_token)):
    """JWTのrole_idから利用可能なfeature_codeリストとロール名を返す"""
    role_id   = payload.get("role_id")
    user_type = payload.get("user_type", "agency")

    if role_id is None:
        raise HTTPException(status_code=400, detail="トークンにロール情報がありません")

    if user_type == "staff":
        conn = get_db_connection()
        try:
            role = conn.execute(
                "SELECT role_name FROM staff_roles WHERE role_id = ?", (role_id,)
            ).fetchone()
            return {
                "role_id":     role_id,
                "role_name":   role["role_name"] if role else "",
                "permissions": STAFF_PERMISSIONS.get(role_id, []),
            }
        finally:
            conn.close()
    else:
        conn = get_db_connection()
        try:
            role = conn.execute(
                "SELECT role_name FROM roles WHERE role_id = ?", (role_id,)
            ).fetchone()
            permissions = get_user_permissions(role_id)
            return {
                "role_id":     role_id,
                "role_name":   role["role_name"] if role else "",
                "permissions": permissions,
            }
        finally:
            conn.close()


@app.get("/api/users")
def get_users(payload: dict = Depends(require_admin)):
    """管理者のみ：自代理店のユーザー一覧をロール情報とともに返す"""
    agency_id = payload.get("agency_id")
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT u.id, u.login_id, u.name, u.is_active, u.created_at,
                   r.role_id, r.role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.role_id
            WHERE u.agency_id = ?
            ORDER BY u.id
        """, (agency_id,)).fetchall()
        return {"users": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.post("/api/users", status_code=201)
def create_user(request: UserCreateRequest, payload: dict = Depends(require_admin)):
    """管理者のみ：自代理店に新規ユーザーを登録する"""
    agency_id   = payload.get("agency_id")
    agency_code = payload.get("agency_code")
    hashed      = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO users (agency_code, agency_id, role_id, login_id, password_hash, name, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (agency_code, agency_id, request.role_id, request.login_id,
              hashed, request.name, request.is_active))
        conn.commit()
        return {"message": "ユーザーを登録しました", "login_id": request.login_id}
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="そのログインIDは既に使用されています")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.put("/api/users/{user_id}")
def update_user(user_id: int, request: UserUpdateRequest,
                payload: dict = Depends(require_admin)):
    """管理者のみ：自代理店のユーザー情報・ロールを変更する"""
    agency_id = payload.get("agency_id")
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE id = ? AND agency_id = ?", (user_id, agency_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

        fields, params = [], []
        if request.name is not None:
            fields.append("name = ?"); params.append(request.name)
        if request.password is not None:
            fields.append("password_hash = ?")
            params.append(bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode())
        if request.role_id is not None:
            fields.append("role_id = ?"); params.append(request.role_id)
        if request.is_active is not None:
            fields.append("is_active = ?"); params.append(request.is_active)

        if not fields:
            raise HTTPException(status_code=400, detail="更新する項目がありません")

        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
        return {"message": "ユーザー情報を更新しました"}
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, payload: dict = Depends(require_admin)):
    """管理者のみ：ユーザーを論理削除する（is_active=0）"""
    agency_id = payload.get("agency_id")
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE id = ? AND agency_id = ?", (user_id, agency_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
        conn.commit()
        return {"message": "ユーザーを無効化しました"}
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.get("/api/role-matrix")
def get_role_matrix(payload: dict = Depends(require_admin)):
    """管理者のみ：ロール×機能の権限マトリクスを返す"""
    conn = get_db_connection()
    try:
        roles    = [dict(r) for r in conn.execute(
            "SELECT role_id, role_name FROM roles ORDER BY role_id"
        ).fetchall()]
        features = [dict(f) for f in conn.execute(
            "SELECT feature_code, feature_name FROM features"
        ).fetchall()]
        perms    = conn.execute(
            "SELECT role_id, feature_code FROM role_permissions"
        ).fetchall()
        perm_map: dict = {}
        for p in perms:
            perm_map.setdefault(p["role_id"], []).append(p["feature_code"])
        return {"roles": roles, "features": features, "permissions": perm_map}
    finally:
        conn.close()


@app.get("/api/dashboard")
def get_dashboard(payload: dict = Depends(verify_token)):
    """
    ダッシュボードデータを返す

    user_type:agency → 自代理店の契約を集計
    user_type:staff  → role_id=1は全代理店、role_id=2,3は同一部課の代理店を集計
    """
    today     = datetime.date.today()
    cur_month = today.strftime("%Y-%m")
    nxt_month = f"{today.year + 1}-01" if today.month == 12 else f"{today.year}-{today.month + 1:02d}"

    user_type = payload.get("user_type", "agency")
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        if user_type == "staff":
            role_id   = payload.get("role_id")
            buka_code = payload.get("buka_code")

            # 管轄代理店コードリストを取得する
            if role_id == 1:
                agency_codes = [r["agency_code"] for r in cur.execute(
                    "SELECT agency_code FROM agencies"
                ).fetchall()]
            else:
                agency_codes = [r["agency_code"] for r in cur.execute(
                    "SELECT agency_code FROM agencies WHERE buka_code = ?", (buka_code,)
                ).fetchall()]

            def aggregate_staff(month: str) -> dict:
                """管轄代理店全体の当月/翌月更改ステータス別件数を集計して返す"""
                if not agency_codes:
                    return {"month": month, "completed": 0, "pending": 0, "total": 0, "rate": 0}
                placeholders = ",".join("?" * len(agency_codes))
                cur.execute(f"""
                    SELECT renewal_status, COUNT(*) AS cnt
                    FROM contracts
                    WHERE agency_code IN ({placeholders})
                      AND strftime('%Y-%m', expiry_date) = ?
                    GROUP BY renewal_status
                """, (*agency_codes, month))
                rows  = {r["renewal_status"]: r["cnt"] for r in cur.fetchall()}
                done  = rows.get("更改済", 0)
                pend  = rows.get("未対応", 0) + rows.get("対応中", 0)
                total = done + pend
                return {
                    "month":     month,
                    "completed": done,
                    "pending":   pend,
                    "total":     total,
                    "rate":      round(done / total * 100, 1) if total > 0 else 0,
                }

            return {
                "user_type":     "staff",
                "staff_code":    payload.get("staff_code", ""),
                "name":          payload.get("name", ""),
                "buka_code":     buka_code,
                "agency_count":  len(agency_codes),
                "current_month": aggregate_staff(cur_month),
                "next_month":    aggregate_staff(nxt_month),
            }

        else:
            # 代理店ユーザー（既存ロジック）
            agency_code = payload["agency_code"]

            def aggregate(month: str) -> dict:
                """自代理店の当月/翌月更改ステータス別件数を集計して返す"""
                cur.execute("""
                    SELECT renewal_status, COUNT(*) AS cnt
                    FROM contracts
                    WHERE agency_code = ?
                      AND strftime('%Y-%m', expiry_date) = ?
                    GROUP BY renewal_status
                """, (agency_code, month))
                rows  = {r["renewal_status"]: r["cnt"] for r in cur.fetchall()}
                done  = rows.get("更改済", 0)
                pend  = rows.get("未対応", 0) + rows.get("対応中", 0)
                total = done + pend
                return {
                    "month":     month,
                    "completed": done,
                    "pending":   pend,
                    "total":     total,
                    "rate":      round(done / total * 100, 1) if total > 0 else 0,
                }

            return {
                "user_type":     "agency",
                "agency_code":   agency_code,
                "login_id":      payload.get("login_id", ""),
                "name":          payload.get("name", ""),
                "current_month": aggregate(cur_month),
                "next_month":    aggregate(nxt_month),
            }
    finally:
        conn.close()


@app.get("/api/maturity")
def get_maturity(
    payload:           dict          = Depends(verify_token),
    date_from:         Optional[str] = Query(default=None, description="満期年月日FROM (YYYY-MM-DD)"),
    date_to:           Optional[str] = Query(default=None, description="満期年月日TO (YYYY-MM-DD)"),
    staff_code:        Optional[str] = Query(default=None),
    policy_type:       Optional[str] = Query(default=None),
    renewal_status:    Optional[str] = Query(default=None),
    followcall_status: Optional[str] = Query(default=None),
):
    """
    満期管理エンドポイント

    user_type:agency → group_codeで同グループの代理店契約を参照可能
    user_type:staff  → role_id=1は全代理店、role_id=2,3は同一部課の代理店のみ
    """
    user_type   = payload.get("user_type", "agency")
    group_code  = payload.get("group_code")
    agency_code = payload.get("agency_code")
    today       = datetime.date.today()

    # デフォルト検索範囲：満期3カ月前〜翌3カ月
    if date_from is None:
        d = today.replace(day=1)
        for _ in range(3):
            d = (d - datetime.timedelta(days=1)).replace(day=1)
        date_from = d.isoformat()
    if date_to is None:
        m = today.month + 3
        y = today.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        date_to = datetime.date(y, m, 28).isoformat()

    sql = """
        SELECT
            c.id, c.agency_code, ag.buka_code, c.contract_no, c.customer_name,
            c.renewal_month, c.status,
            c.customer_id, c.policy_number, c.policy_type,
            c.expiry_date, c.annual_premium,
            c.staff_code, c.contact_method, c.contact_info, c.memo,
            c.has_change,
            c.followcall_status, c.renewal_status,
            c.renewed_policy_number, c.renewed_premium,
            c.upsell_status, c.lapse_status,
            mn.notice_date, mn.notice_type,
            CASE WHEN EXISTS(
                SELECT 1 FROM accidents a WHERE a.contract_no = c.contract_no
            ) THEN 1 ELSE 0 END AS has_accident
        FROM contracts c
        LEFT JOIN maturity_notices mn ON mn.contract_id = c.id
        JOIN agencies ag ON ag.agency_code = c.agency_code
        WHERE c.expiry_date IS NOT NULL
          AND c.expiry_date BETWEEN ? AND ?
    """
    params = [date_from, date_to]

    if user_type == "staff":
        role_id   = payload.get("role_id")
        buka_code = payload.get("buka_code")
        if role_id != 1:
            # 担当者・参照専用：同一部課コードの代理店のみ
            sql += " AND ag.buka_code = ?"
            params.append(buka_code)
        # role_id=1（システム管理者）は全代理店を参照可能（WHERE条件なし）
    elif group_code:
        sql += " AND ag.group_code = ?"
        params.append(group_code)
    else:
        sql += " AND c.agency_code = ?"
        params.append(agency_code)

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
