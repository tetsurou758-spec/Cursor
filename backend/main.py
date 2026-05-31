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


def require_staff_admin(payload: dict = Depends(verify_token)) -> dict:
    """社員かつシステム管理者ロール（user_type=staff・role_id=1）のみアクセスを許可する"""
    if payload.get("user_type") != "staff" or payload.get("role_id") != 1:
        raise HTTPException(status_code=403, detail="社員管理者権限が必要です")
    return payload


class StaffUserCreateRequest(BaseModel):
    """社員ユーザー登録リクエストのスキーマ"""
    staff_code: str
    password: str
    name: str
    buka_code: str = ""
    role_id: int
    is_active: int = 1


class StaffUserUpdateRequest(BaseModel):
    """社員ユーザー更新リクエストのスキーマ（社員番号変更も可）"""
    staff_code: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    buka_code: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[int] = None


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


# ─── 社員ユーザー管理エンドポイント群（社員システム管理者専用）───────────────────────

@app.get("/api/staff/users")
def get_staff_users(payload: dict = Depends(require_staff_admin)):
    """
    社員管理者のみ：社員全員 ＋ 管轄代理店（同一buka_code）のユーザーを合算して返す。
    各レコードにuser_type（staff/agency）フィールドを付与してテーブル判定に使用する。
    """
    buka_code = payload.get("buka_code", "")
    conn = get_db_connection()
    try:
        # ── 社員ユーザー（全員）────────────────────────────────
        staff_rows = conn.execute("""
            SELECT su.staff_id AS id, su.staff_code AS login_id, su.name,
                   su.buka_code, su.is_active,
                   sr.role_id, sr.role_name,
                   'staff' AS user_type, '' AS agency_code
            FROM staff_users su
            LEFT JOIN staff_roles sr ON su.role_id = sr.role_id
            ORDER BY su.staff_id
        """).fetchall()

        # ── 管轄代理店のユーザー（buka_code一致の代理店に所属するユーザー）──
        agency_rows = conn.execute("""
            SELECT u.id AS id, u.login_id, u.name,
                   '' AS buka_code, u.is_active,
                   r.role_id, r.role_name,
                   'agency' AS user_type, u.agency_code
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.role_id
            LEFT JOIN agencies ag ON u.agency_id = ag.agency_id
            WHERE ag.buka_code = ?
            ORDER BY u.agency_id, u.id
        """, (buka_code,)).fetchall()

        users = [dict(r) for r in staff_rows] + [dict(r) for r in agency_rows]
        return {"users": users}
    finally:
        conn.close()


@app.post("/api/staff/agency-users", status_code=201)
def create_staff_agency_user(request: UserCreateRequest,
                             agency_code: str,
                             payload: dict = Depends(require_staff_admin)):
    """
    社員管理者のみ：管轄代理店に新規ユーザーを登録する。
    管轄外の代理店コードを指定した場合は403を返す。
    """
    buka_code = payload.get("buka_code", "")
    conn = get_db_connection()
    try:
        # 代理店が管轄内かチェック
        ag = conn.execute(
            "SELECT agency_id FROM agencies WHERE agency_code = ? AND buka_code = ?",
            (agency_code, buka_code)
        ).fetchone()
        if not ag:
            raise HTTPException(status_code=403, detail="管轄外の代理店です。または代理店コードが存在しません")

        hashed = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()
        conn.execute("""
            INSERT INTO users (agency_code, agency_id, role_id, login_id, password_hash, name, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (agency_code, ag["agency_id"], request.role_id, request.login_id,
              hashed, request.name, request.is_active))
        conn.commit()
        return {"message": "代理店ユーザーを登録しました", "login_id": request.login_id}
    except HTTPException:
        raise
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="そのログインIDは既に使用されています")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.put("/api/staff/agency-users/{user_id}")
def update_staff_agency_user(user_id: int, request: UserUpdateRequest,
                             payload: dict = Depends(require_staff_admin)):
    """
    社員管理者のみ：管轄代理店のユーザーのロール・有効フラグを変更する。
    管轄外ユーザーへのアクセスは403を返す。
    """
    buka_code = payload.get("buka_code", "")
    conn = get_db_connection()
    try:
        # 管轄内の代理店に属するユーザーかチェック
        row = conn.execute("""
            SELECT u.id FROM users u
            LEFT JOIN agencies ag ON u.agency_id = ag.agency_id
            WHERE u.id = ? AND ag.buka_code = ?
        """, (user_id, buka_code)).fetchone()
        if not row:
            raise HTTPException(status_code=403, detail="管轄外のユーザーです")

        fields, params = [], []
        if request.role_id is not None:
            fields.append("role_id = ?"); params.append(request.role_id)
        if request.is_active is not None:
            fields.append("is_active = ?"); params.append(request.is_active)
        if not fields:
            raise HTTPException(status_code=400, detail="更新する項目がありません")

        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
        return {"message": "代理店ユーザー情報を更新しました"}
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.delete("/api/staff/agency-users/{user_id}")
def delete_staff_agency_user(user_id: int, payload: dict = Depends(require_staff_admin)):
    """社員管理者のみ：管轄代理店のユーザーを論理削除する"""
    buka_code = payload.get("buka_code", "")
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT u.id FROM users u
            LEFT JOIN agencies ag ON u.agency_id = ag.agency_id
            WHERE u.id = ? AND ag.buka_code = ?
        """, (user_id, buka_code)).fetchone()
        if not row:
            raise HTTPException(status_code=403, detail="管轄外のユーザーです")
        conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
        conn.commit()
        return {"message": "代理店ユーザーを無効化しました"}
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.post("/api/staff/users", status_code=201)
def create_staff_user(request: StaffUserCreateRequest,
                      payload: dict = Depends(require_staff_admin)):
    """社員管理者のみ：新規社員ユーザーを登録する"""
    hashed = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO staff_users (staff_code, password, name, buka_code, role_id, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (request.staff_code, hashed, request.name, request.buka_code,
              request.role_id, request.is_active))
        conn.commit()
        return {"message": "社員ユーザーを登録しました", "staff_code": request.staff_code}
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="その社員番号は既に使用されています")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.put("/api/staff/users/{staff_id}")
def update_staff_user(staff_id: int, request: StaffUserUpdateRequest,
                      payload: dict = Depends(require_staff_admin)):
    """社員管理者のみ：社員ユーザー情報を変更する（社員番号の変更も可）"""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT staff_id FROM staff_users WHERE staff_id = ?", (staff_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="社員ユーザーが見つかりません")

        fields, params = [], []
        if request.staff_code is not None:
            fields.append("staff_code = ?"); params.append(request.staff_code)
        if request.password is not None:
            fields.append("password = ?")
            params.append(bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode())
        if request.name is not None:
            fields.append("name = ?"); params.append(request.name)
        if request.buka_code is not None:
            fields.append("buka_code = ?"); params.append(request.buka_code)
        if request.role_id is not None:
            fields.append("role_id = ?"); params.append(request.role_id)
        if request.is_active is not None:
            fields.append("is_active = ?"); params.append(request.is_active)

        if not fields:
            raise HTTPException(status_code=400, detail="更新する項目がありません")

        params.append(staff_id)
        conn.execute(f"UPDATE staff_users SET {', '.join(fields)} WHERE staff_id = ?", params)
        conn.commit()
        return {"message": "社員ユーザー情報を更新しました"}
    except HTTPException:
        raise
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="その社員番号は既に使用されています")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.delete("/api/staff/users/{staff_id}")
def delete_staff_user(staff_id: int, payload: dict = Depends(require_staff_admin)):
    """社員管理者のみ：社員ユーザーを論理削除する（is_active=0）"""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT staff_id FROM staff_users WHERE staff_id = ?", (staff_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="社員ユーザーが見つかりません")
        conn.execute("UPDATE staff_users SET is_active = 0 WHERE staff_id = ?", (staff_id,))
        conn.commit()
        return {"message": "社員ユーザーを無効化しました"}
    except HTTPException:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.get("/api/staff/role-matrix")
def get_staff_role_matrix(payload: dict = Depends(require_staff_admin)):
    """社員管理者のみ：社員ロール×権限マトリクスを返す"""
    conn = get_db_connection()
    try:
        roles    = [dict(r) for r in conn.execute(
            "SELECT role_id, role_name FROM staff_roles ORDER BY role_id"
        ).fetchall()]
        features = [dict(f) for f in conn.execute(
            "SELECT feature_code, feature_name FROM features"
        ).fetchall()]
        return {"roles": roles, "features": features, "permissions": STAFF_PERMISSIONS}
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
                    return {"month": month, "completed": 0, "pending": 0, "total": 0, "rate": 0, "total_contracts": 0}
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
                all_cnt = cur.execute(
                    f"SELECT COUNT(*) FROM contracts WHERE agency_code IN ({placeholders})",
                    tuple(agency_codes)
                ).fetchone()[0]
                return {
                    "month":           month,
                    "completed":       done,
                    "pending":         pend,
                    "total":           total,
                    "rate":            round(done / total * 100, 1) if total > 0 else 0,
                    "total_contracts": all_cnt,
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
                all_cnt = cur.execute(
                    "SELECT COUNT(*) FROM contracts WHERE agency_code = ?", (agency_code,)
                ).fetchone()[0]
                return {
                    "month":           month,
                    "completed":       done,
                    "pending":         pend,
                    "total":           total,
                    "rate":            round(done / total * 100, 1) if total > 0 else 0,
                    "total_contracts": all_cnt,
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


class CustomerMatchRequest(BaseModel):
    """名寄せ判定リクエストのスキーマ"""
    group_code: str
    gender: str
    birth_date: str
    first_name: str
    tel: Optional[str] = None
    address: Optional[str] = None


@app.get("/api/customers")
def get_customers(
    payload:           dict          = Depends(verify_token),
    last_name:         Optional[str] = Query(default=None, description="姓（部分一致）"),
    first_name:        Optional[str] = Query(default=None, description="名（部分一致）"),
    agency_code:       Optional[str] = Query(default=None, description="代理店コード"),
    policy_type:       Optional[str] = Query(default=None, description="保有種目"),
    staff_code:        Optional[str] = Query(default=None, description="担当者コード"),
    group_code:        Optional[str] = Query(default=None, description="参照グループコード"),
    tel:               Optional[str] = Query(default=None, description="電話番号（部分一致）"),
    contract_no:       Optional[str] = Query(default=None, description="証券番号（部分一致）"),
    not_insured_types: Optional[str] = Query(default=None, description="未加入種目フィルタ（カンマ区切り）"),
):
    """
    顧客一覧を返す

    代理店ユーザー：自代理店のgroup_codeに属する顧客のみ
    社員ユーザー：管轄部課配下の全group_codeの顧客
    各顧客に保有種目サマリーと複数代理店またがりフラグを付与する
    """
    user_type = payload.get("user_type", "agency")
    conn = get_db_connection()
    try:
        # ── アクセス可能なgroup_codeリストを決定 ──────────────────
        if user_type == "staff":
            role_id   = payload.get("role_id")
            buka_code = payload.get("buka_code")
            if role_id == 1:
                ag_rows = conn.execute("SELECT DISTINCT group_code FROM agencies").fetchall()
            else:
                ag_rows = conn.execute(
                    "SELECT DISTINCT group_code FROM agencies WHERE buka_code = ?", (buka_code,)
                ).fetchall()
            allowed_groups = [r["group_code"] for r in ag_rows]
        else:
            own_gc = payload.get("group_code")
            allowed_groups = [own_gc] if own_gc else []

        # group_codeフィルタ（社員が絞り込む場合）
        if group_code:
            allowed_groups = [g for g in allowed_groups if g == group_code]

        if not allowed_groups:
            return {"customers": [], "total": 0}

        placeholders = ",".join("?" * len(allowed_groups))
        sql    = f"SELECT * FROM customers WHERE group_code IN ({placeholders})"
        params = list(allowed_groups)

        if last_name:
            sql += " AND last_name LIKE ?"
            params.append(f"%{last_name}%")
        if first_name:
            sql += " AND (first_name LIKE ? OR first_name_raw LIKE ?)"
            params.extend([f"%{first_name}%", f"%{first_name}%"])
        if tel:
            sql += " AND tel LIKE ?"
            params.append(f"%{tel}%")

        # 証券番号から紐づく顧客IDを逆引き
        if contract_no:
            cno_rows = conn.execute(
                "SELECT DISTINCT linked_customer_id FROM contracts WHERE contract_no LIKE ? AND linked_customer_id IS NOT NULL",
                (f"%{contract_no}%",)
            ).fetchall()
            cno_ids = [r["linked_customer_id"] for r in cno_rows]
            if cno_ids:
                ph2 = ",".join("?" * len(cno_ids))
                sql += f" AND customer_id IN ({ph2})"
                params.extend(cno_ids)
            else:
                return {"customers": [], "total": 0}

        sql += " ORDER BY group_code, customer_id"
        customers = [dict(r) for r in conn.execute(sql, params).fetchall()]

        # ── 各顧客の契約サマリーを付与 ────────────────────────────
        for cust in customers:
            cid = cust["customer_id"]

            # 絞り込み条件（代理店・担当者・種目）
            c_sql    = "SELECT agency_code, policy_type, staff_code FROM contracts WHERE linked_customer_id = ?"
            c_params = [cid]
            if agency_code:
                c_sql += " AND agency_code = ?"
                c_params.append(agency_code)
            if staff_code:
                c_sql += " AND staff_code = ?"
                c_params.append(staff_code)
            if policy_type:
                c_sql += " AND policy_type = ?"
                c_params.append(policy_type)

            c_rows = conn.execute(c_sql, c_params).fetchall()

            held_types   = {r["policy_type"] for r in c_rows}
            held_agencies = {r["agency_code"] for r in c_rows}
            all_types    = ["自動車", "火災", "傷害", "自賠責", "賠償責任", "サイバーリスク", "所得補償"]

            cust["policy_summary"]     = {t: (t in held_types) for t in all_types}
            cust["held_agencies"]      = sorted(held_agencies)
            cust["multi_agency"]       = len(held_agencies) > 1
            cust["contract_count"]     = len(c_rows)

        # policy_typeフィルタがある場合、保有契約ゼロの顧客を除外
        if policy_type or agency_code or staff_code:
            customers = [c for c in customers if c["contract_count"] > 0]

        # 未加入種目フィルタ（指定種目の契約を持たない顧客のみ）
        if not_insured_types:
            types_list = [t.strip() for t in not_insured_types.split(",") if t.strip()]
            if types_list:
                customers = [
                    c for c in customers
                    if all(not c["policy_summary"].get(t, False) for t in types_list)
                ]

        return {"customers": customers, "total": len(customers)}
    finally:
        conn.close()


@app.get("/api/customers/{customer_id}")
def get_customer_detail(customer_id: int, payload: dict = Depends(verify_token)):
    """
    顧客詳細を返す

    group_codeチェックでアクセス権限を確認する。
    紐づく契約一覧（全種目・全代理店）を含む。
    """
    user_type = payload.get("user_type", "agency")
    conn = get_db_connection()
    try:
        cust = conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        if not cust:
            raise HTTPException(status_code=404, detail="顧客が見つかりません")

        cust_gc = cust["group_code"]

        # アクセス権限チェック
        if user_type == "staff":
            role_id   = payload.get("role_id")
            buka_code = payload.get("buka_code")
            if role_id != 1:
                ag = conn.execute(
                    "SELECT 1 FROM agencies WHERE group_code = ? AND buka_code = ?",
                    (cust_gc, buka_code)
                ).fetchone()
                if not ag:
                    raise HTTPException(status_code=403, detail="アクセス権限がありません")
        else:
            if cust_gc != payload.get("group_code"):
                raise HTTPException(status_code=403, detail="アクセス権限がありません")

        # 紐づく契約一覧
        contracts = [dict(r) for r in conn.execute("""
            SELECT c.*, ag.agency_name, ag.group_code AS ag_group_code
            FROM contracts c
            LEFT JOIN agencies ag ON ag.agency_code = c.agency_code
            WHERE c.linked_customer_id = ?
            ORDER BY c.agency_code, c.expiry_date
        """, (customer_id,)).fetchall()]

        # 顧客一覧と同形式のサマリーを付与
        cust_dict = dict(cust)
        all_types = ["自動車", "火災", "傷害", "自賠責", "賠償責任", "サイバーリスク", "所得補償"]
        held_types    = {c["policy_type"] for c in contracts}
        held_agencies = sorted({c["agency_code"] for c in contracts})
        cust_dict["policy_summary"] = {t: (t in held_types) for t in all_types}
        cust_dict["held_agencies"]  = held_agencies
        cust_dict["multi_agency"]   = len(held_agencies) > 1
        cust_dict["contract_count"] = len(contracts)

        return {"customer": cust_dict, "contracts": contracts}
    finally:
        conn.close()


@app.post("/api/customers/match")
def match_customer(request: CustomerMatchRequest, payload: dict = Depends(verify_token)):
    """
    名寄せ判定API

    同一group_code内で性別・生年月日・名が一致 AND (電話番号 OR 住所) が一致する
    既存顧客IDを返す。一致候補リストと判定根拠も付与する。
    """
    conn = get_db_connection()
    try:
        # 必須3項目のみで候補を絞る
        candidates = conn.execute("""
            SELECT * FROM customers
            WHERE group_code = ?
              AND gender = ?
              AND birth_date = ?
              AND (first_name_raw = ? OR first_name = ?)
        """, (request.group_code, request.gender, request.birth_date,
              request.first_name, request.first_name)).fetchall()

        matched_id   = None
        matched_list = []
        for row in candidates:
            reasons = ["性別一致", "生年月日一致", "名一致"]
            tel_match     = bool(request.tel     and row["tel"]     and request.tel     == row["tel"])
            address_match = bool(request.address and row["address"] and request.address == row["address"])
            if tel_match:
                reasons.append("電話番号一致")
            if address_match:
                reasons.append("住所一致")

            is_match = tel_match or address_match
            if is_match and matched_id is None:
                matched_id = row["customer_id"]

            matched_list.append({
                "customer_id":  row["customer_id"],
                "last_name":    row["last_name"],
                "first_name":   row["first_name"],
                "birth_date":   row["birth_date"],
                "tel":          row["tel"],
                "address":      row["address"],
                "is_match":     is_match,
                "match_reasons": reasons,
            })

        return {
            "matched_customer_id": matched_id,
            "candidates":          matched_list,
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
    customer_name:     Optional[str] = Query(default=None, description="顧客氏名（部分一致）"),
    contract_no:       Optional[str] = Query(default=None, description="証券番号（部分一致）"),
):
    """
    満期管理エンドポイント

    user_type:agency → group_codeで同グループの代理店契約を参照可能
    user_type:staff  → role_id=1は全代理店、role_id=2,3は同一部課の代理店のみ
    date_from/date_toが空の場合はWHERE条件から除外（全期間）
    """
    user_type   = payload.get("user_type", "agency")
    group_code  = payload.get("group_code")
    agency_code = payload.get("agency_code")

    sql = """
        SELECT
            c.id, c.agency_code, ag.buka_code, c.contract_no, c.customer_name,
            c.renewal_month, c.status,
            c.linked_customer_id, c.policy_number, c.policy_type,
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
    """
    params = []

    if date_from and date_from.strip():
        sql += " AND c.expiry_date >= ?"
        params.append(date_from.strip())
    if date_to and date_to.strip():
        sql += " AND c.expiry_date <= ?"
        params.append(date_to.strip())

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
    if customer_name and customer_name.strip():
        sql += " AND c.customer_name LIKE ?"
        params.append(f"%{customer_name.strip()}%")
    if contract_no and contract_no.strip():
        sql += " AND c.contract_no LIKE ?"
        params.append(f"%{contract_no.strip()}%")

    sql += " ORDER BY c.expiry_date"

    conn = get_db_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        contracts = [dict(r) for r in rows]
        return {"contracts": contracts, "total": len(contracts)}
    finally:
        conn.close()


@app.get("/api/contracts/search")
def search_contracts(
    payload:       dict          = Depends(verify_token),
    q:             Optional[str] = Query(default=None,  description="汎用検索（証券番号/顧客名/電話番号）"),
    policy_no:     Optional[str] = Query(default=None,  description="証券番号（部分一致）"),
    customer_name: Optional[str] = Query(default=None,  description="顧客名（部分一致）"),
    customer_tel:  Optional[str] = Query(default=None,  description="電話番号（部分一致）"),
    policy_type:   Optional[str] = Query(default=None,  description="保険種目"),
    agency_code_q: Optional[str] = Query(default=None,  alias="agency_code", description="代理店コード（社員絞込）"),
    page:          int           = Query(default=1,  ge=1),
    limit:         int           = Query(default=50, ge=1, le=200),
    sort_by:       str           = Query(default="expiry_date"),
    sort_order:    str           = Query(default="asc"),
):
    """
    契約検索一覧（ページング・ソート対応）

    代理店ユーザー：自グループの契約のみ
    社員ユーザー：role_id=1は全件、2/3は同一buka_codeの代理店のみ
    """
    user_type  = payload.get("user_type", "agency")
    group_code = payload.get("group_code")
    own_agency = payload.get("agency_code")

    valid_cols = {"expiry_date", "contract_no", "policy_type", "customer_name", "annual_premium"}
    sort_col   = sort_by if sort_by in valid_cols else "expiry_date"
    sort_dir   = "ASC" if sort_order.lower() == "asc" else "DESC"

    conn = get_db_connection()
    try:
        sql = """
            SELECT c.id, c.contract_no, c.agency_code, c.customer_name,
                   c.contractor_last_name, c.contractor_first_name,
                   c.contractor_tel,
                   c.policy_type, c.policy_number, c.expiry_date,
                   c.annual_premium, c.renewal_status, c.linked_customer_id,
                   ag.agency_name
            FROM contracts c
            JOIN agencies ag ON ag.agency_code = c.agency_code
            WHERE 1=1
        """
        params = []

        if user_type == "staff":
            role_id   = payload.get("role_id")
            buka_code = payload.get("buka_code")
            if role_id != 1:
                sql += " AND ag.buka_code = ?"
                params.append(buka_code)
            if agency_code_q:
                sql += " AND c.agency_code = ?"
                params.append(agency_code_q)
        elif group_code:
            sql += " AND ag.group_code = ?"
            params.append(group_code)
        else:
            sql += " AND c.agency_code = ?"
            params.append(own_agency)

        if q:
            sql += " AND (c.contract_no LIKE ? OR c.customer_name LIKE ? OR c.contractor_tel LIKE ?)"
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        if policy_no:
            sql += " AND c.contract_no LIKE ?"
            params.append(f"%{policy_no}%")
        if customer_name:
            sql += " AND c.customer_name LIKE ?"
            params.append(f"%{customer_name}%")
        if customer_tel:
            sql += " AND c.contractor_tel LIKE ?"
            params.append(f"%{customer_tel}%")
        if policy_type:
            sql += " AND c.policy_type = ?"
            params.append(policy_type)

        count_sql = f"SELECT COUNT(*) FROM ({sql})"
        total = conn.execute(count_sql, params).fetchone()[0]

        sql += f" ORDER BY c.{sort_col} {sort_dir} LIMIT ? OFFSET ?"
        params.extend([limit, (page - 1) * limit])

        rows = conn.execute(sql, params).fetchall()
        return {"total": total, "page": page, "limit": limit, "contracts": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.get("/api/contracts/direct-search")
def direct_search_contracts(
    payload: dict = Depends(verify_token),
    q:       str  = Query(..., description="検索クエリ"),
):
    """
    ダイレクト検索（入力値を自動判定して振り分け）

    数字始まり → 電話番号検索（contractor_tel）
    全角文字始まり → 顧客名検索（customer_name）
    それ以外 → 証券番号検索（contract_no）

    0件 → {redirect: "none", count: 0}
    1件 → {redirect: "detail", contract_no: "XXXX", count: 1}
    2件以上 → {redirect: "list", q: "XXXX", count: N}
    """
    if not q:
        return {"redirect": "none", "count": 0}

    user_type  = payload.get("user_type", "agency")
    group_code = payload.get("group_code")
    agency_code = payload.get("agency_code")

    first_char = q[0]
    if first_char.isdigit():
        search_type = "tel"
    elif ord(first_char) > 127:
        search_type = "name"
    else:
        search_type = "contract"

    conn = get_db_connection()
    try:
        if search_type == "tel":
            cond = "c.contractor_tel LIKE ?"
        elif search_type == "name":
            cond = "c.customer_name LIKE ?"
        else:
            cond = "c.contract_no LIKE ?"

        sql = f"""
            SELECT c.contract_no FROM contracts c
            JOIN agencies ag ON ag.agency_code = c.agency_code
            WHERE {cond}
        """
        params = [f"%{q}%"]

        if user_type == "staff":
            role_id   = payload.get("role_id")
            buka_code = payload.get("buka_code")
            if role_id != 1:
                sql += " AND ag.buka_code = ?"
                params.append(buka_code)
        elif group_code:
            sql += " AND ag.group_code = ?"
            params.append(group_code)
        else:
            sql += " AND c.agency_code = ?"
            params.append(agency_code)

        sql += " LIMIT 51"
        rows = conn.execute(sql, params).fetchall()
        count = len(rows)

        if count == 0:
            return {"redirect": "none", "count": 0}
        elif count == 1:
            return {"redirect": "detail", "contract_no": rows[0]["contract_no"], "count": 1}
        else:
            return {"redirect": "list", "q": q, "count": min(count, 50)}
    finally:
        conn.close()


@app.get("/api/contracts/{contract_no}")
def get_contract_detail(contract_no: str, payload: dict = Depends(verify_token)):
    """
    契約詳細を返す（contract_details LEFT OUTER JOIN）

    アクセス制御：
    - agency ユーザー → 自分のgroup_codeに属する代理店の契約のみ
    - staff ユーザー → role_id=1は全件、2/3は同一buka_codeの代理店のみ
    """
    user_type   = payload.get("user_type", "agency")
    group_code  = payload.get("group_code")
    agency_code = payload.get("agency_code")

    conn = get_db_connection()
    try:
        sql = """
            SELECT
                c.*,
                ag.buka_code, ag.agency_name, ag.group_code AS ag_group_code,
                cd.product_name, cd.coverage_target,
                cd.auto_taininsho, cd.auto_taibutsusho, cd.auto_jinshin,
                cd.auto_toshasho, cd.auto_vehicle_amount, cd.auto_vehicle_type,
                cd.auto_deductible, cd.auto_nfl_grade, cd.auto_age_condition,
                cd.auto_driver_limit, cd.auto_use_purpose,
                cd.auto_car_name, cd.auto_car_model, cd.auto_plate_no,
                cd.fire_building_amount, cd.fire_household_amount,
                cd.fire_structure, cd.fire_location,
                cd.fire_quake_flg, cd.fire_quake_amount,
                cd.fire_flood_flg, cd.fire_deductible,
                cd.jibai_car_name, cd.jibai_car_model,
                cd.jibai_plate_no, cd.jibai_coverage_limit,
                cd.inj_death_amount, cd.inj_disability_amount,
                cd.inj_hospital_daily, cd.inj_surgery_benefit,
                cd.inj_outpatient_daily, cd.inj_coverage_scope,
                cd.liab_coverage_limit, cd.liab_deductible,
                cd.liab_jidan_flg, cd.liab_coverage_scope,
                cd.cyber_3rd_limit, cd.cyber_leak_limit,
                cd.cyber_restore_limit, cd.cyber_biz_interruption_flg,
                cd.cyber_annual_revenue
            FROM contracts c
            JOIN agencies ag ON ag.agency_code = c.agency_code
            LEFT OUTER JOIN contract_details cd ON cd.contract_id = c.id
            WHERE c.contract_no = ?
        """
        params = [contract_no]

        # アクセス制御
        if user_type == "staff":
            role_id   = payload.get("role_id")
            buka_code = payload.get("buka_code")
            if role_id != 1:
                sql += " AND ag.buka_code = ?"
                params.append(buka_code)
        elif group_code:
            sql += " AND ag.group_code = ?"
            params.append(group_code)
        else:
            sql += " AND c.agency_code = ?"
            params.append(agency_code)

        row = conn.execute(sql, params).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="契約が見つかりません")

        return {"contract": dict(row)}
    finally:
        conn.close()
