-- property_ownersテーブルにprofit_management_seq_noカラムを追加
-- データベース: mirai_base

USE mirai_base;

-- profit_management_seq_noカラムを追加
ALTER TABLE property_owners 
ADD COLUMN profit_management_seq_no INT DEFAULT NULL COMMENT '粗利按分管理レコードのseq_no（外部キー）' 
AFTER property_id;

-- インデックスを追加
ALTER TABLE property_owners 
ADD INDEX idx_profit_management_seq_no (profit_management_seq_no);

-- 既存データの更新（property_idが一致する最初のprofit_managementレコードのseq_noを設定）
UPDATE property_owners po
INNER JOIN (
    SELECT property_id, MIN(seq_no) as min_seq_no
    FROM profit_management
    GROUP BY property_id
) pm ON po.property_id = pm.property_id
SET po.profit_management_seq_no = pm.min_seq_no
WHERE po.profit_management_seq_no IS NULL;



