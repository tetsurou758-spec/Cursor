from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt
import bcrypt
import sqlite3
import datetime
import os

app = FastAPI(title="仮想損害保険 代理店システムAPI")

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
        "login_id": user["login_id"],
        "name": user["name"],
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "name": user["name"],
    }
