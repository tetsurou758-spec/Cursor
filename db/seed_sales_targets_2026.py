"""
2026年度 成績目標値シードスクリプト（デモ用）

2026年度の契約（expiry_date 2026-04-01〜2027-03-31）の
annual_premium × 1.1 を目標値として sales_targets に投入する。

投入対象：
- 担当者別（staff_code単位）
- 代理店合計（staff_code='ALL'）
"""

import os
import sys
import sqlite3

sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = os.path.join(os.path.dirname(__file__), "users.sqlite")

# 日本語種目 → 英字コード変換マップ
POLICY_TYPE_MAP = {
    "自動車":         "AUTO",
    "火災":           "FIRE",
    "傷害":           "INJURY",
    "自賠責":         "JIBAI",
    "賠償責任":       "LIABILITY",
    "サイバーリスク": "CYBER",
    "所得補償":       "INCOME",
}

FISCAL_YEAR  = 2026
TARGET_RATIO = 1.0   # 更改前保険料をそのまま目標値に設定
DATE_FROM    = "2026-04-01"
DATE_TO      = "2027-03-31"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 既存の2026年度レコードを削除（再実行時の重複防止）
    deleted = conn.execute(
        "DELETE FROM sales_targets WHERE fiscal_year = ?", (FISCAL_YEAR,)
    ).rowcount
    conn.commit()
    print(f"既存2026年度レコード削除: {deleted}件")

    # ── 担当者別集計 ─────────────────────────────────────────────────────────
    rows = conn.execute("""
        SELECT agency_code,
               staff_code,
               CAST(strftime('%m', expiry_date) AS INTEGER) AS month,
               policy_type,
               SUM(annual_premium) AS base_total
        FROM contracts
        WHERE expiry_date >= ?
          AND expiry_date <= ?
          AND annual_premium IS NOT NULL
          AND staff_code IS NOT NULL
          AND staff_code != ''
        GROUP BY agency_code, staff_code, month, policy_type
    """, (DATE_FROM, DATE_TO)).fetchall()

    insert_data = []
    for r in rows:
        pt_en = POLICY_TYPE_MAP.get(r["policy_type"])
        if not pt_en:
            continue   # 'その他' 等はスキップ
        target = round(r["base_total"] * TARGET_RATIO)
        insert_data.append((
            r["agency_code"], r["staff_code"], FISCAL_YEAR,
            r["month"], pt_en, target
        ))

    # ── 代理店合計（ALL）集計 ────────────────────────────────────────────────
    rows_all = conn.execute("""
        SELECT agency_code,
               CAST(strftime('%m', expiry_date) AS INTEGER) AS month,
               policy_type,
               SUM(annual_premium) AS base_total
        FROM contracts
        WHERE expiry_date >= ?
          AND expiry_date <= ?
          AND annual_premium IS NOT NULL
        GROUP BY agency_code, month, policy_type
    """, (DATE_FROM, DATE_TO)).fetchall()

    for r in rows_all:
        pt_en = POLICY_TYPE_MAP.get(r["policy_type"])
        if not pt_en:
            continue
        target = round(r["base_total"] * TARGET_RATIO)
        insert_data.append((
            r["agency_code"], "ALL", FISCAL_YEAR,
            r["month"], pt_en, target
        ))

    # ── 一括INSERT ────────────────────────────────────────────────────────────
    conn.executemany("""
        INSERT INTO sales_targets
            (agency_code, staff_code, fiscal_year, month, policy_type, target_amount)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(agency_code, staff_code, fiscal_year, month, policy_type)
        DO UPDATE SET target_amount = excluded.target_amount,
                      updated_at    = CURRENT_TIMESTAMP
    """, insert_data)
    conn.commit()

    print(f"投入件数: {len(insert_data)}件")

    # ── サマリ確認 ────────────────────────────────────────────────────────────
    summary = conn.execute("""
        SELECT agency_code, staff_code, COUNT(*) as cnt,
               SUM(target_amount) as total
        FROM sales_targets
        WHERE fiscal_year = ?
        GROUP BY agency_code, staff_code
        ORDER BY agency_code, staff_code
    """, (FISCAL_YEAR,)).fetchall()
    print("\n=== 投入結果サマリ ===")
    for s in summary:
        print(f"  {s['agency_code']} / {s['staff_code']:6s} : {s['cnt']}件  合計¥{s['total']:,}")

    conn.close()


if __name__ == "__main__":
    main()
