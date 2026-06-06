-- contract_details カラム変更マイグレーション v2
-- 自賠責: jibai_coverage_limit 削除 → jibai_injury_limit / jibai_death_limit 追加
-- 賠償責任: liab_coverage_limit / liab_deductible / liab_jidan_flg / liab_coverage_scope 削除
--          → liab_bodily_limit_per_person / liab_bodily_limit_per_accident / liab_property_limit 追加
-- 所得補償: 6カラム新規追加

-- 1. 新カラム追加
ALTER TABLE contract_details ADD COLUMN jibai_injury_limit    INTEGER DEFAULT 1200000;
ALTER TABLE contract_details ADD COLUMN jibai_death_limit     INTEGER DEFAULT 30000000;

ALTER TABLE contract_details ADD COLUMN liab_bodily_limit_per_person   TEXT;
ALTER TABLE contract_details ADD COLUMN liab_bodily_limit_per_accident TEXT;
ALTER TABLE contract_details ADD COLUMN liab_property_limit            TEXT;

ALTER TABLE contract_details ADD COLUMN income_monthly_benefit  INTEGER;
ALTER TABLE contract_details ADD COLUMN income_deductible_days  INTEGER;
ALTER TABLE contract_details ADD COLUMN income_benefit_period   TEXT;
ALTER TABLE contract_details ADD COLUMN income_coverage_type    TEXT;
ALTER TABLE contract_details ADD COLUMN income_occupation_type  TEXT;
ALTER TABLE contract_details ADD COLUMN income_monthly_income   INTEGER;

-- 2. 既存データ移行（賠償責任: liab_coverage_limit → liab_bodily_limit_per_person へ）
UPDATE contract_details
SET liab_bodily_limit_per_person = liab_coverage_limit
WHERE policy_type = '賠償責任' AND liab_coverage_limit IS NOT NULL;

-- 3. 旧カラム削除
ALTER TABLE contract_details DROP COLUMN jibai_coverage_limit;
ALTER TABLE contract_details DROP COLUMN liab_coverage_limit;
ALTER TABLE contract_details DROP COLUMN liab_deductible;
ALTER TABLE contract_details DROP COLUMN liab_jidan_flg;
ALTER TABLE contract_details DROP COLUMN liab_coverage_scope;
