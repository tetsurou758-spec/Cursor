import sqlite3, sys, os
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('db/users.sqlite')
conn.row_factory = sqlite3.Row

print("=" * 60)
print("【 users テーブル 】代理店ユーザー")
print("=" * 60)
rows = conn.execute('SELECT id, agency_code, login_id, name, role_id, is_active FROM users ORDER BY agency_code, id').fetchall()
print(f"{'id':<4} {'agency_code':<12} {'login_id':<10} {'name':<20} {'role_id'} is_active")
print('-' * 65)
for r in rows:
    print(f"{r['id']:<4} {r['agency_code']:<12} {r['login_id']:<10} {r['name']:<20} {r['role_id']:<8} {r['is_active']}")

print("\n" + "=" * 60)
print("【 staff_users テーブル 】社員ユーザー")
print("=" * 60)
cols = [r[1] for r in conn.execute("PRAGMA table_info(staff_users)")]
print("カラム:", cols)
rows2 = conn.execute('SELECT * FROM staff_users').fetchall()
for r in rows2:
    print(dict(r))

print("\n" + "=" * 60)
print("【 roles テーブル 】")
print("=" * 60)
for r in conn.execute('SELECT * FROM roles'):
    print(dict(r))

print("\n" + "=" * 60)
print("【 staff_roles テーブル 】")
print("=" * 60)
for r in conn.execute('SELECT * FROM staff_roles'):
    print(dict(r))

print("\n" + "=" * 60)
print("【 db/ フォルダ内ファイル 】")
print("=" * 60)
for f in sorted(os.listdir('db')):
    path = os.path.join('db', f)
    print(f"  {f:<35} {os.path.getsize(path):>10} bytes")

conn.close()
