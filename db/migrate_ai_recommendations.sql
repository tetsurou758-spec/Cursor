-- ai_recommendations テーブル新設
-- AIによる保険加入推奨履歴を管理する

CREATE TABLE IF NOT EXISTS ai_recommendations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id      TEXT NOT NULL,          -- 顧客ID（customersテーブルのcustomer_id）
    agency_code      TEXT NOT NULL,          -- 代理店コード（アクセス制御用）
    group_code       TEXT NOT NULL,          -- 参照グループコード
    recommend_types  TEXT,                   -- 推奨種目リスト（JSON配列: ["FIRE","CYBER"]）
    reason           TEXT,                   -- AI推奨理由（自然言語）
    risk_score       REAL,                   -- リスクスコア（0.0〜1.0）
    created_by       TEXT,                   -- 実行ユーザーID（代理店ユーザーまたは社員ID）
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_bulk          INTEGER DEFAULT 0,      -- 0=個別生成, 1=一括生成
    bulk_job_id      TEXT                    -- 一括ジョブID（is_bulk=1のときのみ）
);

CREATE INDEX IF NOT EXISTS idx_ai_rec_customer ON ai_recommendations(customer_id);
CREATE INDEX IF NOT EXISTS idx_ai_rec_agency   ON ai_recommendations(agency_code);
CREATE INDEX IF NOT EXISTS idx_ai_rec_group    ON ai_recommendations(group_code);
