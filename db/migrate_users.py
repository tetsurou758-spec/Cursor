"""
usersテーブル拡張マイグレーション
- staff_code カラムを追加
- 各代理店に管理者1名＋担当者5名を設定（計48名）
- 契約TBLの担当者コードを優先割当て、不足分は自動生成
"""
import sqlite3
import bcrypt
import sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "db/users.sqlite"

# ── 名前マスター（管理者・担当者それぞれ8代理店分） ──────────────────
ADMIN_NAMES = {
    "A001": "田中 一郎",
    "A002": "佐藤 次郎",
    "A003": "鈴木 三郎",
    "A004": "高橋 四郎",
    "B001": "伊藤 一郎",
    "B002": "渡辺 次郎",
    "C001": "中村 一郎",
    "C003": "小林 次郎",
}

# 担当者名プール（各代理店で先頭から5名使用）
STAFF_NAME_POOL = {
    "A001": ["山田 花子", "松本 幸子", "井上 由美", "木村 直子", "林 明美"],
    "A002": ["斎藤 恵子", "清水 裕子", "山口 智子", "阿部 京子", "池田 夏子"],
    "A003": ["橋本 奈々", "石川 美咲", "前田 里奈", "藤田 麻衣", "後藤 亜希"],
    "A004": ["岡田 桃子", "長谷川 葵", "近藤 梨花", "坂本 千尋", "遠藤 詩織"],
    "B001": ["加藤 健二", "山本 浩二", "中島 誠", "小川 修", "野村 俊介"],
    "B002": ["松田 拓也", "原田 大介", "柴田 和也", "宮本 翔", "福田 亮太"],
    "C001": ["西村 浩", "菅原 聡", "上田 徹", "杉山 雄二", "増田 剛"],
    "C003": ["丸山 洋介", "島田 英樹", "平野 貴志", "江口 誠司", "石井 康介"],
}


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(12)).decode()


def get_contract_staff_codes(conn, agency_code: str) -> list:
    """contractsテーブルから代理店別の担当者コードを取得（件数降順）"""
    rows = conn.execute("""
        SELECT staff_code
        FROM contracts
        WHERE agency_code = ? AND staff_code IS NOT NULL AND staff_code != ''
        GROUP BY staff_code
        ORDER BY COUNT(*) DESC
    """, (agency_code,)).fetchall()
    return [r["staff_code"] for r in rows]


def fill_staff_codes(existing: list, count: int = 5) -> list:
    """既存コードをベースに、不足分をS001〜S999から補完"""
    result = list(existing[:count])
    if len(result) >= count:
        return result

    # 既存コードのプレフィックス文字を特定（なければ'S'）
    prefix = 'S'
    used = set(result)
    n = 1
    while len(result) < count:
        candidate = f"{prefix}{n:03d}"
        if candidate not in used:
            result.append(candidate)
            used.add(candidate)
        n += 1
    return result


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # ── 1. staff_code カラムを追加（既存なら何もしない） ──────────────
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
    if "staff_code" not in existing_cols:
        conn.execute("ALTER TABLE users ADD COLUMN staff_code TEXT")
        conn.commit()
        print("✅ staff_code カラムを追加しました")
    else:
        print("ℹ️  staff_code カラムは既に存在します")

    # ── 2. 代理店一覧を取得 ────────────────────────────────────────
    agencies = conn.execute(
        "SELECT agency_id, agency_code FROM agencies ORDER BY agency_code"
    ).fetchall()
    print(f"\n対象代理店: {[a['agency_code'] for a in agencies]}")

    # ── 3. 既存ユーザーを全削除（新規作成で置き換え） ─────────────────
    conn.execute("DELETE FROM users")
    conn.commit()
    print("🗑️  既存ユーザーを削除しました")

    # ── 4. 各代理店にユーザーを投入 ────────────────────────────────
    all_users = []
    for ag in agencies:
        agency_code = ag["agency_code"]
        agency_id   = ag["agency_id"]

        # 契約TBLから担当者コードを取得・補完
        contract_codes = get_contract_staff_codes(conn, agency_code)
        staff_codes    = fill_staff_codes(contract_codes, count=5)

        # 管理者ユーザー
        all_users.append({
            "agency_code":   agency_code,
            "agency_id":     agency_id,
            "role_id":       1,
            "login_id":      "admin",
            "password":      hash_password("password123"),
            "name":          ADMIN_NAMES[agency_code],
            "staff_code":    None,  # 管理者は担当者コードなし
            "is_active":     1,
        })

        # 担当者ユーザー（5名）
        names = STAFF_NAME_POOL[agency_code]
        for i, sc in enumerate(staff_codes):
            all_users.append({
                "agency_code": agency_code,
                "agency_id":   agency_id,
                "role_id":     2,
                "login_id":    f"staff{i+1}",
                "password":    hash_password(f"pass{(i+1):03d}"),
                "name":        names[i],
                "staff_code":  sc,
                "is_active":   1,
            })

    # ── 5. INSERT ────────────────────────────────────────────────
    conn.executemany("""
        INSERT INTO users (agency_code, agency_id, role_id, login_id, password_hash, name, staff_code, is_active)
        VALUES (:agency_code, :agency_id, :role_id, :login_id, :password, :name, :staff_code, :is_active)
    """, all_users)
    conn.commit()
    print(f"✅ {len(all_users)} 件のユーザーを投入しました\n")

    # ── 6. 確認表示 ──────────────────────────────────────────────
    print(f"{'代理店':<8} {'login_id':<10} {'name':<18} {'staff_code':<12} {'role'}")
    print("-" * 65)
    for r in conn.execute("""
        SELECT u.agency_code, u.login_id, u.name, u.staff_code, u.role_id
        FROM users u ORDER BY u.agency_code, u.role_id, u.login_id
    """):
        role_label = "管理者" if r["role_id"] == 1 else "担当"
        sc = r["staff_code"] or "（なし）"
        print(f"{r['agency_code']:<8} {r['login_id']:<10} {r['name']:<18} {sc:<12} {role_label}")

    conn.close()
    print("\n✅ マイグレーション完了")


if __name__ == "__main__":
    main()
