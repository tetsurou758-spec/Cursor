import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect(r'C:\Users\yoshi\OneDrive\ドキュメント\Cursor\db\users.sqlite')
cur = conn.cursor()
print("=== SQLで直接集計（A001 グループA）===")
for m in ['2026-05','2026-06','2026-07']:
    q = "SELECT COUNT(*) FROM contracts WHERE agency_code='A001' AND strftime('%Y-%m',expiry_date)=?"
    total = cur.execute(q, (m,)).fetchone()[0]
    done  = cur.execute(q.replace("COUNT(*)", "COUNT(*)") +
                        " AND renewal_status='更改済'", (m,)).fetchone()[0]
    print(f"  {m}: 総件数={total}, 更改済={done}, 完了率={round(done/total*100,1) if total else 0}%")
conn.close()
