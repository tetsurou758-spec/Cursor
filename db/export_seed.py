"""
export_seed.py
現在のDB（users.sqlite / insurance.db）の内容を読み取り、
同一状態を再現できる db/generated_seed.py を生成する。

使い方:
    python db/export_seed.py
    python db/generated_seed.py   ← 生成されたスクリプトで再現
"""

import sqlite3
import os
import sys
import json
from datetime import datetime

# =========================================================
# 設定
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DB  = os.path.join(BASE_DIR, "users.sqlite")
INS_DB    = os.path.join(BASE_DIR, "insurance.db")
OUTPUT    = os.path.join(BASE_DIR, "generated_seed.py")

# BLOBデータが大きすぎるため除外するテーブル
SKIP_TABLES = {
    "renewal_recommend_plans",  # PDF BLOBが大量
    "riskmap_pdfs",             # PDF BLOB
    "report_requests",          # 帳票ファイルBLOB
    "sqlite_sequence",
}

# =========================================================
# ヘルパー
# =========================================================

def get_tables(conn):
    """テーブル一覧取得（sqlite_sequence除く）"""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid"
    ).fetchall()
    return [r[0] for r in rows if r[0] not in SKIP_TABLES]


def get_schema(conn, table):
    """CREATE TABLE文を取得"""
    row = conn.execute(
        f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] if row else None


def get_rows(conn, table):
    """全行取得（カラム名付き）"""
    cur = conn.execute(f'SELECT * FROM "{table}"')
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return cols, rows


def py_repr(val):
    """値をPythonリテラル文字列に変換"""
    if val is None:
        return "None"
    if isinstance(val, (int, float)):
        return repr(val)
    if isinstance(val, bytes):
        # 小さいBLOBはbytesリテラルで出力
        return repr(val)
    return repr(str(val))


# =========================================================
# メイン
# =========================================================

def export_db(conn, db_label, tables, lines):
    """1つのDBのテーブルを出力バッファに追記"""
    for table in tables:
        schema = get_schema(conn, table)
        if not schema:
            continue
        cols, rows = get_rows(conn, table)

        lines.append(f"\n    # -------- {db_label}: {table} ({len(rows)}件) --------")
        lines.append(f'    cur.executescript("""')
        lines.append(f'DROP TABLE IF EXISTS "{table}";')
        lines.append(schema.rstrip(";") + ";")
        lines.append('""")')

        if not rows:
            continue

        # INSERT文を100行単位で分割（大テーブル対応）
        col_str = ", ".join(f'"{c}"' for c in cols)
        placeholder = ", ".join(["?"] * len(cols))

        lines.append(f'    _rows_{table} = [')
        for row in rows:
            vals = ", ".join(py_repr(v) for v in row)
            lines.append(f'        ({vals}),')
        lines.append(f'    ]')
        lines.append(f'    cur.executemany(')
        lines.append(f'        \'INSERT INTO "{table}" ({col_str}) VALUES ({placeholder})\',')
        lines.append(f'        _rows_{table}')
        lines.append(f'    )')


def main():
    print(f"[1/4] users.sqlite 読み込み中...")
    conn_u = sqlite3.connect(USERS_DB)

    print(f"[2/4] insurance.db 読み込み中...")
    conn_i = sqlite3.connect(INS_DB)

    tables_u = get_tables(conn_u)
    tables_i = get_tables(conn_i)

    print(f"      users.sqlite : {tables_u}")
    print(f"      insurance.db : {tables_i}")

    # ===== 出力バッファ =====
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append('"""')
    lines.append(f'generated_seed.py  （自動生成: {now}）')
    lines.append('現在のDBの状態をそのまま再現するシードスクリプト。')
    lines.append('export_seed.py によって生成された。直接編集しないこと。')
    lines.append('')
    lines.append('使い方:')
    lines.append('    python db/generated_seed.py')
    lines.append('"""')
    lines.append('')
    lines.append('import sqlite3, os')
    lines.append('')
    lines.append('BASE_DIR = os.path.dirname(os.path.abspath(__file__))')
    lines.append('USERS_DB = os.path.join(BASE_DIR, "users.sqlite")')
    lines.append('INS_DB   = os.path.join(BASE_DIR, "insurance.db")')
    lines.append('')
    lines.append('')
    lines.append('def seed_users_db():')
    lines.append('    conn = sqlite3.connect(USERS_DB)')
    lines.append('    cur  = conn.cursor()')
    lines.append('    cur.execute("PRAGMA foreign_keys = OFF")')

    export_db(conn_u, "users.sqlite", tables_u, lines)

    lines.append('')
    lines.append('    conn.commit()')
    lines.append('    conn.close()')
    lines.append(f'    print("  users.sqlite: {sum(1 for t in tables_u)}テーブル 復元完了")')
    lines.append('')
    lines.append('')
    lines.append('def seed_insurance_db():')
    lines.append('    conn = sqlite3.connect(INS_DB)')
    lines.append('    cur  = conn.cursor()')
    lines.append('    cur.execute("PRAGMA foreign_keys = OFF")')

    export_db(conn_i, "insurance.db", tables_i, lines)

    lines.append('')
    lines.append('    conn.commit()')
    lines.append('    conn.close()')
    lines.append(f'    print("  insurance.db: {sum(1 for t in tables_i)}テーブル 復元完了")')
    lines.append('')
    lines.append('')
    lines.append('if __name__ == "__main__":')
    lines.append('    print("DB再現シードを実行します...")')
    lines.append('    print("[1/2] users.sqlite 復元中...")')
    lines.append('    seed_users_db()')
    lines.append('    print("[2/2] insurance.db 復元中...")')
    lines.append('    seed_insurance_db()')
    lines.append('    print("完了 OK")')

    conn_u.close()
    conn_i.close()

    print(f"[3/4] {OUTPUT} に書き出し中...")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    size_kb = os.path.getsize(OUTPUT) // 1024
    print(f"[4/4] 完了 → {OUTPUT}  ({size_kb} KB)")
    print()
    print("再現するには:")
    print("    python db/generated_seed.py")


if __name__ == "__main__":
    main()
