"""
データベース初期化スクリプト
users テーブルとcontractsテーブルを作成し、サンプルデータを登録する
"""
import sqlite3
import os
import bcrypt

DB_PATH = os.path.join(os.path.dirname(__file__), "users.sqlite")

# ─── ユーザーデータ ──────────────────────────────────────────
DUMMY_USERS = [
    {"agency_code": "A001", "login_id": "admin",  "password": "password123", "name": "管理者 太郎"},
    {"agency_code": "B002", "login_id": "agent1", "password": "pass456",     "name": "代理店 次郎"},
    {"agency_code": "C003", "login_id": "user1",  "password": "pass789",     "name": "利用者 三郎"},
]

# ─── 契約サンプルデータ設定 ──────────────────────────────────
# (代理店コード, 更改月, 完了件数, 対応中件数)
CONTRACT_CONFIG = [
    ("A001", "2026-05",  28, 217),   # 今月 合計245件
    ("A001", "2026-06", 125, 199),   # 翌月 合計324件
    ("B002", "2026-05",  15, 180),   # 今月 合計195件
    ("B002", "2026-06",  80, 210),   # 翌月 合計290件
    ("C003", "2026-05",  10, 145),   # 今月 合計155件
    ("C003", "2026-06",  60, 180),   # 翌月 合計240件
]

# 顧客名生成用リスト
LAST_NAMES  = ["田中", "鈴木", "佐藤", "山田", "中村", "小林", "加藤",
               "吉田", "山本", "松本", "伊藤", "渡辺", "木村", "清水",
               "高橋", "橋本", "林", "斉藤", "中島", "阿部"]
FIRST_NAMES = ["太郎", "花子", "一郎", "二郎", "三郎", "直子", "美咲",
               "裕子", "健一", "幸子", "浩司", "和子", "誠", "文子",
               "正男", "光子", "憲一", "恵子", "隆", "久美子"]


def make_name(n: int) -> str:
    """連番から顧客名を生成する"""
    return (LAST_NAMES[n % len(LAST_NAMES)] + " " +
            FIRST_NAMES[(n // len(LAST_NAMES)) % len(FIRST_NAMES)])


def init_db() -> None:
    """
    users・contractsテーブルを作成してサンプルデータを登録する
    既存レコードはUPSERT（conflictしたら上書き）で処理する
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        # ── usersテーブル ──────────────────────────────────────
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

        for user in DUMMY_USERS:
            hashed = bcrypt.hashpw(user["password"].encode(), bcrypt.gensalt()).decode()
            cursor.execute("""
                INSERT INTO users (agency_code, login_id, password_hash, name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(agency_code, login_id) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    name          = excluded.name
            """, (user["agency_code"], user["login_id"], hashed, user["name"]))
            print(f"  ユーザー登録: [{user['agency_code']}] {user['login_id']} ({user['name']})")

        # ── contractsテーブル ──────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contracts (
                id            INTEGER  PRIMARY KEY AUTOINCREMENT,
                agency_code   TEXT     NOT NULL,
                contract_no   TEXT     NOT NULL UNIQUE,
                customer_name TEXT     NOT NULL,
                renewal_month TEXT     NOT NULL,
                status        TEXT     NOT NULL CHECK(status IN ('completed', 'pending')),
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 既存の契約データを削除して再登録する
        cursor.execute("DELETE FROM contracts")

        total_contracts = 0
        for agency_code, month, completed, pending in CONTRACT_CONFIG:
            seq = 0
            for status, count in [("completed", completed), ("pending", pending)]:
                for _ in range(count):
                    cursor.execute("""
                        INSERT INTO contracts (agency_code, contract_no, customer_name, renewal_month, status)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        agency_code,
                        f"{agency_code}-{month}-{seq:04d}",
                        make_name(seq),
                        month,
                        status,
                    ))
                    seq += 1
            subtotal = completed + pending
            total_contracts += subtotal
            print(f"  契約登録: {agency_code} {month} 完了{completed}件/対応中{pending}件={subtotal}件")

        conn.commit()
        print(f"\nデータベースの初期化が完了しました: {DB_PATH}")
        print(f"  contracts 合計: {total_contracts}件")

    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
