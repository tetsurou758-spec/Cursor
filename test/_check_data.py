import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect(r'C:\Users\yoshi\OneDrive\ドキュメント\Cursor\db\users.sqlite')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
SELECT contract_no, customer_name, agency_code, expiry_date, linked_customer_id, renewal_month
FROM contracts
WHERE agency_code = 'A001' AND linked_customer_id IS NOT NULL AND customer_name LIKE '%鈴木%'
LIMIT 5
""")
print("=== A001 鈴木 linked ===")
for r in cur.fetchall():
    print(dict(r))

cur.execute("""
SELECT contract_no, customer_name, agency_code, expiry_date, linked_customer_id, renewal_month
FROM contracts
WHERE agency_code = 'A001' AND linked_customer_id IS NOT NULL
ORDER BY renewal_month
LIMIT 10
""")
print("\n=== A001 linked contracts ===")
for r in cur.fetchall():
    print(dict(r))
conn.close()
