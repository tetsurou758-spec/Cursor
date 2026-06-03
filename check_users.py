import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('db/users.sqlite')
conn.row_factory = sqlite3.Row

print("=== agencies テーブル ===")
for r in conn.execute("SELECT agency_id, agency_code, agency_name, buka_code, group_code FROM agencies ORDER BY agency_code"):
    print(dict(r))

print("\n=== contracts テーブル カラム ===")
cols = [r[1] for r in conn.execute("PRAGMA table_info(contracts)")]
print(cols)

print("\n=== 代理店別 担当者コード一覧（contracts） ===")
rows = conn.execute("""
    SELECT agency_code, staff_code, COUNT(*) as cnt
    FROM contracts
    WHERE staff_code IS NOT NULL AND staff_code != ''
    GROUP BY agency_code, staff_code
    ORDER BY agency_code, staff_code
""").fetchall()
for r in rows:
    print(dict(r))

conn.close()
