-- 手数料管理テーブル
CREATE TABLE IF NOT EXISTS commissions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    agency_code       TEXT NOT NULL,
    insurer_name      TEXT NOT NULL,
    fiscal_year       INTEGER NOT NULL,
    month             INTEGER NOT NULL,
    first_year_amount INTEGER DEFAULT 0,
    renewal_amount    INTEGER DEFAULT 0,
    other_amount      INTEGER DEFAULT 0,
    status            TEXT DEFAULT '作成中',
    created_at        TEXT DEFAULT (datetime('now','localtime')),
    updated_at        TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(agency_code, insurer_name, fiscal_year, month)
);
CREATE INDEX IF NOT EXISTS idx_comm_agency ON commissions(agency_code);
CREATE INDEX IF NOT EXISTS idx_comm_fy ON commissions(fiscal_year, month);

-- 意向確認テーブル
CREATE TABLE IF NOT EXISTS intention_confirmations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id       INTEGER REFERENCES contracts(id),
    policy_no         TEXT NOT NULL,
    agency_code       TEXT NOT NULL,
    customer_name     TEXT NOT NULL,
    staff_code        TEXT,
    policy_type       TEXT,
    customer_needs    TEXT,
    proposed_products TEXT,
    compared_products TEXT,
    recommendation_reason TEXT,
    final_product     TEXT,
    customer_confirmed INTEGER DEFAULT 0,
    confirmed_at      TEXT,
    lapse_reason      TEXT,
    lapse_detail      TEXT,
    status            TEXT DEFAULT '未記録',
    created_at        TEXT DEFAULT (datetime('now','localtime')),
    updated_at        TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_int_agency ON intention_confirmations(agency_code);
CREATE INDEX IF NOT EXISTS idx_int_policy ON intention_confirmations(policy_no);
