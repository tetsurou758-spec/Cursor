import sys; sys.stdout.reconfigure(encoding='utf-8')
from backend.routers.sales_router import POLICY_TYPE_MAP, POLICY_TYPES
import sqlite3

print("マッピング確認:")
for ja, en in POLICY_TYPE_MAP.items():
    print(f"  {ja} -> {en}")

conn = sqlite3.connect('db/users.sqlite')
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT policy_type, SUM(renewed_premium) AS total
    FROM contracts
    WHERE agency_code = 'A001'
      AND renewed_policy_number IS NOT NULL
      AND renewed_premium IS NOT NULL
    GROUP BY policy_type
""").fetchall()

print("\n変換テスト（A001 更改実績）:")
for r in rows:
    raw = r["policy_type"]
    converted = POLICY_TYPE_MAP.get(raw, raw if raw in POLICY_TYPES else None)
    print(f"  '{raw}' -> '{converted}'  合計={r['total']}")
conn.close()
