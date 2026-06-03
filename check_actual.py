import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('db/users.sqlite')
conn.row_factory = sqlite3.Row

sql = """
    SELECT staff_code, policy_type,
           CAST(strftime('%m', expiry_date) AS INTEGER) AS month,
           SUM(renewed_premium) AS total, COUNT(*) AS cnt
    FROM contracts
    WHERE agency_code = 'A001'
      AND expiry_date >= '2026-04-01'
      AND expiry_date <= '2027-03-31'
      AND renewed_policy_number IS NOT NULL
      AND renewed_premium IS NOT NULL
    GROUP BY staff_code, policy_type, month
    ORDER BY staff_code, month, policy_type
    LIMIT 20
"""
rows = conn.execute(sql).fetchall()
print(f"A001 2026年度 更改実績（{len(rows)}件）")
for r in rows:
    print(dict(r))

# 合計も確認
total = conn.execute("""
    SELECT COUNT(*) as cnt, SUM(renewed_premium) as total
    FROM contracts
    WHERE agency_code = 'A001'
      AND expiry_date >= '2026-04-01'
      AND expiry_date <= '2027-03-31'
      AND renewed_policy_number IS NOT NULL
      AND renewed_premium IS NOT NULL
""").fetchone()
print(f"\n合計: {dict(total)}")
conn.close()
