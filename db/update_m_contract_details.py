"""
M-系契約（満期管理サンプル）の contract_details を
各契約固有の本物らしい値に更新するスクリプト
"""
import sqlite3, sys, os
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.sqlite')
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# M系契約ID一覧（contract_no → 固有データ）
M_DATA = {
    'M-A001-001': {  # 自動車
        'product_name': 'THEクルマの保険',
        'coverage_target': '登録自動車',
        'auto_taininsho': '無制限', 'auto_taibutsusho': '無制限',
        'auto_jinshin': '5,000万円', 'auto_toshasho': '1,000万円',
        'auto_vehicle_amount': '190万円', 'auto_vehicle_type': '一般',
        'auto_deductible': '5万円-10万円',
        'auto_nfl_grade': 14, 'auto_age_condition': '26歳以上',
        'auto_driver_limit': '本人・配偶者限定', 'auto_use_purpose': '日常・レジャー',
        'auto_car_name': 'ヴォクシー', 'auto_car_model': 'ZRR80W',
        'auto_plate_no': '横浜300ぬ2345',
    },
    'M-A001-002': {  # 火災
        'product_name': 'THEすまいの保険', 'coverage_target': 'マンション居室',
        'fire_building_amount': 18000000, 'fire_household_amount': 4000000,
        'fire_structure': 'M構造',
        'fire_location': '東京都新宿区西新宿3-1-2',
        'fire_quake_flg': 1, 'fire_quake_amount': 9000000,
        'fire_flood_flg': 1, 'fire_deductible': 0,
    },
    'M-A001-003': {  # 自動車
        'product_name': 'THEクルマの保険', 'coverage_target': '登録自動車',
        'auto_taininsho': '無制限', 'auto_taibutsusho': '無制限',
        'auto_jinshin': '5,000万円', 'auto_toshasho': '1,000万円',
        'auto_vehicle_amount': '230万円', 'auto_vehicle_type': '一般',
        'auto_deductible': 'なし-10万円',
        'auto_nfl_grade': 17, 'auto_age_condition': '35歳以上',
        'auto_driver_limit': '夫婦限定', 'auto_use_purpose': '通勤・通学',
        'auto_car_name': 'ステップワゴン', 'auto_car_model': 'RP3',
        'auto_plate_no': '品川500ほ6789',
    },
    'M-A001-004': {  # 傷害
        'product_name': 'THEけがの保険(海外付)', 'coverage_target': '本人・家族',
        'inj_death_amount': 20000000, 'inj_disability_amount': 20000000,
        'inj_hospital_daily': 8000, 'inj_surgery_benefit': '入院中20万円/外来10万円',
        'inj_outpatient_daily': 5000, 'inj_coverage_scope': '国内外',
    },
    'M-A001-005': {  # 火災
        'product_name': 'THEすまいの保険', 'coverage_target': '木造一戸建て',
        'fire_building_amount': 16000000, 'fire_household_amount': 3500000,
        'fire_structure': 'H構造',
        'fire_location': '埼玉県さいたま市浦和区常盤4-5-6',
        'fire_quake_flg': 1, 'fire_quake_amount': 8000000,
        'fire_flood_flg': 1, 'fire_deductible': 50000,
    },
    'M-B002-001': {  # 自動車
        'product_name': 'THEクルマの保険', 'coverage_target': '登録自動車',
        'auto_taininsho': '無制限', 'auto_taibutsusho': '無制限',
        'auto_jinshin': '3,000万円', 'auto_toshasho': '500万円',
        'auto_vehicle_amount': '170万円', 'auto_vehicle_type': '車対車+A',
        'auto_deductible': '5万円-10万円',
        'auto_nfl_grade': 9, 'auto_age_condition': '全年齢担保',
        'auto_driver_limit': '限定なし', 'auto_use_purpose': '日常・レジャー',
        'auto_car_name': 'フィット', 'auto_car_model': 'GR3',
        'auto_plate_no': '大宮500あ1111',
    },
    'M-B002-002': {  # 火災
        'product_name': 'THEすまいの保険', 'coverage_target': 'マンション居室',
        'fire_building_amount': 22000000, 'fire_household_amount': 5000000,
        'fire_structure': 'M構造',
        'fire_location': '神奈川県横浜市中区山下町2-3',
        'fire_quake_flg': 1, 'fire_quake_amount': 11000000,
        'fire_flood_flg': 0, 'fire_deductible': 0,
    },
    'M-B002-003': {  # 傷害
        'product_name': 'THEけがの保険(海外付)', 'coverage_target': '本人・家族',
        'inj_death_amount': 30000000, 'inj_disability_amount': 30000000,
        'inj_hospital_daily': 10000, 'inj_surgery_benefit': '入院中20万円/外来10万円',
        'inj_outpatient_daily': 6000, 'inj_coverage_scope': '国内外',
    },
    'M-B002-004': {  # 自動車
        'product_name': 'THEクルマの保険', 'coverage_target': '登録自動車',
        'auto_taininsho': '無制限', 'auto_taibutsusho': '無制限',
        'auto_jinshin': '5,000万円', 'auto_toshasho': '1,000万円',
        'auto_vehicle_amount': '260万円', 'auto_vehicle_type': '一般',
        'auto_deductible': 'なし-10万円',
        'auto_nfl_grade': 20, 'auto_age_condition': '35歳以上',
        'auto_driver_limit': '本人・配偶者限定', 'auto_use_purpose': '業務使用',
        'auto_car_name': 'アルファード', 'auto_car_model': 'AGH30W',
        'auto_plate_no': '横浜300さ8888',
    },
    'M-B002-005': {  # その他
        'product_name': '企業総合保険', 'coverage_target': '事務所・設備一式',
    },
    'M-B002-006': {  # 火災
        'product_name': 'THEすまいの保険', 'coverage_target': '木造一戸建て',
        'fire_building_amount': 20000000, 'fire_household_amount': 4000000,
        'fire_structure': 'H構造',
        'fire_location': '神奈川県川崎市宮前区宮崎1-2-3',
        'fire_quake_flg': 1, 'fire_quake_amount': 10000000,
        'fire_flood_flg': 1, 'fire_deductible': 50000,
    },
    'M-C003-001': {  # 自動車
        'product_name': 'THEクルマの保険', 'coverage_target': '登録自動車',
        'auto_taininsho': '無制限', 'auto_taibutsusho': '無制限',
        'auto_jinshin': '5,000万円', 'auto_toshasho': '1,000万円',
        'auto_vehicle_amount': '200万円', 'auto_vehicle_type': '一般',
        'auto_deductible': '5万円-10万円',
        'auto_nfl_grade': 11, 'auto_age_condition': '26歳以上',
        'auto_driver_limit': '家族限定', 'auto_use_purpose': '日常・レジャー',
        'auto_car_name': 'セレナ', 'auto_car_model': 'C27',
        'auto_plate_no': '名古屋300む3456',
    },
    'M-C003-002': {  # 火災
        'product_name': 'THEすまいの保険', 'coverage_target': '木造一戸建て',
        'fire_building_amount': 14000000, 'fire_household_amount': 3000000,
        'fire_structure': 'H構造',
        'fire_location': '愛知県名古屋市昭和区五軒家町3-4',
        'fire_quake_flg': 0, 'fire_quake_amount': None,
        'fire_flood_flg': 1, 'fire_deductible': 50000,
    },
    'M-C003-003': {  # 自動車
        'product_name': 'THEクルマの保険', 'coverage_target': '登録自動車',
        'auto_taininsho': '無制限', 'auto_taibutsusho': '無制限',
        'auto_jinshin': '5,000万円', 'auto_toshasho': '1,000万円',
        'auto_vehicle_amount': '280万円', 'auto_vehicle_type': '一般',
        'auto_deductible': 'なし-10万円',
        'auto_nfl_grade': 19, 'auto_age_condition': '35歳以上',
        'auto_driver_limit': '夫婦限定', 'auto_use_purpose': '通勤・通学',
        'auto_car_name': 'ランドクルーザー', 'auto_car_model': 'GRJ150W',
        'auto_plate_no': '名古屋300め5678',
    },
    'M-C003-004': {  # 傷害
        'product_name': 'THEけがの保険', 'coverage_target': '本人',
        'inj_death_amount': 15000000, 'inj_disability_amount': 15000000,
        'inj_hospital_daily': 6000, 'inj_surgery_benefit': '入院中10万円/外来5万円',
        'inj_outpatient_daily': 4000, 'inj_coverage_scope': '国内のみ',
    },
    'M-C003-005': {  # 火災
        'product_name': 'THEすまいの保険', 'coverage_target': '鉄骨造一戸建て',
        'fire_building_amount': 28000000, 'fire_household_amount': 6000000,
        'fire_structure': 'T構造',
        'fire_location': '愛知県名古屋市千種区末盛通6-7',
        'fire_quake_flg': 1, 'fire_quake_amount': 14000000,
        'fire_flood_flg': 1, 'fire_deductible': 0,
    },
}

updated = 0
for contract_no, data in M_DATA.items():
    # contract_id を取得
    row = cur.execute("SELECT id FROM contracts WHERE contract_no = ?", (contract_no,)).fetchone()
    if not row:
        print(f"  WARNING: {contract_no} not found in contracts")
        continue
    contract_id = row['id']

    # 全カラムをNULLにリセットしてから対象データをUPDATE
    null_fields = [
        'product_name', 'coverage_target',
        'auto_taininsho', 'auto_taibutsusho', 'auto_jinshin', 'auto_toshasho',
        'auto_vehicle_amount', 'auto_vehicle_type', 'auto_deductible',
        'auto_nfl_grade', 'auto_age_condition', 'auto_driver_limit',
        'auto_use_purpose', 'auto_car_name', 'auto_car_model', 'auto_plate_no',
        'fire_building_amount', 'fire_household_amount', 'fire_structure',
        'fire_location', 'fire_quake_flg', 'fire_quake_amount',
        'fire_flood_flg', 'fire_deductible',
        'jibai_car_name', 'jibai_car_model', 'jibai_plate_no', 'jibai_coverage_limit',
        'inj_death_amount', 'inj_disability_amount', 'inj_hospital_daily',
        'inj_surgery_benefit', 'inj_outpatient_daily', 'inj_coverage_scope',
        'liab_coverage_limit', 'liab_deductible', 'liab_jidan_flg', 'liab_coverage_scope',
        'cyber_3rd_limit', 'cyber_leak_limit', 'cyber_restore_limit',
        'cyber_biz_interruption_flg', 'cyber_annual_revenue',
    ]

    # SET句（data にあるカラムは値、ないカラムはNULL）
    set_parts = []
    set_vals = []
    for col in null_fields:
        set_parts.append(f"{col} = ?")
        set_vals.append(data.get(col))  # data にないキーは None (NULL)

    set_vals.append(contract_id)
    sql = f"UPDATE contract_details SET {', '.join(set_parts)} WHERE contract_id = ?"
    cur.execute(sql, set_vals)
    updated += 1
    print(f"  更新: {contract_no} ({data.get('product_name', '?')})")

conn.commit()
conn.close()
print(f"\n完了: {updated}件のM系契約detailを更新しました")
