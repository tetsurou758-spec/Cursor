"""
contract_details テーブルのダミーデータINSERTスクリプト
- contract_detailsテーブルが未存在の場合はDDLで先にCREATE
- 既存レコードはスキップ（INSERT OR IGNORE）
- policy_typeごとにパターンをローテーション（idを割った余り）
"""

import sqlite3
import os
import sys

# DBパス（スクリプトの親ディレクトリ基準）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.sqlite")
DDL_PATH = os.path.join(BASE_DIR, "migrate_contract_details.sql")


def get_patterns():
    """policy_typeごとのINSERTパターン定義を返す"""
    patterns = {
        "自動車": [
            {
                "product_name": "THEクルマの保険",
                "auto_taininsho": "無制限",
                "auto_taibutsusho": "無制限",
                "auto_jinshin": "5,000万円",
                "auto_toshasho": "1,000万円",
                "auto_vehicle_amount": "180万円",
                "auto_vehicle_type": "一般",
                "auto_deductible": "5万円-10万円",
                "auto_nfl_grade": 12,
                "auto_age_condition": "26歳以上",
                "auto_driver_limit": "本人・配偶者限定",
                "auto_use_purpose": "日常・レジャー",
                "auto_car_name": "プリウス",
                "auto_car_model": "ZVW50",
                "auto_plate_no": "品川300あ1234",
                "coverage_target": "登録自動車",
            },
            {
                "product_name": "THEクルマの保険",
                "auto_taininsho": "無制限",
                "auto_taibutsusho": "無制限",
                "auto_jinshin": "3,000万円",
                "auto_toshasho": "500万円",
                "auto_vehicle_amount": None,
                "auto_vehicle_type": None,
                "auto_deductible": None,
                "auto_nfl_grade": 7,
                "auto_age_condition": "全年齢担保",
                "auto_driver_limit": "限定なし",
                "auto_use_purpose": "通勤・通学",
                "auto_car_name": "フィット",
                "auto_car_model": "GK3",
                "auto_plate_no": "横浜500さ5678",
                "coverage_target": "登録自動車",
            },
            {
                "product_name": "THEクルマの保険",
                "auto_taininsho": "無制限",
                "auto_taibutsusho": "無制限",
                "auto_jinshin": "5,000万円",
                "auto_toshasho": "1,000万円",
                "auto_vehicle_amount": "250万円",
                "auto_vehicle_type": "一般",
                "auto_deductible": "なし-10万円",
                "auto_nfl_grade": 18,
                "auto_age_condition": "35歳以上",
                "auto_driver_limit": "夫婦限定",
                "auto_use_purpose": "業務使用",
                "auto_car_name": "クラウン",
                "auto_car_model": "GRS214",
                "auto_plate_no": "名古屋300も9012",
                "coverage_target": "登録自動車",
            },
        ],
        "火災": [
            {
                "product_name": "THEすまいの保険",
                "fire_building_amount": 20000000,
                "fire_household_amount": 5000000,
                "fire_structure": "M構造",
                "fire_location": "東京都港区赤坂1-1-1",
                "fire_quake_flg": 1,
                "fire_quake_amount": 10000000,
                "fire_flood_flg": 1,
                "fire_deductible": 0,
                "coverage_target": "マンション居室",
            },
            {
                "product_name": "THEすまいの保険",
                "fire_building_amount": 15000000,
                "fire_household_amount": 3000000,
                "fire_structure": "H構造",
                "fire_location": "神奈川県横浜市青葉区2-3-4",
                "fire_quake_flg": 0,
                "fire_quake_amount": None,
                "fire_flood_flg": 1,
                "fire_deductible": 50000,
                "coverage_target": "木造一戸建て",
            },
            {
                "product_name": "THEすまいの保険",
                "fire_building_amount": 25000000,
                "fire_household_amount": 0,
                "fire_structure": "T構造",
                "fire_location": "大阪府大阪市北区3-4-5",
                "fire_quake_flg": 1,
                "fire_quake_amount": 12500000,
                "fire_flood_flg": 0,
                "fire_deductible": 0,
                "coverage_target": "鉄骨造一戸建て",
            },
        ],
        "自賠責": [
            {
                "product_name": "自動車損害賠償責任保険",
                "jibai_car_name": "プリウス",
                "jibai_car_model": "ZVW50",
                "jibai_plate_no": "品川300あ1234",
                "jibai_coverage_limit": "死亡3,000万円/傷害120万円/後遺障害4,000万円",
                "coverage_target": "登録自動車",
            },
            {
                "product_name": "自動車損害賠償責任保険",
                "jibai_car_name": "N-BOX",
                "jibai_car_model": "JF3",
                "jibai_plate_no": "横浜580え3456",
                "jibai_coverage_limit": "死亡3,000万円/傷害120万円/後遺障害4,000万円",
                "coverage_target": "軽自動車",
            },
        ],
        "傷害": [
            {
                "product_name": "THEけがの保険",
                "inj_death_amount": 10000000,
                "inj_disability_amount": 10000000,
                "inj_hospital_daily": 5000,
                "inj_surgery_benefit": "入院中10万円/外来5万円",
                "inj_outpatient_daily": 3000,
                "inj_coverage_scope": "国内のみ",
                "coverage_target": "本人",
            },
            {
                "product_name": "THEけがの保険(海外付)",
                "inj_death_amount": 20000000,
                "inj_disability_amount": 20000000,
                "inj_hospital_daily": 8000,
                "inj_surgery_benefit": "入院中20万円/外来10万円",
                "inj_outpatient_daily": 5000,
                "inj_coverage_scope": "国内外",
                "coverage_target": "本人・家族",
            },
        ],
        "賠償責任": [
            {
                "product_name": "個人賠償責任保険",
                "liab_coverage_limit": "1億円",
                "liab_deductible": 0,
                "liab_jidan_flg": 1,
                "liab_coverage_scope": "国内外",
                "coverage_target": "本人・家族",
            },
            {
                "product_name": "個人賠償責任保険",
                "liab_coverage_limit": "3億円",
                "liab_deductible": 50000,
                "liab_jidan_flg": 1,
                "liab_coverage_scope": "国内のみ",
                "coverage_target": "本人",
            },
        ],
        "サイバーリスク": [
            {
                "product_name": "サイバーリスク保険(中小)",
                "cyber_3rd_limit": "5,000万円",
                "cyber_leak_limit": "1,000万円",
                "cyber_restore_limit": "500万円",
                "cyber_biz_interruption_flg": 0,
                "cyber_annual_revenue": "1億円未満",
                "coverage_target": "法人",
            },
            {
                "product_name": "サイバーリスク保険(中堅)",
                "cyber_3rd_limit": "1億円",
                "cyber_leak_limit": "3,000万円",
                "cyber_restore_limit": "2,000万円",
                "cyber_biz_interruption_flg": 1,
                "cyber_annual_revenue": "1億円以上5億円未満",
                "coverage_target": "法人",
            },
        ],
        "所得補償": [
            {
                "product_name": "所得補償保険",
                "coverage_target": "本人",
                "inj_hospital_daily": 100000,
                "inj_coverage_scope": "国内外",
            },
        ],
        "その他": [
            {
                "product_name": "その他保険",
                "coverage_target": "対象物件",
            },
        ],
    }
    return patterns


# contract_detailsテーブルの全カラム（id, created_at, updated_at を除く）
COLUMNS = [
    "contract_id",
    "policy_type",
    "product_name",
    "coverage_target",
    "auto_taininsho",
    "auto_taibutsusho",
    "auto_jinshin",
    "auto_toshasho",
    "auto_vehicle_amount",
    "auto_vehicle_type",
    "auto_deductible",
    "auto_nfl_grade",
    "auto_age_condition",
    "auto_driver_limit",
    "auto_use_purpose",
    "auto_car_name",
    "auto_car_model",
    "auto_plate_no",
    "fire_building_amount",
    "fire_household_amount",
    "fire_structure",
    "fire_location",
    "fire_quake_flg",
    "fire_quake_amount",
    "fire_flood_flg",
    "fire_deductible",
    "jibai_car_name",
    "jibai_car_model",
    "jibai_plate_no",
    "jibai_coverage_limit",
    "inj_death_amount",
    "inj_disability_amount",
    "inj_hospital_daily",
    "inj_surgery_benefit",
    "inj_outpatient_daily",
    "inj_coverage_scope",
    "liab_coverage_limit",
    "liab_deductible",
    "liab_jidan_flg",
    "liab_coverage_scope",
    "cyber_3rd_limit",
    "cyber_leak_limit",
    "cyber_restore_limit",
    "cyber_biz_interruption_flg",
    "cyber_annual_revenue",
]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # contract_detailsテーブルが存在しない場合はDDLで作成
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='contract_details'"
    )
    if cur.fetchone() is None:
        print("contract_detailsテーブルが存在しないため、DDLで作成します...")
        with open(DDL_PATH, encoding="utf-8") as f:
            ddl = f.read()
        cur.executescript(ddl)
        conn.commit()
        print("テーブル作成完了")
    else:
        print("contract_detailsテーブルは既に存在します")

    # contractsテーブルから全レコード取得
    cur.execute("SELECT id, policy_type FROM contracts ORDER BY id")
    contracts = cur.fetchall()
    print(f"contractsレコード数: {len(contracts)}件")

    patterns = get_patterns()

    # INSERT SQL組み立て
    placeholders = ", ".join(["?" for _ in COLUMNS])
    col_list = ", ".join(COLUMNS)
    insert_sql = (
        f"INSERT OR IGNORE INTO contract_details ({col_list}) VALUES ({placeholders})"
    )

    inserted = 0
    skipped = 0

    for contract in contracts:
        contract_id = contract["id"]
        policy_type = contract["policy_type"]

        # policy_typeに対応するパターンリストを取得（未定義はその他扱い）
        pattern_list = patterns.get(policy_type, patterns["その他"])
        # idを3で割った余りでローテーション（パターン数で剰余）
        idx = contract_id % len(pattern_list)
        pattern = pattern_list[idx]

        # INSERTするrowを組み立て（カラム順に値を並べる）
        row_dict = {"contract_id": contract_id, "policy_type": policy_type}
        row_dict.update(pattern)

        # カラム順に値のタプルを作成（未定義カラムはNone）
        values = tuple(row_dict.get(col) for col in COLUMNS)

        cur.execute(insert_sql, values)
        if cur.rowcount > 0:
            inserted += 1
        else:
            skipped += 1

    conn.commit()
    conn.close()

    print(f"\n--- 実行結果 ---")
    print(f"INSERT成功: {inserted}件")
    print(f"スキップ(既存): {skipped}件")
    print(f"合計対象: {inserted + skipped}件")
    print(f"\nAgent A 完了: contract_details テーブル作成・{inserted}件INSERT")


if __name__ == "__main__":
    main()
