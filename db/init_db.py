"""
データベース初期化スクリプト
users / contracts / maturity_notices テーブルを作成してサンプルデータを登録する
"""
import sqlite3, os, bcrypt
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "users.sqlite")

# ── ユーザーデータ ──────────────────────────────────────────────
DUMMY_USERS = [
    {"agency_code": "A001", "login_id": "admin",  "password": "password123", "name": "管理者 太郎"},
    {"agency_code": "B002", "login_id": "agent1", "password": "pass456",     "name": "代理店 次郎"},
    {"agency_code": "C003", "login_id": "user1",  "password": "pass789",     "name": "利用者 三郎"},
]

# ── 既存ダッシュボード用 契約サンプル設定 ──────────────────────
CONTRACT_CONFIG = [
    ("A001", "2026-05",  28, 217),
    ("A001", "2026-06", 125, 199),
    ("B002", "2026-05",  15, 180),
    ("B002", "2026-06",  80, 210),
    ("C003", "2026-05",  10, 145),
    ("C003", "2026-06",  60, 180),
]

LAST_NAMES  = ["田中","鈴木","佐藤","山田","中村","小林","加藤",
               "吉田","山本","松本","伊藤","渡辺","木村","清水",
               "高橋","橋本","林","斉藤","中島","阿部"]
FIRST_NAMES = ["太郎","花子","一郎","二郎","三郎","直子","美咲",
               "裕子","健一","幸子","浩司","和子","誠","文子",
               "正男","光子","憲一","恵子","隆","久美子"]

def make_name(n):
    return LAST_NAMES[n % len(LAST_NAMES)] + " " + FIRST_NAMES[(n // len(LAST_NAMES)) % len(FIRST_NAMES)]

def notice_date(expiry_str):
    """満期日から60日前を満期案内発送予定日として返す"""
    return (date.fromisoformat(expiry_str) - timedelta(days=60)).isoformat()

# ── 満期管理用 サンプル契約データ（各代理店5件） ──────────────
MATURITY_CONTRACTS = [
    # ── A001 ──────────────────────────────────────────────────
    dict(
        agency_code="A001", contract_no="M-A001-001", customer_name="高橋 健一",
        renewal_month="2026-03", status="completed",
        customer_id="CUST-A001-001", policy_number="POL-A001-2603-0001",
        policy_type="自動車", expiry_date="2026-03-20", annual_premium=85000,
        staff_code="S001", contact_method="TEL", contact_info="090-1234-5678",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-A001-2703-0001", renewed_premium=87000,
        upsell_status="なし", lapse_status=0,
    ),
    dict(
        agency_code="A001", contract_no="M-A001-002", customer_name="田中 裕子",
        renewal_month="2026-04", status="completed",
        customer_id="CUST-A001-002", policy_number="POL-A001-2604-0001",
        policy_type="火災", expiry_date="2026-04-15", annual_premium=120000,
        staff_code="S001", contact_method="メール", contact_info="tanaka@example.com",
        memo="他社に乗り換え。次回フォロー要", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="落ち",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=1,
    ),
    dict(
        agency_code="A001", contract_no="M-A001-003", customer_name="鈴木 一郎",
        renewal_month="2026-05", status="pending",
        customer_id="CUST-A001-003", policy_number="POL-A001-2605-0001",
        policy_type="自動車", expiry_date="2026-05-10", annual_premium=95000,
        staff_code="S002", contact_method="TEL", contact_info="080-9876-5432",
        memo="事故歴あり。保険料上昇の可能性あり要説明", has_accident=1, has_change=0,
        followcall_status="実施済", renewal_status="対応中",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
    ),
    dict(
        agency_code="A001", contract_no="M-A001-004", customer_name="山田 直子",
        renewal_month="2026-05", status="pending",
        customer_id="CUST-A001-004", policy_number="POL-A001-2605-0002",
        policy_type="傷害", expiry_date="2026-05-31", annual_premium=45000,
        staff_code="S002", contact_method="メール", contact_info="yamada@example.com",
        memo="住所変更済。証券送付先確認要", has_accident=0, has_change=1,
        followcall_status="未実施", renewal_status="未対応",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
    ),
    dict(
        agency_code="A001", contract_no="M-A001-005", customer_name="中村 浩司",
        renewal_month="2026-06", status="pending",
        customer_id="CUST-A001-005", policy_number="POL-A001-2606-0001",
        policy_type="火災", expiry_date="2026-06-15", annual_premium=150000,
        staff_code="S001", contact_method="TEL", contact_info="070-1111-2222",
        memo="", has_accident=0, has_change=0,
        followcall_status="未実施", renewal_status="未対応",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
    ),
    # ── B002 ──────────────────────────────────────────────────
    dict(
        agency_code="B002", contract_no="M-B002-001", customer_name="小林 和子",
        renewal_month="2026-03", status="completed",
        customer_id="CUST-B002-001", policy_number="POL-B002-2603-0001",
        policy_type="自動車", expiry_date="2026-03-05", annual_premium=78000,
        staff_code="S003", contact_method="TEL", contact_info="090-3333-4444",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-B002-2703-0001", renewed_premium=80000,
        upsell_status="なし", lapse_status=0,
    ),
    dict(
        agency_code="B002", contract_no="M-B002-002", customer_name="加藤 誠",
        renewal_month="2026-04", status="completed",
        customer_id="CUST-B002-002", policy_number="POL-B002-2604-0001",
        policy_type="火災", expiry_date="2026-04-01", annual_premium=200000,
        staff_code="S003", contact_method="メール", contact_info="kato@example.com",
        memo="車両も提案済。アップセル成功", has_accident=0, has_change=1,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-B002-2704-0001", renewed_premium=210000,
        upsell_status="あり", lapse_status=0,
    ),
    dict(
        agency_code="B002", contract_no="M-B002-003", customer_name="吉田 文子",
        renewal_month="2026-05", status="pending",
        customer_id="CUST-B002-003", policy_number="POL-B002-2605-0001",
        policy_type="傷害", expiry_date="2026-05-15", annual_premium=55000,
        staff_code="S003", contact_method="TEL", contact_info="080-5555-6666",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="対応中",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
    ),
    dict(
        agency_code="B002", contract_no="M-B002-004", customer_name="山本 正男",
        renewal_month="2026-05", status="pending",
        customer_id="CUST-B002-004", policy_number="POL-B002-2605-0002",
        policy_type="自動車", expiry_date="2026-05-25", annual_premium=110000,
        staff_code="S003", contact_method="TEL", contact_info="090-7777-8888",
        memo="事故対応中。修理完了後に更改手続き予定", has_accident=1, has_change=0,
        followcall_status="未実施", renewal_status="未対応",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
    ),
    dict(
        agency_code="B002", contract_no="M-B002-005", customer_name="松本 光子",
        renewal_month="2026-07", status="pending",
        customer_id="CUST-B002-005", policy_number="POL-B002-2607-0001",
        policy_type="その他", expiry_date="2026-07-01", annual_premium=35000,
        staff_code="S003", contact_method="メール", contact_info="matsumoto@example.com",
        memo="", has_accident=0, has_change=0,
        followcall_status="未実施", renewal_status="未対応",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
    ),
    # ── C003 ──────────────────────────────────────────────────
    dict(
        agency_code="C003", contract_no="M-C003-001", customer_name="伊藤 憲一",
        renewal_month="2026-03", status="completed",
        customer_id="CUST-C003-001", policy_number="POL-C003-2603-0001",
        policy_type="自動車", expiry_date="2026-03-31", annual_premium=92000,
        staff_code="S004", contact_method="TEL", contact_info="090-1010-2020",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-C003-2703-0001", renewed_premium=94000,
        upsell_status="なし", lapse_status=0,
    ),
    dict(
        agency_code="C003", contract_no="M-C003-002", customer_name="渡辺 恵子",
        renewal_month="2026-04", status="completed",
        customer_id="CUST-C003-002", policy_number="POL-C003-2604-0001",
        policy_type="火災", expiry_date="2026-04-20", annual_premium=180000,
        staff_code="S004", contact_method="メール", contact_info="watanabe@example.com",
        memo="競合他社に流れた。価格差15%の模様", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="落ち",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=1,
    ),
    dict(
        agency_code="C003", contract_no="M-C003-003", customer_name="木村 隆",
        renewal_month="2026-05", status="pending",
        customer_id="CUST-C003-003", policy_number="POL-C003-2605-0001",
        policy_type="自動車", expiry_date="2026-05-05", annual_premium=72000,
        staff_code="S005", contact_method="TEL", contact_info="080-3030-4040",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="対応中",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
    ),
    dict(
        agency_code="C003", contract_no="M-C003-004", customer_name="清水 久美子",
        renewal_month="2026-05", status="pending",
        customer_id="CUST-C003-004", policy_number="POL-C003-2605-0002",
        policy_type="傷害", expiry_date="2026-05-28", annual_premium=48000,
        staff_code="S005", contact_method="メール", contact_info="shimizu@example.com",
        memo="", has_accident=0, has_change=1,
        followcall_status="未実施", renewal_status="未対応",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
    ),
    dict(
        agency_code="C003", contract_no="M-C003-005", customer_name="高橋 浩司",
        renewal_month="2026-06", status="pending",
        customer_id="CUST-C003-005", policy_number="POL-C003-2606-0001",
        policy_type="火災", expiry_date="2026-06-30", annual_premium=225000,
        staff_code="S004", contact_method="TEL", contact_info="070-5050-6060",
        memo="大口。年払い。慎重に対応", has_accident=0, has_change=0,
        followcall_status="未実施", renewal_status="未対応",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
    ),
]

# 満期案内帳票タイプ（契約順に割り当て）
NOTICE_TYPES = ["はがき", "はがき", "冊子", "冊子", "はがき"]


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        # ── usersテーブル ──────────────────────────────────────
        cur.execute("""
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
        for u in DUMMY_USERS:
            hashed = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt()).decode()
            cur.execute("""
                INSERT INTO users (agency_code, login_id, password_hash, name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(agency_code, login_id) DO UPDATE SET
                    password_hash=excluded.password_hash, name=excluded.name
            """, (u["agency_code"], u["login_id"], hashed, u["name"]))
            print(f"  ユーザー: [{u['agency_code']}] {u['login_id']}")

        # ── contractsテーブル（再作成）──────────────────────────
        cur.execute("DROP TABLE IF EXISTS maturity_notices")
        cur.execute("DROP TABLE IF EXISTS contracts")
        cur.execute("""
            CREATE TABLE contracts (
                id                    INTEGER  PRIMARY KEY AUTOINCREMENT,
                agency_code           TEXT     NOT NULL,
                contract_no           TEXT     NOT NULL UNIQUE,
                customer_name         TEXT     NOT NULL,
                renewal_month         TEXT     NOT NULL,
                status                TEXT     NOT NULL CHECK(status IN ('completed','pending')),
                customer_id           TEXT,
                policy_number         TEXT,
                policy_type           TEXT,
                expiry_date           DATE,
                annual_premium        INTEGER,
                staff_code            TEXT,
                contact_method        TEXT,
                contact_info          TEXT,
                memo                  TEXT,
                has_accident          INTEGER  DEFAULT 0,
                has_change            INTEGER  DEFAULT 0,
                followcall_status     TEXT,
                renewal_status        TEXT,
                renewed_policy_number TEXT,
                renewed_premium       INTEGER,
                upsell_status         TEXT     DEFAULT 'なし',
                lapse_status          INTEGER  DEFAULT 0,
                created_at            DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── maturity_noticesテーブル ───────────────────────────
        cur.execute("""
            CREATE TABLE maturity_notices (
                notice_id   INTEGER  PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER  NOT NULL,
                notice_date DATE     NOT NULL,
                notice_type TEXT     NOT NULL CHECK(notice_type IN ('はがき','冊子')),
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES contracts(id)
            )
        """)

        # ── ダッシュボード用 既存サンプル契約（1449件）──────────
        total_dash = 0
        for agency_code, month, completed, pending in CONTRACT_CONFIG:
            seq = 0
            for sts, cnt in [("completed", completed), ("pending", pending)]:
                for _ in range(cnt):
                    cur.execute("""
                        INSERT INTO contracts (agency_code, contract_no, customer_name, renewal_month, status)
                        VALUES (?, ?, ?, ?, ?)
                    """, (agency_code, f"{agency_code}-{month}-{seq:04d}", make_name(seq), month, sts))
                    seq += 1
            total_dash += completed + pending
        print(f"  契約（ダッシュボード用）: {total_dash}件")

        # ── 満期管理用 サンプル契約（15件）──────────────────────
        for mc in MATURITY_CONTRACTS:
            cur.execute("""
                INSERT INTO contracts (
                    agency_code, contract_no, customer_name, renewal_month, status,
                    customer_id, policy_number, policy_type, expiry_date, annual_premium,
                    staff_code, contact_method, contact_info, memo,
                    has_accident, has_change, followcall_status, renewal_status,
                    renewed_policy_number, renewed_premium, upsell_status, lapse_status
                ) VALUES (
                    :agency_code,:contract_no,:customer_name,:renewal_month,:status,
                    :customer_id,:policy_number,:policy_type,:expiry_date,:annual_premium,
                    :staff_code,:contact_method,:contact_info,:memo,
                    :has_accident,:has_change,:followcall_status,:renewal_status,
                    :renewed_policy_number,:renewed_premium,:upsell_status,:lapse_status
                )
            """, mc)
            # maturity_notices を登録する
            cid = cur.lastrowid
            ntype = NOTICE_TYPES[int(mc["contract_no"].split("-")[-1]) - 1]
            ndate = notice_date(mc["expiry_date"])
            cur.execute("""
                INSERT INTO maturity_notices (contract_id, notice_date, notice_type)
                VALUES (?, ?, ?)
            """, (cid, ndate, ntype))

        print(f"  契約（満期管理用）: {len(MATURITY_CONTRACTS)}件 + notices: {len(MATURITY_CONTRACTS)}件")

        conn.commit()
        print(f"\nDB初期化完了: {DB_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
