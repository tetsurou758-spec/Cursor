import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect(r'C:\Users\yoshi\OneDrive\ドキュメント\Cursor\db\users.sqlite')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== M-始まり契約の contract_no / policy_number ===")
cur.execute("""
SELECT c.id, c.contract_no, c.policy_number, c.policy_type,
       cd.id as detail_id, cd.product_name, cd.auto_nfl_grade,
       cd.auto_car_name, cd.auto_plate_no
FROM contracts c
LEFT JOIN contract_details cd ON cd.contract_id = c.id
WHERE c.contract_no LIKE 'M-%'
ORDER BY c.contract_no
""")
for r in cur.fetchall():
    print(dict(r))

print("\n=== 非M系の比較（CUST-A001-0001-01）===")
cur.execute("""
SELECT c.id, c.contract_no, c.policy_number,
       cd.id as detail_id, cd.product_name, cd.auto_nfl_grade, cd.auto_car_name
FROM contracts c
LEFT JOIN contract_details cd ON cd.contract_id = c.id
WHERE c.contract_no = 'CUST-A001-0001-01'
""")
for r in cur.fetchall():
    print(dict(r))

# maturityのリンク生成ロジック再現
print("\n=== maturity.htmlのリンクURL再現 ===")
cur.execute("""
SELECT c.contract_no, c.policy_number
FROM contracts c
WHERE c.contract_no LIKE 'M-%'
ORDER BY c.contract_no
LIMIT 5
""")
for r in cur.fetchall():
    raw_no = r['contract_no'] or r['policy_number'] or ''
    print(f"contract_no={r['contract_no']}, policy_number={r['policy_number']}, link_target={raw_no}")
    print(f"  → contract_detail.html?contract_no={raw_no}")

conn.close()
