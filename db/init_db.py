"""
データベース初期化スクリプト
全テーブルを再作成し、サンプルデータを登録する
"""
import sqlite3, os, bcrypt, random, hashlib
from datetime import date, timedelta

random.seed(42)  # 再実行しても同じデータを生成する

DB_PATH = os.path.join(os.path.dirname(__file__), "users.sqlite")

# ── ランダムデータ生成用定数 ─────────────────────────────────────
POLICY_TYPES    = ['自動車', '火災', '傷害', 'その他']
STAFF_CODES_ALL = ['S001', 'S002', 'S003', 'S004', 'S005']
NOTICE_TYPES_ALL = ['はがき', '冊子']

def rand_contact():
    """連絡手段と連絡先のダミーデータを返す"""
    if random.choice([True, False]):
        return 'TEL', f"090-{random.randint(1000,9999)}-{random.randint(1000,9999)}"
    else:
        return 'メール', f"user{random.randint(100,999)}@example.com"

# ── 代理店マスタ（buka_code追加）─────────────────────────────────
AGENCIES = [
    dict(agency_id=1, agency_code="A001", agency_name="AXエージェント東京本店",
         address="東京都千代田区丸の内1-1-1",      tel="03-1111-0001", email="a001@ax-agent.jp", group_code="A", buka_code="X001"),
    dict(agency_id=2, agency_code="A002", agency_name="AXエージェント東京支店1",
         address="東京都新宿区西新宿2-2-2",        tel="03-1111-0002", email="a002@ax-agent.jp", group_code="A", buka_code="X001"),
    dict(agency_id=3, agency_code="A003", agency_name="AXエージェント東京支店2",
         address="東京都渋谷区道玄坂3-3-3",       tel="03-1111-0003", email="a003@ax-agent.jp", group_code="A", buka_code="X001"),
    dict(agency_id=4, agency_code="B001", agency_name="BXエージェント大阪本店",
         address="大阪府大阪市北区梅田1-1-1",     tel="06-2222-0001", email="b001@bx-agent.jp", group_code="B", buka_code="Y001"),
    dict(agency_id=5, agency_code="B002", agency_name="BXエージェント大阪支店1",
         address="大阪府大阪市中央区本町2-2-2",   tel="06-2222-0002", email="b002@bx-agent.jp", group_code="B", buka_code="X001"),
    dict(agency_id=6, agency_code="C001", agency_name="CXエージェント名古屋本店",
         address="愛知県名古屋市中村区名駅1-1-1", tel="052-3333-0001", email="c001@cx-agent.jp", group_code="C", buka_code="Z001"),
    dict(agency_id=7, agency_code="C003", agency_name="CXエージェント名古屋支店1",
         address="愛知県名古屋市栄2-2-2",         tel="052-3333-0003", email="c003@cx-agent.jp", group_code="C", buka_code="X001"),
]

# ── 代理店向けロールマスタ ───────────────────────────────────────
ROLES = [
    dict(role_id=1, role_name="管理者",   description="全機能にアクセス可能な管理者ロール"),
    dict(role_id=2, role_name="一般担当", description="保険金支払状況参照を除く通常業務ロール"),
    dict(role_id=3, role_name="閲覧専用", description="限定的な参照のみ可能なロール"),
]

# ── 社員向けロールマスタ ─────────────────────────────────────────
STAFF_ROLES = [
    dict(role_id=1, role_name="システム管理者", description="全部課・全代理店・全権限"),
    dict(role_id=2, role_name="代理店担当者",   description="同一部課コードの代理店のみ・編集可"),
    dict(role_id=3, role_name="参照専用社員",   description="同一部課コードの代理店のみ・参照のみ"),
]

# ── 機能マスタ ───────────────────────────────────────────────────
FEATURES = [
    dict(feature_code="PAYMENT_VIEW",  feature_name="保険金支払状況参照", description="保険金支払状況の参照機能"),
    dict(feature_code="CUSTOMER_EDIT", feature_name="顧客情報編集",       description="顧客情報の参照・編集機能"),
    dict(feature_code="MATURITY_VIEW", feature_name="満期管理参照",       description="満期管理の参照機能"),
    dict(feature_code="REPORT_VIEW",   feature_name="帳票出力",           description="各種帳票のPDF出力機能"),
    dict(feature_code="USER_ADMIN",    feature_name="ユーザー管理",       description="ユーザーの登録・編集・削除機能"),
]

# ── ロール×機能マッピング ─────────────────────────────────────────
ROLE_PERMISSIONS = [
    (1, "PAYMENT_VIEW"), (1, "CUSTOMER_EDIT"), (1, "MATURITY_VIEW"), (1, "REPORT_VIEW"), (1, "USER_ADMIN"),
    (2, "CUSTOMER_EDIT"), (2, "MATURITY_VIEW"), (2, "REPORT_VIEW"), (2, "USER_ADMIN"),
    (3, "PAYMENT_VIEW"), (3, "USER_ADMIN"),
]

# ── 代理店ユーザーデータ ─────────────────────────────────────────
DUMMY_USERS = [
    dict(agency_code="A001", agency_id=1, role_id=1, login_id="admin",  password="password123", name="管理者 太郎", is_active=1),
    dict(agency_code="A001", agency_id=1, role_id=2, login_id="staff1", password="pass001",     name="担当 一郎",   is_active=1),
    dict(agency_code="B002", agency_id=5, role_id=2, login_id="agent1", password="pass456",     name="代理店 次郎", is_active=1),
    dict(agency_code="C003", agency_id=7, role_id=3, login_id="user1",  password="pass789",     name="利用者 三郎", is_active=1),
]

# ── 社員ユーザーデータ ────────────────────────────────────────────
STAFF_USERS = [
    dict(staff_code="S001", password="staff123", name="山田太郎", buka_code="X001", role_id=1, is_active=1),
    dict(staff_code="S002", password="staff456", name="鈴木花子", buka_code="X001", role_id=2, is_active=1),
    dict(staff_code="S003", password="staff789", name="佐藤次郎", buka_code="Y001", role_id=3, is_active=1),
]

# ── 事故データ（A001配下の契約2件）─────────────────────────────
ACCIDENTS = [
    dict(contract_no="M-A001-001", report_date="2026-03-10", accident_type="車両事故", status="処理完了"),
    dict(contract_no="M-A001-003", report_date="2026-05-02", accident_type="車両事故", status="対応中"),
]

# ── ダッシュボード用 既存サンプル契約設定 ─────────────────────
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

# 名前→性別マッピング（FIRST_NAMESと対応）
_FIRST_NAME_GENDER = {
    "太郎": "M", "花子": "F", "一郎": "M", "二郎": "M", "三郎": "M",
    "直子": "F", "美咲": "F", "裕子": "F", "健一": "M", "幸子": "F",
    "浩司": "M", "和子": "F", "誠":   "M", "文子": "F", "正男": "M",
    "光子": "F", "憲一": "M", "恵子": "F", "隆":   "M", "久美子": "F",
}

# 代理店グループ→住所プレフィックス・区名リスト
_ADDR_CONFIG = {
    "A": ("東京都",       ["新宿区", "渋谷区", "港区", "品川区", "目黒区", "世田谷区", "中野区", "杉並区"]),
    "B": ("大阪府大阪市", ["北区", "中央区", "西区", "浪速区", "天王寺区", "住吉区", "生野区", "福島区"]),
    "C": ("愛知県名古屋市", ["中区", "昭和区", "瑞穂区", "守山区", "名東区", "天白区", "緑区", "港区"]),
}

def make_contractor_info(customer_name: str, agency_code: str) -> dict:
    """
    customer_name と agency_code から名寄せ用contractor情報を確定的に生成する。
    同一 customer_name であれば常に同じ値を返すため、バッチで同一人物として名寄せされる。
    """
    import hashlib as _hl
    parts = customer_name.split()
    last_name  = parts[0]
    first_name = parts[1] if len(parts) > 1 else ""

    gender = _FIRST_NAME_GENDER.get(first_name, "M")
    first_name_masked = mask_first_name(first_name)

    # 氏名のハッシュで確定的に生成
    h = int(_hl.md5((last_name + first_name).encode("utf-8")).hexdigest(), 16)

    year  = 1945 + (h % 51)           # 1945–1995
    month = 1 + ((h >> 8)  % 12)
    day   = 1 + ((h >> 16) % 28)
    birth_date = f"{year}-{month:02d}-{day:02d}"

    tel_prefix = ["070", "080", "090"][h % 3]
    tel = f"{tel_prefix}-{(h >> 4) % 10000:04d}-{(h >> 20) % 10000:04d}"

    grp = agency_code[0]
    city, wards = _ADDR_CONFIG.get(grp, ("東京都", ["中央区"]))
    ward    = wards[h % len(wards)]
    chome   = (h >> 12) % 9 + 1
    ban     = (h >> 20) % 9 + 1
    gou     = (h >> 28) % 9 + 1
    address = f"{city}{ward}{chome}-{ban}-{gou}"

    return {
        "contractor_last_name":      last_name,
        "contractor_first_name":     first_name_masked,
        "contractor_first_name_raw": first_name,
        "contractor_gender":         gender,
        "contractor_birth_date":     birth_date,
        "contractor_tel":            tel,
        "contractor_address":        address,
    }

def notice_date(expiry_str):
    """満期日から90日前（約3ヶ月）を満期案内発送予定日として返す"""
    return (date.fromisoformat(expiry_str) - timedelta(days=90)).isoformat()

# ── 満期管理用 サンプル契約データ（各代理店5〜6件）────────────
MATURITY_CONTRACTS = [
    # ── A001 ──────────────────────────────────────────────────
    dict(
        agency_code="A001", contract_no="M-A001-001", customer_name="高橋 健一",
        renewal_month="2026-03", status="completed",
        policy_number="POL-A001-2603-0001",
        policy_type="自動車", expiry_date="2026-03-20", annual_premium=85000,
        staff_code="S001", contact_method="TEL", contact_info="090-1234-5678",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-A001-2703-0001", renewed_premium=87000,
        upsell_status="なし", lapse_status=0,
        contractor_last_name="高橋", contractor_first_name="○一",
        contractor_first_name_raw="健一", contractor_gender="M",
        contractor_birth_date="1975-03-15",
        contractor_address="東京都港区赤坂2-3-4", contractor_tel="090-1234-5678",
    ),
    dict(
        agency_code="A001", contract_no="M-A001-002", customer_name="田中 裕子",
        renewal_month="2026-04", status="completed",
        policy_number="POL-A001-2604-0001",
        policy_type="火災", expiry_date="2026-04-15", annual_premium=120000,
        staff_code="S001", contact_method="メール", contact_info="tanaka@example.com",
        memo="他社に乗り換え。次回フォロー要", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="落ち",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=1,
        contractor_last_name="田中", contractor_first_name="○子",
        contractor_first_name_raw="裕子", contractor_gender="F",
        contractor_birth_date="1980-07-22",
        contractor_address="東京都渋谷区恵比寿1-5-8", contractor_tel="080-2345-6789",
    ),
    dict(
        agency_code="A001", contract_no="M-A001-003", customer_name="鈴木 一郎",
        renewal_month="2026-05", status="completed",
        policy_number="POL-A001-2605-0001",
        policy_type="自動車", expiry_date="2026-05-10", annual_premium=95000,
        staff_code="S002", contact_method="TEL", contact_info="080-9876-5432",
        memo="事故歴あり。保険料上昇の可能性あり要説明", has_accident=1, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-A001-2605-NEW1", renewed_premium=95000,
        upsell_status="あり", lapse_status=0,
        contractor_last_name="鈴木", contractor_first_name="○郎",
        contractor_first_name_raw="一郎", contractor_gender="M",
        contractor_birth_date="1968-09-10",
        contractor_address="東京都新宿区西新宿3-1-2", contractor_tel="080-9876-5432",
    ),
    dict(
        agency_code="A001", contract_no="M-A001-004", customer_name="山田 直子",
        renewal_month="2026-05", status="pending",
        policy_number="POL-A001-2605-0002",
        policy_type="傷害", expiry_date="2026-05-31", annual_premium=45000,
        staff_code="S002", contact_method="メール", contact_info="yamada@example.com",
        memo="住所変更済。証券送付先確認要", has_accident=0, has_change=1,
        followcall_status="未実施", renewal_status="未対応",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
        contractor_last_name="山田", contractor_first_name="○子",
        contractor_first_name_raw="直子", contractor_gender="F",
        contractor_birth_date="1985-11-30",
        contractor_address="東京都目黒区中目黒4-2-6", contractor_tel="070-3456-7890",
    ),
    dict(
        agency_code="A001", contract_no="M-A001-005", customer_name="中村 浩司",
        renewal_month="2026-06", status="completed",
        policy_number="POL-A001-2606-0001",
        policy_type="火災", expiry_date="2026-06-15", annual_premium=150000,
        staff_code="S001", contact_method="TEL", contact_info="070-1111-2222",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-A001-2606-NEW1", renewed_premium=160000,
        upsell_status="あり", lapse_status=0,
        contractor_last_name="中村", contractor_first_name="○司",
        contractor_first_name_raw="浩司", contractor_gender="M",
        contractor_birth_date="1971-04-05",
        contractor_address="東京都品川区大崎1-8-3", contractor_tel="070-1111-2222",
    ),
    # ── B002 ──────────────────────────────────────────────────
    dict(
        agency_code="B002", contract_no="M-B002-001", customer_name="小林 和子",
        renewal_month="2026-03", status="completed",
        policy_number="POL-B002-2603-0001",
        policy_type="自動車", expiry_date="2026-03-05", annual_premium=78000,
        staff_code="S003", contact_method="TEL", contact_info="090-3333-4444",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-B002-2703-0001", renewed_premium=80000,
        upsell_status="なし", lapse_status=0,
        contractor_last_name="小林", contractor_first_name="○子",
        contractor_first_name_raw="和子", contractor_gender="F",
        contractor_birth_date="1972-08-14",
        contractor_address="大阪府大阪市北区梅田3-1-5", contractor_tel="090-3333-4444",
    ),
    dict(
        agency_code="B002", contract_no="M-B002-002", customer_name="加藤 誠",
        renewal_month="2026-04", status="completed",
        policy_number="POL-B002-2604-0001",
        policy_type="火災", expiry_date="2026-04-01", annual_premium=200000,
        staff_code="S003", contact_method="メール", contact_info="kato@example.com",
        memo="車両も提案済。アップセル成功", has_accident=0, has_change=1,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-B002-2704-0001", renewed_premium=210000,
        upsell_status="あり", lapse_status=0,
        contractor_last_name="加藤", contractor_first_name="○",
        contractor_first_name_raw="誠", contractor_gender="M",
        contractor_birth_date="1978-12-01",
        contractor_address="大阪府大阪市中央区難波2-4-7", contractor_tel="080-4444-5555",
    ),
    dict(
        agency_code="B002", contract_no="M-B002-003", customer_name="吉田 文子",
        renewal_month="2026-05", status="completed",
        policy_number="POL-B002-2605-0001",
        policy_type="傷害", expiry_date="2026-05-15", annual_premium=55000,
        staff_code="S003", contact_method="TEL", contact_info="080-5555-6666",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-B002-2605-NEW1", renewed_premium=85000,
        upsell_status="なし", lapse_status=0,
        contractor_last_name="吉田", contractor_first_name="○子",
        contractor_first_name_raw="文子", contractor_gender="F",
        contractor_birth_date="1983-06-18",
        contractor_address="大阪府大阪市西区靭本町1-6-3", contractor_tel="080-5555-6666",
    ),
    dict(
        agency_code="B002", contract_no="M-B002-004", customer_name="山本 正男",
        renewal_month="2026-05", status="pending",
        policy_number="POL-B002-2605-0002",
        policy_type="自動車", expiry_date="2026-05-25", annual_premium=110000,
        staff_code="S003", contact_method="TEL", contact_info="090-7777-8888",
        memo="事故対応中。修理完了後に更改手続き予定", has_accident=1, has_change=0,
        followcall_status="未実施", renewal_status="未対応",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
        contractor_last_name="山本", contractor_first_name="○男",
        contractor_first_name_raw="正男", contractor_gender="M",
        contractor_birth_date="1965-02-25",
        contractor_address="大阪府吹田市豊津町5-9-2", contractor_tel="090-7777-8888",
    ),
    dict(
        agency_code="B002", contract_no="M-B002-005", customer_name="松本 光子",
        renewal_month="2026-07", status="pending",
        policy_number="POL-B002-2607-0001",
        policy_type="その他", expiry_date="2026-07-01", annual_premium=35000,
        staff_code="S003", contact_method="メール", contact_info="matsumoto@example.com",
        memo="", has_accident=0, has_change=0,
        followcall_status="未実施", renewal_status="未対応",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
        contractor_last_name="松本", contractor_first_name="○子",
        contractor_first_name_raw="光子", contractor_gender="F",
        contractor_birth_date="1990-10-07",
        contractor_address="大阪府豊中市岡町北2-3-8", contractor_tel="070-6666-7777",
    ),
    dict(
        agency_code="B002", contract_no="M-B002-006", customer_name="新田 裕司",
        renewal_month="2026-06", status="completed",
        policy_number="POL-B002-2606-0001",
        policy_type="火災", expiry_date="2026-06-20", annual_premium=100000,
        staff_code="S003", contact_method="TEL", contact_info="090-9999-1111",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-B002-2606-NEW1", renewed_premium=120000,
        upsell_status="あり", lapse_status=0,
        contractor_last_name="新田", contractor_first_name="○司",
        contractor_first_name_raw="裕司", contractor_gender="M",
        contractor_birth_date="1982-03-19",
        contractor_address="大阪府大阪市浪速区難波中1-2-4", contractor_tel="090-9999-1111",
    ),
    # ── C003 ──────────────────────────────────────────────────
    dict(
        agency_code="C003", contract_no="M-C003-001", customer_name="伊藤 憲一",
        renewal_month="2026-03", status="completed",
        policy_number="POL-C003-2603-0001",
        policy_type="自動車", expiry_date="2026-03-31", annual_premium=92000,
        staff_code="S004", contact_method="TEL", contact_info="090-1010-2020",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-C003-2703-0001", renewed_premium=94000,
        upsell_status="なし", lapse_status=0,
        contractor_last_name="伊藤", contractor_first_name="○一",
        contractor_first_name_raw="憲一", contractor_gender="M",
        contractor_birth_date="1969-07-11",
        contractor_address="愛知県名古屋市中区錦3-4-5", contractor_tel="090-1010-2020",
    ),
    dict(
        agency_code="C003", contract_no="M-C003-002", customer_name="渡辺 恵子",
        renewal_month="2026-04", status="completed",
        policy_number="POL-C003-2604-0001",
        policy_type="火災", expiry_date="2026-04-20", annual_premium=180000,
        staff_code="S004", contact_method="メール", contact_info="watanabe@example.com",
        memo="競合他社に流れた。価格差15%の模様", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="落ち",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=1,
        contractor_last_name="渡辺", contractor_first_name="○子",
        contractor_first_name_raw="恵子", contractor_gender="F",
        contractor_birth_date="1976-05-28",
        contractor_address="愛知県名古屋市昭和区広路町3-2-1", contractor_tel="080-2020-3030",
    ),
    dict(
        agency_code="C003", contract_no="M-C003-003", customer_name="木村 隆",
        renewal_month="2026-05", status="completed",
        policy_number="POL-C003-2605-0001",
        policy_type="自動車", expiry_date="2026-05-05", annual_premium=72000,
        staff_code="S005", contact_method="TEL", contact_info="080-3030-4040",
        memo="", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-C003-2605-NEW1", renewed_premium=75000,
        upsell_status="なし", lapse_status=0,
        contractor_last_name="木村", contractor_first_name="○",
        contractor_first_name_raw="隆", contractor_gender="M",
        contractor_birth_date="1963-08-03",
        contractor_address="愛知県名古屋市守山区瀬古1-7-9", contractor_tel="080-3030-4040",
    ),
    dict(
        agency_code="C003", contract_no="M-C003-004", customer_name="清水 久美子",
        renewal_month="2026-05", status="pending",
        policy_number="POL-C003-2605-0002",
        policy_type="傷害", expiry_date="2026-05-28", annual_premium=48000,
        staff_code="S005", contact_method="メール", contact_info="shimizu@example.com",
        memo="", has_accident=0, has_change=1,
        followcall_status="未実施", renewal_status="未対応",
        renewed_policy_number=None, renewed_premium=None,
        upsell_status="なし", lapse_status=0,
        contractor_last_name="清水", contractor_first_name="○美子",
        contractor_first_name_raw="久美子", contractor_gender="F",
        contractor_birth_date="1987-01-16",
        contractor_address="愛知県名古屋市天白区植田西2-5-3", contractor_tel="070-4040-5050",
    ),
    dict(
        agency_code="C003", contract_no="M-C003-005", customer_name="高橋 浩司",
        renewal_month="2026-06", status="completed",
        policy_number="POL-C003-2606-0001",
        policy_type="火災", expiry_date="2026-06-30", annual_premium=225000,
        staff_code="S004", contact_method="TEL", contact_info="070-5050-6060",
        memo="大口。年払い。慎重に対応", has_accident=0, has_change=0,
        followcall_status="実施済", renewal_status="更改済",
        renewed_policy_number="POL-C003-2606-NEW1", renewed_premium=95000,
        upsell_status="あり", lapse_status=0,
        contractor_last_name="高橋", contractor_first_name="○司",
        contractor_first_name_raw="浩司", contractor_gender="M",
        contractor_birth_date="1958-12-20",
        contractor_address="愛知県名古屋市中川区高畑3-8-6", contractor_tel="070-5050-6060",
    ),
]

NOTICE_TYPES = ["はがき", "はがき", "冊子", "冊子", "はがき"]

# ── 種目マスタ ────────────────────────────────────────────────────
POLICY_TYPES_MASTER = [
    ("AUTO",      "自動車",         1),
    ("FIRE",      "火災",           2),
    ("INJURY",    "傷害",           3),
    ("JIBAI",     "自賠責",         4),
    ("LIABILITY", "賠償責任",       5),
    ("CYBER",     "サイバーリスク", 6),
    ("INCOME",    "所得補償",       7),
]

# ── グループA顧客（10名）group_code="A" ────────────────────────────
# ①②は複数代理店にまたがる名寄せ統合デモ用
# グループB・Cに同姓同名を登録（別グループ→別顧客のデモ）
CUSTOMERS_GROUP_A = [
    # ① 羽生 結弦：A001に自動車・自賠責、A002に火災 → グループA内で名寄せ統合→1件
    dict(
        group_code="A",
        last_name="羽生", first_name_raw="結弦", gender="M", birth_date="1994-12-07",
        address="東京都港区赤坂1-1-1", tel="090-1207-9400", email="hanyu.yuzuru@example.com",
        family_structure="単身", hobbies="フィギュアスケート、将棋", assets_info="投資資産あり、プロスケーター",
        contracts=[
            dict(agency_code="A001", policy_type="自動車",  annual_premium=135000, expiry_date="2027-12-07", staff_code="S001"),
            dict(agency_code="A001", policy_type="自賠責",  annual_premium=19000,  expiry_date="2027-12-07", staff_code="S001"),
            dict(agency_code="A002", policy_type="火災",    annual_premium=98000,  expiry_date="2027-06-30", staff_code="S001"),
        ]
    ),
    # ② 大谷 翔平：A001に自動車、A003に傷害・賠償責任 → グループA内で名寄せ統合→1件
    dict(
        group_code="A",
        last_name="大谷", first_name_raw="翔平", gender="M", birth_date="1994-07-05",
        address="東京都千代田区丸の内2-3-4", tel="090-0705-9400", email="ohtani.shohei@example.com",
        family_structure="夫婦のみ", hobbies="野球、読書", assets_info="高額資産家、プロ野球選手",
        contracts=[
            dict(agency_code="A001", policy_type="自動車",  annual_premium=158000, expiry_date="2027-07-05", staff_code="S002"),
            dict(agency_code="A003", policy_type="傷害",    annual_premium=68000,  expiry_date="2027-04-30", staff_code="S001"),
            dict(agency_code="A003", policy_type="賠償責任", annual_premium=75000, expiry_date="2027-04-30", staff_code="S001"),
        ]
    ),
    # ③ 山本 太一：A001に自動車・火災・自賠責
    dict(
        group_code="A",
        last_name="山本", first_name_raw="太一", gender="M", birth_date="1975-08-12",
        address="東京都港区六本木3-2-1", tel="090-2345-6789", email="yamamoto.taichi@example.com",
        family_structure="夫婦子あり", hobbies="ゴルフ、読書", assets_info="持家（ローン残8年）、車2台保有",
        contracts=[
            dict(agency_code="A001", policy_type="自動車", annual_premium=125000, expiry_date="2027-08-31", staff_code="S001"),
            dict(agency_code="A001", policy_type="火災",   annual_premium=88000,  expiry_date="2027-09-30", staff_code="S001"),
            dict(agency_code="A001", policy_type="自賠責", annual_premium=18500,  expiry_date="2027-08-31", staff_code="S001"),
        ]
    ),
    # ④ 白石 麻衣：A001に自動車・傷害
    dict(
        group_code="A",
        last_name="白石", first_name_raw="麻衣", gender="F", birth_date="1992-08-20",
        address="東京都渋谷区神南1-5-2", tel="080-3456-7890", email="shiraishi.mai@example.com",
        family_structure="単身", hobbies="ヨガ、映画鑑賞", assets_info="賃貸マンション、車1台保有",
        contracts=[
            dict(agency_code="A001", policy_type="自動車", annual_premium=98000, expiry_date="2027-07-31", staff_code="S002"),
            dict(agency_code="A001", policy_type="傷害",   annual_premium=42000, expiry_date="2027-07-31", staff_code="S002"),
        ]
    ),
    # ⑤ 坂口 健太：A001に火災・賠償責任・サイバーリスク
    dict(
        group_code="A",
        last_name="坂口", first_name_raw="健太", gender="M", birth_date="1985-03-25",
        address="東京都新宿区西新宿7-8-9", tel="070-4567-8901", email="sakaguchi.kenta@example.com",
        family_structure="夫婦のみ", hobbies="カメラ、旅行", assets_info="持家（完済）、自営業（IT系）",
        contracts=[
            dict(agency_code="A001", policy_type="火災",           annual_premium=135000, expiry_date="2027-03-31", staff_code="S001"),
            dict(agency_code="A001", policy_type="賠償責任",       annual_premium=62000,  expiry_date="2027-03-31", staff_code="S001"),
            dict(agency_code="A001", policy_type="サイバーリスク", annual_premium=75000,  expiry_date="2027-03-31", staff_code="S001"),
        ]
    ),
    # ⑥ 森川 悠介：A001に自動車のみ
    dict(
        group_code="A",
        last_name="森川", first_name_raw="悠介", gender="M", birth_date="1998-11-05",
        address="東京都世田谷区下北沢2-1-3", tel="090-5678-9012", email="morikawa.yusuke@example.com",
        family_structure="単身", hobbies="バンド活動、スノーボード", assets_info="賃貸アパート、バイク1台・車1台保有",
        contracts=[
            dict(agency_code="A001", policy_type="自動車", annual_premium=85000, expiry_date="2027-10-31", staff_code="S002"),
        ]
    ),
    # ⑦ 吉田 幸子：A001に火災・所得補償
    dict(
        group_code="A",
        last_name="吉田", first_name_raw="幸子", gender="F", birth_date="1981-06-17",
        address="東京都目黒区自由が丘1-3-5", tel="080-6789-0123", email="yoshida.sachiko@example.com",
        family_structure="子あり（小学生）", hobbies="料理、ガーデニング", assets_info="持家（ローン残15年）、専業主婦",
        contracts=[
            dict(agency_code="A001", policy_type="火災",   annual_premium=195000, expiry_date="2027-06-30", staff_code="S001"),
            dict(agency_code="A001", policy_type="所得補償", annual_premium=98000, expiry_date="2027-06-30", staff_code="S001"),
        ]
    ),
    # ⑧ 田辺 大輔：A001に自動車・火災・傷害・自賠責
    dict(
        group_code="A",
        last_name="田辺", first_name_raw="大輔", gender="M", birth_date="1973-09-08",
        address="東京都品川区大井1-12-5", tel="090-7890-1234", email="tanabe.daisuke@example.com",
        family_structure="夫婦子あり（2名）", hobbies="釣り、野球観戦", assets_info="持家、車3台保有、中小企業経営者",
        contracts=[
            dict(agency_code="A001", policy_type="自動車", annual_premium=148000, expiry_date="2027-09-30", staff_code="S002"),
            dict(agency_code="A001", policy_type="火災",   annual_premium=220000, expiry_date="2027-09-30", staff_code="S002"),
            dict(agency_code="A001", policy_type="傷害",   annual_premium=65000,  expiry_date="2027-09-30", staff_code="S002"),
            dict(agency_code="A001", policy_type="自賠責", annual_premium=19000,  expiry_date="2027-09-30", staff_code="S002"),
        ]
    ),
    # ⑨ 宮本 美穂：A002に賠償責任・サイバーリスク
    dict(
        group_code="A",
        last_name="宮本", first_name_raw="美穂", gender="F", birth_date="1987-04-30",
        address="東京都中野区中野3-7-2", tel="070-8901-2345", email="miyamoto.miho@example.com",
        family_structure="夫婦のみ", hobbies="ハイキング、陶芸", assets_info="賃貸マンション、フリーランスデザイナー",
        contracts=[
            dict(agency_code="A002", policy_type="賠償責任",       annual_premium=48000, expiry_date="2027-04-30", staff_code="S001"),
            dict(agency_code="A002", policy_type="サイバーリスク", annual_premium=62000, expiry_date="2027-04-30", staff_code="S001"),
        ]
    ),
    # ⑩ 栗原 勇太：A003に自動車・サイバーリスク
    dict(
        group_code="A",
        last_name="栗原", first_name_raw="勇太", gender="M", birth_date="1994-02-14",
        address="東京都豊島区池袋2-4-8", tel="090-9012-3456", email="kurihara.yuta@example.com",
        family_structure="単身", hobbies="プログラミング、e-Sports", assets_info="賃貸マンション、ITエンジニア",
        contracts=[
            dict(agency_code="A003", policy_type="自動車",         annual_premium=92000, expiry_date="2027-02-28", staff_code="S002"),
            dict(agency_code="A003", policy_type="サイバーリスク", annual_premium=85000, expiry_date="2027-02-28", staff_code="S002"),
        ]
    ),
]

# ── グループB顧客（8名）group_code="B" ────────────────────────────
# ①②は羽生・大谷と同姓同名だが別グループ→別顧客（デモ用）
CUSTOMERS_GROUP_B = [
    # ① 羽生 結弦（B002）：グループBの別顧客として登録
    dict(
        group_code="B",
        last_name="羽生", first_name_raw="結弦", gender="M", birth_date="1994-12-07",
        address="大阪府大阪市北区梅田1-2-3", tel="080-1207-0001", email="hanyu.b@example.com",
        family_structure="単身", hobbies="フィギュアスケート、将棋", assets_info="投資資産あり",
        contracts=[
            dict(agency_code="B002", policy_type="火災", annual_premium=98000, expiry_date="2027-06-30", staff_code="S003"),
        ]
    ),
    # ② 大谷 翔平（B002）：グループBの別顧客として登録
    dict(
        group_code="B",
        last_name="大谷", first_name_raw="翔平", gender="M", birth_date="1994-07-05",
        address="大阪府大阪市中央区心斎橋1-1-1", tel="080-0705-0001", email="ohtani.b@example.com",
        family_structure="夫婦のみ", hobbies="野球、読書", assets_info="高額資産家",
        contracts=[
            dict(agency_code="B002", policy_type="傷害",   annual_premium=68000, expiry_date="2027-04-30", staff_code="S003"),
            dict(agency_code="B002", policy_type="賠償責任", annual_premium=75000, expiry_date="2027-04-30", staff_code="S003"),
        ]
    ),
    # ③ 菊地 裕太：B001に自動車・火災・傷害
    dict(
        group_code="B",
        last_name="菊地", first_name_raw="裕太", gender="M", birth_date="1984-05-20",
        address="大阪府大阪市北区梅田2-5-3", tel="090-2345-1111", email="kikuchi.yuta@example.com",
        family_structure="夫婦子あり", hobbies="バスケットボール、料理", assets_info="持家、会社員（製造業）",
        contracts=[
            dict(agency_code="B001", policy_type="自動車", annual_premium=110000, expiry_date="2027-05-31", staff_code="S003"),
            dict(agency_code="B001", policy_type="火災",   annual_premium=145000, expiry_date="2027-05-31", staff_code="S003"),
            dict(agency_code="B001", policy_type="傷害",   annual_premium=48000,  expiry_date="2027-05-31", staff_code="S003"),
        ]
    ),
    # ④ 深川 圭子：B002に自動車・所得補償
    dict(
        group_code="B",
        last_name="深川", first_name_raw="圭子", gender="F", birth_date="1991-09-14",
        address="大阪府大阪市西区江戸堀1-7-4", tel="080-3456-2222", email="fukagawa.keiko@example.com",
        family_structure="単身", hobbies="ピアノ、読書", assets_info="賃貸マンション、会社員",
        contracts=[
            dict(agency_code="B002", policy_type="自動車",  annual_premium=88000,  expiry_date="2027-09-30", staff_code="S003"),
            dict(agency_code="B002", policy_type="所得補償", annual_premium=105000, expiry_date="2027-09-30", staff_code="S003"),
        ]
    ),
    # ⑤ 尾形 拓也：B002に火災・サイバーリスク・賠償責任
    dict(
        group_code="B",
        last_name="尾形", first_name_raw="拓也", gender="M", birth_date="1976-12-03",
        address="大阪府大阪市中央区谷町4-3-8", tel="070-4567-3333", email="ogata.takuya@example.com",
        family_structure="夫婦のみ", hobbies="クラシック音楽、美術鑑賞", assets_info="持家（完済）、小規模法人代表",
        contracts=[
            dict(agency_code="B002", policy_type="火災",           annual_premium=180000, expiry_date="2027-12-31", staff_code="S003"),
            dict(agency_code="B002", policy_type="サイバーリスク", annual_premium=95000,  expiry_date="2027-12-31", staff_code="S003"),
            dict(agency_code="B002", policy_type="賠償責任",       annual_premium=72000,  expiry_date="2027-12-31", staff_code="S003"),
        ]
    ),
    # ⑥ 浜田 奈美：B001に自動車・傷害・自賠責
    dict(
        group_code="B",
        last_name="浜田", first_name_raw="奈美", gender="F", birth_date="1988-03-17",
        address="大阪府吹田市江坂町2-9-5", tel="090-5678-4444", email="hamada.nami@example.com",
        family_structure="夫婦子あり（1名）", hobbies="テニス、子育て", assets_info="持家、パート（医療事務）",
        contracts=[
            dict(agency_code="B001", policy_type="自動車", annual_premium=95000, expiry_date="2027-03-31", staff_code="S003"),
            dict(agency_code="B001", policy_type="傷害",   annual_premium=38000, expiry_date="2027-03-31", staff_code="S003"),
            dict(agency_code="B001", policy_type="自賠責", annual_premium=16500, expiry_date="2027-03-31", staff_code="S003"),
        ]
    ),
    # ⑦ 成田 雄介：B002に自動車・火災・自賠責・サイバーリスク
    dict(
        group_code="B",
        last_name="成田", first_name_raw="雄介", gender="M", birth_date="1982-11-09",
        address="大阪府豊中市庄内西町3-4-7", tel="090-7890-6666", email="narita.yusuke@example.com",
        family_structure="夫婦子あり（2名）", hobbies="車いじり、キャンプ", assets_info="持家、車3台保有、整備士",
        contracts=[
            dict(agency_code="B002", policy_type="自動車",         annual_premium=132000, expiry_date="2027-11-30", staff_code="S003"),
            dict(agency_code="B002", policy_type="火災",           annual_premium=158000, expiry_date="2027-11-30", staff_code="S003"),
            dict(agency_code="B002", policy_type="自賠責",         annual_premium=18000,  expiry_date="2027-11-30", staff_code="S003"),
            dict(agency_code="B002", policy_type="サイバーリスク", annual_premium=65000,  expiry_date="2027-11-30", staff_code="S003"),
        ]
    ),
    # ⑧ 岩佐 玲奈：B001に賠償責任・所得補償
    dict(
        group_code="B",
        last_name="岩佐", first_name_raw="玲奈", gender="F", birth_date="1979-06-25",
        address="大阪府高槻市城西町1-5-3", tel="070-8901-7777", email="iwasa.reina@example.com",
        family_structure="子あり（高校生）", hobbies="ウォーキング、絵画", assets_info="賃貸戸建、パート（小売）",
        contracts=[
            dict(agency_code="B001", policy_type="賠償責任",  annual_premium=52000, expiry_date="2027-06-30", staff_code="S003"),
            dict(agency_code="B001", policy_type="所得補償",  annual_premium=88000, expiry_date="2027-06-30", staff_code="S003"),
        ]
    ),
]

# ── グループC顧客（8名）group_code="C" ────────────────────────────
CUSTOMERS_GROUP_C = [
    # ① 増田 隆雄：C001に自動車・火災・賠償責任
    dict(
        group_code="C",
        last_name="増田", first_name_raw="隆雄", gender="M", birth_date="1985-04-04",
        address="愛知県名古屋市中区錦2-6-3", tel="090-2345-9999", email="masuda.takao@example.com",
        family_structure="夫婦子あり（2名）", hobbies="野球、DIY", assets_info="持家（ローン残10年）、会社員（建設）",
        contracts=[
            dict(agency_code="C001", policy_type="自動車",  annual_premium=118000, expiry_date="2027-04-30", staff_code="S004"),
            dict(agency_code="C001", policy_type="火災",    annual_premium=172000, expiry_date="2027-04-30", staff_code="S004"),
            dict(agency_code="C001", policy_type="賠償責任", annual_premium=58000, expiry_date="2027-04-30", staff_code="S004"),
        ]
    ),
    # ② 沖田 倫子：C003に傷害・所得補償
    dict(
        group_code="C",
        last_name="沖田", first_name_raw="倫子", gender="F", birth_date="1992-08-11",
        address="愛知県名古屋市千種区覚王山1-3-8", tel="080-3456-0001", email="okita.noriko@example.com",
        family_structure="単身", hobbies="ヨガ、旅行", assets_info="賃貸、会社員（医療）",
        contracts=[
            dict(agency_code="C003", policy_type="傷害",   annual_premium=45000,  expiry_date="2027-08-31", staff_code="S004"),
            dict(agency_code="C003", policy_type="所得補償", annual_premium=118000, expiry_date="2027-08-31", staff_code="S004"),
        ]
    ),
    # ③ 谷口 和彦：C001に自動車・自賠責・サイバーリスク
    dict(
        group_code="C",
        last_name="谷口", first_name_raw="和彦", gender="M", birth_date="1974-06-19",
        address="愛知県名古屋市守山区大森5-9-2", tel="070-4567-0002", email="taniguchi.kazuhiko@example.com",
        family_structure="夫婦子あり（3名）", hobbies="釣り、ゴルフ", assets_info="持家（完済）、車2台、自営業（飲食）",
        contracts=[
            dict(agency_code="C001", policy_type="自動車",         annual_premium=98000, expiry_date="2027-06-30", staff_code="S005"),
            dict(agency_code="C001", policy_type="自賠責",         annual_premium=17000, expiry_date="2027-06-30", staff_code="S005"),
            dict(agency_code="C001", policy_type="サイバーリスク", annual_premium=82000, expiry_date="2027-06-30", staff_code="S005"),
        ]
    ),
    # ④ 黒木 華奈：C003に火災・賠償責任
    dict(
        group_code="C",
        last_name="黒木", first_name_raw="華奈", gender="F", birth_date="1988-01-30",
        address="愛知県名古屋市昭和区広路本町2-1-4", tel="090-5678-0003", email="kuroki.kana@example.com",
        family_structure="夫婦のみ", hobbies="カフェ巡り、スポーツ観戦", assets_info="賃貸マンション、会社員（広告）",
        contracts=[
            dict(agency_code="C003", policy_type="火災",   annual_premium=95000, expiry_date="2027-01-31", staff_code="S004"),
            dict(agency_code="C003", policy_type="賠償責任", annual_premium=44000, expiry_date="2027-01-31", staff_code="S004"),
        ]
    ),
    # ⑤ 松田 翔太：C003に自動車のみ
    dict(
        group_code="C",
        last_name="松田", first_name_raw="翔太", gender="M", birth_date="1997-12-15",
        address="愛知県名古屋市名東区社が丘3-5-7", tel="080-6789-0004", email="matsuda.shota@example.com",
        family_structure="単身", hobbies="バイク、ゲーム", assets_info="賃貸アパート、バイク2台・車1台保有",
        contracts=[
            dict(agency_code="C003", policy_type="自動車", annual_premium=82000, expiry_date="2027-12-31", staff_code="S005"),
        ]
    ),
    # ⑥ 藤本 美紀：C001に自動車・火災・傷害・所得補償
    dict(
        group_code="C",
        last_name="藤本", first_name_raw="美紀", gender="F", birth_date="1980-09-07",
        address="愛知県名古屋市天白区平針2-8-6", tel="090-7890-0005", email="fujimoto.miki@example.com",
        family_structure="子あり（小学生・中学生）", hobbies="料理、バドミントン", assets_info="持家（ローン残18年）、パート（事務）",
        contracts=[
            dict(agency_code="C001", policy_type="自動車",  annual_premium=112000, expiry_date="2027-09-30", staff_code="S004"),
            dict(agency_code="C001", policy_type="火災",    annual_premium=185000, expiry_date="2027-09-30", staff_code="S004"),
            dict(agency_code="C001", policy_type="傷害",    annual_premium=52000,  expiry_date="2027-09-30", staff_code="S004"),
            dict(agency_code="C001", policy_type="所得補償", annual_premium=92000, expiry_date="2027-09-30", staff_code="S004"),
        ]
    ),
    # ⑦ 今井 義人：C003に賠償責任・サイバーリスク
    dict(
        group_code="C",
        last_name="今井", first_name_raw="義人", gender="M", birth_date="1975-03-22",
        address="愛知県名古屋市西区城西4-3-1", tel="070-8901-0006", email="imai.yoshito@example.com",
        family_structure="夫婦のみ", hobbies="温泉旅行、将棋", assets_info="持家（完済）、定年退職後・年金受給中",
        contracts=[
            dict(agency_code="C003", policy_type="賠償責任",       annual_premium=48000, expiry_date="2027-03-31", staff_code="S005"),
            dict(agency_code="C003", policy_type="サイバーリスク", annual_premium=55000, expiry_date="2027-03-31", staff_code="S005"),
        ]
    ),
    # ⑧ 野村 栞菜：C001に自動車・火災・自賠責
    dict(
        group_code="C",
        last_name="野村", first_name_raw="栞菜", gender="F", birth_date="1993-11-28",
        address="愛知県名古屋市緑区鳴海町3-12-9", tel="090-9012-0007", email="nomura.kanna@example.com",
        family_structure="単身", hobbies="ダンス、ネットショッピング", assets_info="賃貸マンション、会社員（小売）",
        contracts=[
            dict(agency_code="C001", policy_type="自動車", annual_premium=88000,  expiry_date="2027-11-30", staff_code="S004"),
            dict(agency_code="C001", policy_type="火災",   annual_premium=125000, expiry_date="2027-11-30", staff_code="S004"),
            dict(agency_code="C001", policy_type="自賠責", annual_premium=17500,  expiry_date="2027-11-30", staff_code="S004"),
        ]
    ),
]

ALL_CUSTOMER_GROUPS = [CUSTOMERS_GROUP_A, CUSTOMERS_GROUP_B, CUSTOMERS_GROUP_C]


def make_match_key(group_code: str, gender: str, birth_date: str, first_name_raw: str) -> str:
    """名寄せキー（group_code + gender + birth_date + first_name_raw のSHA256ハッシュ）"""
    raw = f"{group_code}|{gender}|{birth_date}|{first_name_raw}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def mask_first_name(first_name_raw: str) -> str:
    """名の先頭1文字を○でマスクする"""
    if len(first_name_raw) <= 1:
        return "○"
    return "○" + first_name_raw[1:]


def find_same_customer(conn, group_code: str, gender: str, birth_date: str,
                       first_name: str, tel: str, address: str):
    """
    同一group_code内で必須3項目（性別・生年月日・名）が一致
    AND（電話番号一致 OR 住所一致）の場合に既存customer_idを返す。
    一致なければNoneを返す。
    """
    rows = conn.execute("""
        SELECT customer_id FROM customers
        WHERE group_code = ?
          AND gender = ?
          AND birth_date = ?
          AND first_name_raw = ?
          AND (
            (tel     IS NOT NULL AND tel     != '' AND tel     = ?)
            OR
            (address IS NOT NULL AND address != '' AND address = ?)
          )
    """, (group_code, gender, birth_date, first_name, tel or "", address or "")).fetchall()
    return rows[0]["customer_id"] if rows else None


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = OFF")

        # テーブルを全削除（依存関係の逆順）
        for tbl in ("maturity_notices", "accidents", "role_permissions",
                    "contracts", "customers", "policy_types",
                    "users", "features", "roles",
                    "staff_users", "staff_roles", "agencies"):
            cur.execute(f"DROP TABLE IF EXISTS {tbl}")

        # ── 代理店マスタ ─────────────────────────────────────────
        cur.execute("""
            CREATE TABLE agencies (
                agency_id   INTEGER  PRIMARY KEY AUTOINCREMENT,
                agency_code TEXT     NOT NULL UNIQUE,
                agency_name TEXT     NOT NULL,
                address     TEXT,
                tel         TEXT,
                email       TEXT,
                group_code  TEXT     NOT NULL,
                buka_code   TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for a in AGENCIES:
            cur.execute("""
                INSERT INTO agencies (agency_id, agency_code, agency_name, address, tel, email, group_code, buka_code)
                VALUES (:agency_id,:agency_code,:agency_name,:address,:tel,:email,:group_code,:buka_code)
            """, a)
        print(f"  代理店: {len(AGENCIES)}件")

        # ── 社員ロールマスタ ─────────────────────────────────────
        cur.execute("""
            CREATE TABLE staff_roles (
                role_id     INTEGER PRIMARY KEY,
                role_name   TEXT    NOT NULL,
                description TEXT
            )
        """)
        for sr in STAFF_ROLES:
            cur.execute("INSERT INTO staff_roles VALUES (:role_id,:role_name,:description)", sr)
        print(f"  社員ロール: {len(STAFF_ROLES)}件")

        # ── 社員ユーザーテーブル ──────────────────────────────────
        cur.execute("""
            CREATE TABLE staff_users (
                staff_id    INTEGER  PRIMARY KEY AUTOINCREMENT,
                staff_code  TEXT     NOT NULL UNIQUE,
                password    TEXT     NOT NULL,
                name        TEXT     NOT NULL,
                buka_code   TEXT     NOT NULL,
                role_id     INTEGER  NOT NULL,
                is_active   INTEGER  DEFAULT 1,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES staff_roles(role_id)
            )
        """)
        for su in STAFF_USERS:
            hashed = bcrypt.hashpw(su["password"].encode(), bcrypt.gensalt()).decode()
            cur.execute("""
                INSERT INTO staff_users (staff_code, password, name, buka_code, role_id, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (su["staff_code"], hashed, su["name"], su["buka_code"], su["role_id"], su["is_active"]))
            role_name = STAFF_ROLES[su["role_id"] - 1]["role_name"]
            print(f"  社員ユーザー: {su['staff_code']} {su['name']} ({role_name})")

        # ── 代理店ロールマスタ ───────────────────────────────────
        cur.execute("""
            CREATE TABLE roles (
                role_id     INTEGER PRIMARY KEY,
                role_name   TEXT    NOT NULL,
                description TEXT
            )
        """)
        for r in ROLES:
            cur.execute("INSERT INTO roles VALUES (:role_id,:role_name,:description)", r)
        print(f"  代理店ロール: {len(ROLES)}件")

        # ── 機能マスタ ────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE features (
                feature_code TEXT PRIMARY KEY,
                feature_name TEXT NOT NULL,
                description  TEXT
            )
        """)
        for f in FEATURES:
            cur.execute("INSERT INTO features VALUES (:feature_code,:feature_name,:description)", f)
        print(f"  機能: {len(FEATURES)}件")

        # ── ロール×機能 ───────────────────────────────────────────
        cur.execute("""
            CREATE TABLE role_permissions (
                role_id      INTEGER NOT NULL,
                feature_code TEXT    NOT NULL,
                PRIMARY KEY (role_id, feature_code),
                FOREIGN KEY (role_id)      REFERENCES roles(role_id),
                FOREIGN KEY (feature_code) REFERENCES features(feature_code)
            )
        """)
        for rp in ROLE_PERMISSIONS:
            cur.execute("INSERT INTO role_permissions VALUES (?, ?)", rp)
        print(f"  権限マッピング: {len(ROLE_PERMISSIONS)}件")

        # ── 代理店ユーザーテーブル ───────────────────────────────
        cur.execute("""
            CREATE TABLE users (
                id            INTEGER  PRIMARY KEY AUTOINCREMENT,
                agency_code   TEXT     NOT NULL,
                agency_id     INTEGER,
                role_id       INTEGER,
                login_id      TEXT     NOT NULL,
                password_hash TEXT     NOT NULL,
                name          TEXT     NOT NULL,
                is_active     INTEGER  DEFAULT 1,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(agency_code, login_id),
                FOREIGN KEY (agency_id) REFERENCES agencies(agency_id),
                FOREIGN KEY (role_id)   REFERENCES roles(role_id)
            )
        """)
        for u in DUMMY_USERS:
            hashed = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt()).decode()
            cur.execute("""
                INSERT INTO users (agency_code, agency_id, role_id, login_id, password_hash, name, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (u["agency_code"], u["agency_id"], u["role_id"],
                  u["login_id"], hashed, u["name"], u["is_active"]))
            role_name = ROLES[u["role_id"] - 1]["role_name"]
            print(f"  代理店ユーザー: [{u['agency_code']}] {u['login_id']} ({role_name})")

        # ── 種目マスタ（policy_types）────────────────────────────
        cur.execute("""
            CREATE TABLE policy_types (
                type_code     TEXT    PRIMARY KEY,
                type_name     TEXT    NOT NULL,
                display_order INTEGER NOT NULL
            )
        """)
        for tc, tn, do in POLICY_TYPES_MASTER:
            cur.execute("INSERT INTO policy_types VALUES (?, ?, ?)", (tc, tn, do))
        print(f"  種目マスタ: {len(POLICY_TYPES_MASTER)}件")

        # ── 顧客マスタ（group_codeを上位キーとして管理）──────────
        # UNIQUE(group_code, match_key)：同一グループ内で同一人物は1件のみ
        cur.execute("""
            CREATE TABLE customers (
                customer_id      INTEGER  PRIMARY KEY AUTOINCREMENT,
                group_code       TEXT     NOT NULL,
                last_name        TEXT     NOT NULL,
                first_name       TEXT     NOT NULL,
                first_name_raw   TEXT     NOT NULL,
                gender           TEXT     CHECK(gender IN ('M','F')),
                birth_date       TEXT,
                address          TEXT,
                tel              TEXT,
                email            TEXT,
                family_structure TEXT,
                hobbies          TEXT,
                assets_info      TEXT,
                match_key        TEXT     NOT NULL,
                created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_code, match_key)
            )
        """)

        # ── contractsテーブル（顧客管理項目追加）────────────────
        cur.execute("""
            CREATE TABLE contracts (
                id                    INTEGER  PRIMARY KEY AUTOINCREMENT,
                agency_code           TEXT     NOT NULL,
                contract_no           TEXT     NOT NULL UNIQUE,
                customer_name         TEXT     NOT NULL,
                renewal_month         TEXT     NOT NULL,
                status                TEXT     NOT NULL CHECK(status IN ('completed','pending')),
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
                created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
                linked_customer_id        INTEGER  REFERENCES customers(customer_id),
                contractor_last_name      TEXT,
                contractor_first_name     TEXT,
                contractor_first_name_raw TEXT,
                contractor_gender         TEXT,
                contractor_birth_date     TEXT,
                contractor_address        TEXT,
                contractor_tel            TEXT
            )
        """)

        # ── maturity_noticesテーブル ──────────────────────────────
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

        # ── 事故情報テーブル ──────────────────────────────────────
        cur.execute("""
            CREATE TABLE accidents (
                accident_id   INTEGER  PRIMARY KEY AUTOINCREMENT,
                contract_no   TEXT     NOT NULL,
                report_date   DATE     NOT NULL,
                accident_type TEXT,
                status        TEXT,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for ac in ACCIDENTS:
            cur.execute("""
                INSERT INTO accidents (contract_no, report_date, accident_type, status)
                VALUES (:contract_no,:report_date,:accident_type,:status)
            """, ac)
        print(f"  事故データ: {len(ACCIDENTS)}件")

        # ── ダッシュボード用 サンプル契約（1449件）────────────────
        total_dash = 0
        total_notices = 0
        for agency_code, month, completed, pending in CONTRACT_CONFIG:
            seq = 0
            for sts, cnt, r_sts, fc_sts in [
                ("completed", completed, "更改済", "実施済"),
                ("pending",   pending,   "未対応", "未実施"),
            ]:
                for _ in range(cnt):
                    expiry_date = f"{month}-15"
                    method, info = rand_contact()
                    premium = random.choice(range(45000, 201000, 1000))
                    p_type  = random.choice(POLICY_TYPES)
                    s_code  = random.choice(STAFF_CODES_ALL)
                    n_type  = random.choice(NOTICE_TYPES_ALL)
                    n_date  = notice_date(expiry_date)
                    cname = make_name(seq)
                    ci    = make_contractor_info(cname, agency_code)
                    cur.execute("""
                        INSERT INTO contracts
                        (agency_code, contract_no, customer_name, renewal_month, status,
                         expiry_date, renewal_status, followcall_status,
                         policy_type, staff_code, contact_method, contact_info, annual_premium,
                         contractor_last_name, contractor_first_name, contractor_first_name_raw,
                         contractor_gender, contractor_birth_date,
                         contractor_address, contractor_tel)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (agency_code, f"{agency_code}-{month}-{seq:04d}", cname,
                          month, sts, expiry_date, r_sts, fc_sts,
                          p_type, s_code, method, info, premium,
                          ci["contractor_last_name"], ci["contractor_first_name"],
                          ci["contractor_first_name_raw"], ci["contractor_gender"],
                          ci["contractor_birth_date"], ci["contractor_address"],
                          ci["contractor_tel"]))
                    cid = cur.lastrowid
                    cur.execute("""
                        INSERT INTO maturity_notices (contract_id, notice_date, notice_type)
                        VALUES (?, ?, ?)
                    """, (cid, n_date, n_type))
                    total_notices += 1
                    seq += 1
            total_dash += completed + pending
        print(f"  契約（ダッシュボード用）: {total_dash}件 + notices: {total_notices}件")

        # ── 満期管理用 サンプル契約（16件）──────────────────────
        for mc in MATURITY_CONTRACTS:
            cur.execute("""
                INSERT INTO contracts (
                    agency_code, contract_no, customer_name, renewal_month, status,
                    policy_number, policy_type, expiry_date, annual_premium,
                    staff_code, contact_method, contact_info, memo,
                    has_accident, has_change, followcall_status, renewal_status,
                    renewed_policy_number, renewed_premium, upsell_status, lapse_status,
                    contractor_last_name, contractor_first_name, contractor_first_name_raw,
                    contractor_gender, contractor_birth_date,
                    contractor_address, contractor_tel
                ) VALUES (
                    :agency_code,:contract_no,:customer_name,:renewal_month,:status,
                    :policy_number,:policy_type,:expiry_date,:annual_premium,
                    :staff_code,:contact_method,:contact_info,:memo,
                    :has_accident,:has_change,:followcall_status,:renewal_status,
                    :renewed_policy_number,:renewed_premium,:upsell_status,:lapse_status,
                    :contractor_last_name,:contractor_first_name,:contractor_first_name_raw,
                    :contractor_gender,:contractor_birth_date,
                    :contractor_address,:contractor_tel
                )
            """, mc)
            cid   = cur.lastrowid
            ntype = NOTICE_TYPES[(int(mc["contract_no"].split("-")[-1]) - 1) % len(NOTICE_TYPES)]
            ndate = notice_date(mc["expiry_date"])
            cur.execute("""
                INSERT INTO maturity_notices (contract_id, notice_date, notice_type)
                VALUES (?, ?, ?)
            """, (cid, ndate, ntype))
        print(f"  契約（満期管理用）: {len(MATURITY_CONTRACTS)}件 + notices: {len(MATURITY_CONTRACTS)}件")

        # ── 顧客マスタ＆顧客契約データ投入（グループ単位）────────
        total_customers = 0
        total_cust_contracts = 0
        for group_customers in ALL_CUSTOMER_GROUPS:
            for c in group_customers:
                group_code = c["group_code"]
                first_name = mask_first_name(c["first_name_raw"])
                match_key  = make_match_key(group_code, c["gender"], c["birth_date"], c["first_name_raw"])

                # 名寄せ：同一グループ内に既存顧客がいれば統合
                existing_id = find_same_customer(
                    conn, group_code, c["gender"], c["birth_date"],
                    c["first_name_raw"], c["tel"], c["address"]
                )
                if existing_id:
                    cust_db_id = existing_id
                else:
                    cur.execute("""
                        INSERT OR IGNORE INTO customers
                        (group_code, last_name, first_name, first_name_raw, gender, birth_date,
                         address, tel, email, family_structure, hobbies, assets_info, match_key)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (group_code, c["last_name"], first_name, c["first_name_raw"],
                          c["gender"], c["birth_date"], c["address"], c["tel"], c["email"],
                          c["family_structure"], c["hobbies"], c["assets_info"], match_key))
                    cust_db_id = cur.lastrowid
                    total_customers += 1

                # 各代理店への契約を登録
                customer_display_name = f"{c['last_name']} {first_name}"
                for ci, ct in enumerate(c["contracts"], 1):
                    contract_no   = f"CUST-{ct['agency_code']}-{cust_db_id:04d}-{ci:02d}"
                    renewal_month = ct["expiry_date"][:7]
                    cur.execute("""
                        INSERT INTO contracts
                        (agency_code, contract_no, customer_name, renewal_month, status,
                         policy_type, expiry_date, annual_premium, staff_code,
                         contact_method, contact_info, followcall_status, renewal_status,
                         upsell_status, lapse_status,
                         linked_customer_id,
                         contractor_last_name, contractor_first_name, contractor_first_name_raw,
                         contractor_gender, contractor_birth_date,
                         contractor_address, contractor_tel)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (ct["agency_code"], contract_no, customer_display_name,
                          renewal_month, "pending",
                          ct["policy_type"], ct["expiry_date"], ct["annual_premium"], ct["staff_code"],
                          "TEL", c["tel"], "未実施", "未対応", "なし", 0,
                          cust_db_id,
                          c["last_name"], first_name, c["first_name_raw"],
                          c["gender"], c["birth_date"],
                          c["address"], c["tel"]))
                    total_cust_contracts += 1

        print(f"  顧客マスタ: {total_customers}名 / 顧客契約: {total_cust_contracts}件")

        cur.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        print(f"\nDB初期化完了: {DB_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
