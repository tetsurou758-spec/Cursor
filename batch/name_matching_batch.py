"""
名寄せバッチ
contractsテーブルの未名寄せ契約（linked_customer_id IS NULL）を対象に
同一参照グループ内で名寄せ判定を行い
customersテーブルを生成・更新する

【連絡先情報の取得ルール】
同一顧客の複数契約がある場合、expiry_date が最新（＝始期日が最新）の
契約の連絡先情報を顧客マスタに登録する：
  - contractor_address → customers.address
  - contractor_tel     → customers.tel

【match_keyの生成】
contractor_first_name_raw（本名）を使用してmatch_keyを生成する。
マスク前の名前があることで、イニシャルの違いによる名寄せ漏れを防ぐ。

【営業情報はバッチで生成しない】
以下はバッチでNULLのまま（UIから代理店担当者が手入力する項目）：
  - email / family_structure / hobbies / assets_info
"""
import sqlite3
import hashlib
import os
import logging
from collections import defaultdict
from datetime import datetime

# ── パス設定 ─────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "db", "users.sqlite")
LOG_DIR  = os.path.join(BASE_DIR, "logs")


def setup_logger() -> tuple:
    """ファイル＋コンソール二重出力のロガーを設定する"""
    os.makedirs(LOG_DIR, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(LOG_DIR, f"name_matching_{ts}.log")

    logger = logging.getLogger("name_matching")
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger, log_path


def make_match_key(group_code: str, gender: str,
                   birth_date: str, first_name_raw: str) -> str:
    """名寄せキー：group_code + gender + birth_date + first_name_raw のSHA256"""
    raw = f"{group_code}|{gender}|{birth_date}|{first_name_raw}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def mask_first_name(name: str) -> str:
    """名の先頭1文字を○でマスクする"""
    if not name:
        return "○"
    return "○" if len(name) == 1 else "○" + name[1:]


def find_same_customer(cur, group_code: str, gender: str, birth_date: str,
                       first_name_raw: str, tel: str, address: str):
    """
    同一group_code内で性別・生年月日・名（本名）が一致
    AND（電話番号一致 OR 住所一致）の場合にcustomer_idを返す
    一致なければNoneを返す
    """
    row = cur.execute("""
        SELECT customer_id FROM customers
        WHERE group_code    = ?
          AND gender        = ?
          AND birth_date    = ?
          AND first_name_raw = ?
          AND (
                (tel     IS NOT NULL AND tel     != '' AND tel     = ?)
             OR (address IS NOT NULL AND address != '' AND address = ?)
              )
        LIMIT 1
    """, (group_code, gender, birth_date,
          first_name_raw,
          tel or "", address or "")).fetchone()
    return row[0] if row else None


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_unmatched_contracts(cur) -> list:
    """
    未名寄せかつ contractor_first_name_raw を持つ契約を取得する。
    同一顧客の複数契約は後でグループ化するため全件取得する。
    """
    return cur.execute("""
        SELECT
            c.id                       AS contract_id,
            c.contract_no,
            c.agency_code,
            c.contractor_last_name,
            c.contractor_first_name,
            c.contractor_first_name_raw,
            c.contractor_gender,
            c.contractor_birth_date,
            c.contractor_address,
            c.contractor_tel,
            c.contact_method,
            c.contact_info,
            c.expiry_date,
            ag.group_code
        FROM contracts c
        JOIN agencies ag ON ag.agency_code = c.agency_code
        WHERE c.linked_customer_id        IS NULL
          AND c.contractor_last_name      IS NOT NULL
          AND c.contractor_gender         IS NOT NULL
          AND c.contractor_birth_date     IS NOT NULL
          AND c.contractor_first_name_raw IS NOT NULL
        ORDER BY ag.group_code, c.agency_code, c.id
    """).fetchall()


def group_contracts_by_customer(rows: list) -> list:
    """
    契約を顧客候補キー (group_code, gender, birth_date, first_name_raw) でグループ化する。
    各グループ内は expiry_date の降順（最新始期が先頭）にソートし、
    先頭の契約を連絡先情報の取得元（primary）として扱う。

    戻り値: [(primary_dict, [all_dicts_in_group]), ...]
    """
    groups = defaultdict(list)
    for row in rows:
        key = (
            row["group_code"],
            (row["contractor_gender"]         or "").strip(),
            (row["contractor_birth_date"]     or "").strip(),
            (row["contractor_first_name_raw"] or "").strip(),
        )
        groups[key].append(dict(row))

    result = []
    for contracts in groups.values():
        # expiry_date降順ソートで最新始期の契約を先頭に
        contracts.sort(key=lambda c: c["expiry_date"] or "", reverse=True)
        result.append((contracts[0], contracts))

    return result


def process_customer_group(cur, primary: dict, contracts: list, logger) -> tuple:
    """
    同一顧客グループを処理する。
      primary  : 最新始期の契約（連絡先情報の取得元）
      contracts: 同一顧客の全契約リスト

    戻り値: (is_new: bool, linked_count: int, error_count: int)
    """
    group_code     = primary["group_code"]
    last_name      = (primary["contractor_last_name"]      or "").strip()
    first_name_raw = (primary["contractor_first_name_raw"] or "").strip()
    first_name     = mask_first_name(first_name_raw)
    gender         = (primary["contractor_gender"]         or "").strip()
    birth_date     = (primary["contractor_birth_date"]     or "").strip()
    address        = (primary["contractor_address"]        or "").strip()
    tel            = (primary["contractor_tel"]            or "").strip()

    if not (last_name and first_name_raw and gender and birth_date):
        for c in contracts:
            logger.warning(f"  スキップ [{c['contract_no']}]: 必須項目不足")
        return False, 0, len(contracts)

    try:
        existing_id = find_same_customer(
            cur, group_code, gender, birth_date, first_name_raw, tel, address
        )

        if existing_id:
            # 既存顧客へ紐付け（連絡先はupdate_atのみ更新）
            customer_id = existing_id
            is_new = False
            cur.execute(
                "UPDATE customers SET updated_at = CURRENT_TIMESTAMP WHERE customer_id = ?",
                (customer_id,)
            )
        else:
            # 新規顧客登録（連絡先はprimary契約の情報を使用）
            match_key = make_match_key(group_code, gender, birth_date, first_name_raw)
            cur.execute("""
                INSERT OR IGNORE INTO customers
                    (group_code, last_name, first_name, first_name_raw,
                     gender, birth_date, address, tel, match_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (group_code, last_name, first_name, first_name_raw,
                  gender, birth_date, address, tel, match_key))

            new_id = cur.lastrowid
            if not new_id:
                # INSERT OR IGNORE でスキップされた（同一match_key既存）
                row2 = cur.execute(
                    "SELECT customer_id FROM customers WHERE group_code=? AND match_key=?",
                    (group_code, match_key)
                ).fetchone()
                new_id = row2[0] if row2 else None

            if not new_id:
                for c in contracts:
                    logger.error(f"  [エラー] {c['contract_no']}: 顧客登録に失敗しました")
                return False, 0, len(contracts)

            customer_id = new_id
            is_new = True
            logger.info(
                f"  [新規登録] customer_id={customer_id}"
                f" ({last_name} {first_name_raw} / G:{group_code})"
                f" ← 連絡先: {primary['contract_no']} 満期:{primary['expiry_date']}"
            )

        # 全契約を顧客に紐付け
        linked = 0
        for c in contracts:
            cur.execute(
                "UPDATE contracts SET linked_customer_id = ? WHERE id = ?",
                (customer_id, c["contract_id"])
            )
            logger.info(
                f"  {'[新規]' if is_new else '[既存]'}紐付 {c['contract_no']}"
                f" → customer_id={customer_id} ({last_name} {first_name_raw})"
            )
            linked += 1

        return is_new, linked, 0

    except Exception as e:
        logger.error(f"  [エラー] グループ処理中にエラー: {e}")
        return False, 0, len(contracts)


def print_db_stats(cur, logger):
    """グループ別・代理店別の顧客数・契約数を出力する"""
    logger.info("")
    logger.info("─" * 60)
    logger.info("【DB統計】グループ別・代理店別 顧客数・契約数")
    logger.info("─" * 60)

    stats = cur.execute("""
        SELECT
            ag.group_code,
            ag.agency_code,
            ag.agency_name,
            COUNT(DISTINCT c.linked_customer_id) AS linked_customers,
            COUNT(c.id)                           AS total_contracts
        FROM agencies ag
        LEFT JOIN contracts c ON c.agency_code = ag.agency_code
        GROUP BY ag.group_code, ag.agency_code
        ORDER BY ag.group_code, ag.agency_code
    """).fetchall()

    cur_group = None
    for s in stats:
        if s["group_code"] != cur_group:
            cur_group = s["group_code"]
            gc_total = cur.execute("""
                SELECT COUNT(*) AS cnt FROM customers WHERE group_code = ?
            """, (cur_group,)).fetchone()["cnt"]
            logger.info(f"  ▶ グループ {cur_group}（顧客マスタ合計: {gc_total}名）")

        logger.info(
            f"    {s['agency_code']} {s['agency_name'][:18]:<18}"
            f"  紐付顧客: {s['linked_customers']:>4}件"
            f"  契約数: {s['total_contracts']:>5}件"
        )

    total_cust = cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    total_cont = cur.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
    logger.info(f"\n  顧客マスタ合計: {total_cust}名  /  契約合計: {total_cont}件")


def run_batch(logger) -> bool:
    logger.info("=" * 60)
    logger.info("名寄せバッチ 開始")
    logger.info(f"DB: {DB_PATH}")
    logger.info("=" * 60)

    cnt_target = cnt_new_customers = cnt_contracts_linked = cnt_error = 0

    conn = get_db()
    try:
        cur = conn.cursor()

        # ① 未名寄せ契約を取得
        targets    = fetch_unmatched_contracts(cur)
        cnt_target = len(targets)
        logger.info(f"処理対象契約: {cnt_target}件")

        if cnt_target == 0:
            logger.info("未名寄せ契約なし。処理をスキップします。")
        else:
            # ② 同一顧客でグループ化（最新expiry_dateのものを先頭＝primary）
            groups = group_contracts_by_customer(targets)
            logger.info(f"顧客候補グループ数: {len(groups)}件")
            logger.info("─" * 60)

            for primary, contracts in groups:
                is_new, linked, errors = process_customer_group(
                    cur, primary, contracts, logger
                )
                if is_new:
                    cnt_new_customers += 1
                cnt_contracts_linked += linked
                cnt_error            += errors

        conn.commit()

        # ③ DB統計
        print_db_stats(cur, logger)

    except Exception as e:
        logger.error(f"バッチ処理中に予期せぬエラーが発生しました: {e}")
        conn.rollback()
        cnt_error += 1
    finally:
        conn.close()

    # ④ サマリー出力
    logger.info("")
    logger.info("=" * 60)
    logger.info("【処理結果サマリー】")
    logger.info(f"  処理対象契約件数   : {cnt_target:>5} 件")
    logger.info(f"  新規顧客登録       : {cnt_new_customers:>5} 名")
    logger.info(f"  契約紐付け完了     : {cnt_contracts_linked:>5} 件")
    logger.info(f"  エラー件数         : {cnt_error:>5} 件")
    logger.info("名寄せバッチ 終了")
    logger.info("=" * 60)

    return cnt_error == 0


if __name__ == "__main__":
    logger, log_path = setup_logger()
    success = run_batch(logger)
    print(f"\nログファイル: {log_path}")
    raise SystemExit(0 if success else 1)
