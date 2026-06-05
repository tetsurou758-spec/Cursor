"""
更改おすすめプランTBL（renewal_recommend_plans）シードスクリプト

maturity_noticesが存在する契約を対象にPDFを生成してDBに投入する。
"""

import os
import sys
import sqlite3

# reportsモジュールをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from reports.generate_renewal_notice import generate_renewal_notice_pdf

DB_PATH = os.path.join(os.path.dirname(__file__), "users.sqlite")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # テーブル作成
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS renewal_recommend_plans (
            id           INTEGER  PRIMARY KEY AUTOINCREMENT,
            contract_no  TEXT     NOT NULL UNIQUE,
            pdf_data     BLOB     NOT NULL,
            generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_renewal_recommend_plans_contract_no
            ON renewal_recommend_plans(contract_no);
    """)
    conn.commit()

    # maturity_noticesが存在する契約を取得
    targets = conn.execute("""
        SELECT c.*, mn.notice_type
        FROM maturity_notices mn
        JOIN contracts c ON c.id = mn.contract_id
        ORDER BY c.contract_no
    """).fetchall()

    print(f"対象件数: {len(targets)}件")

    ok = 0
    ng = 0
    for row in targets:
        contract = dict(row)
        contract_no = contract["contract_no"]

        # contract_details取得（なければNone）
        detail_row = conn.execute(
            "SELECT * FROM contract_details WHERE contract_id = ?", (contract["id"],)
        ).fetchone()
        cd = dict(detail_row) if detail_row else None

        try:
            pdf_bytes = generate_renewal_notice_pdf(contract, cd)
            conn.execute("""
                INSERT INTO renewal_recommend_plans (contract_no, pdf_data)
                VALUES (?, ?)
                ON CONFLICT(contract_no) DO UPDATE SET
                    pdf_data     = excluded.pdf_data,
                    updated_at   = CURRENT_TIMESTAMP
            """, (contract_no, pdf_bytes))
            conn.commit()
            ok += 1
            if ok % 50 == 0:
                print(f"  {ok}件生成済...")
        except Exception as e:
            ng += 1
            print(f"  [ERROR] {contract_no}: {e}")

    conn.close()
    print(f"\n完了: 成功={ok}件  失敗={ng}件")


if __name__ == "__main__":
    main()
