-- 更改おすすめプランTBL
-- 別システムが事前生成したPDFをBLOBで保持する
CREATE TABLE IF NOT EXISTS renewal_recommend_plans (
    id           INTEGER  PRIMARY KEY AUTOINCREMENT,
    contract_no  TEXT     NOT NULL UNIQUE,   -- 元契約の証券番号（contracts.contract_noと紐づけ）
    pdf_data     BLOB     NOT NULL,           -- 更改通知書PDFバイナリ
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_renewal_recommend_plans_contract_no
    ON renewal_recommend_plans(contract_no);
