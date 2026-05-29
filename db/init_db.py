"""
データベース初期化スクリプト
テスト用ダミーユーザーを3件登録する
"""
import sqlite3
import os
import bcrypt

# データベースファイルのパス
DB_PATH = os.path.join(os.path.dirname(__file__), "users.sqlite")

# テスト用ダミーアカウント一覧
DUMMY_USERS = [
    {"agency_code": "A001", "login_id": "admin",  "password": "password123", "name": "管理者 太郎"},
    {"agency_code": "B002", "login_id": "agent1", "password": "pass456",     "name": "代理店 次郎"},
    {"agency_code": "C003", "login_id": "user1",  "password": "pass789",     "name": "利用者 三郎"},
]


def init_db() -> None:
    """
    usersテーブルを作成し、ダミーユーザーを登録する
    既存レコードは代理店コード＋ログインIDの一意制約でUPSERTされる
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        # usersテーブルを作成する（既存の場合はスキップ）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER  PRIMARY KEY AUTOINCREMENT,
                agency_code   TEXT     NOT NULL,
                login_id      TEXT     NOT NULL,
                password_hash TEXT     NOT NULL,
                name          TEXT     NOT NULL,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(agency_code, login_id)
            )
        """)

        # ダミーユーザーをハッシュ化して登録する
        for user in DUMMY_USERS:
            hashed = bcrypt.hashpw(user["password"].encode(), bcrypt.gensalt()).decode()
            cursor.execute(
                """
                INSERT INTO users (agency_code, login_id, password_hash, name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(agency_code, login_id) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    name          = excluded.name
                """,
                (user["agency_code"], user["login_id"], hashed, user["name"]),
            )
            print(f"  登録完了: [{user['agency_code']}] {user['login_id']} ({user['name']})")

        conn.commit()
        print(f"\nデータベースの初期化が完了しました: {DB_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
