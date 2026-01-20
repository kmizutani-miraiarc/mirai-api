-- purchase_summaryテーブルにis_appraisal_onlyカラムを追加
-- 査定物件のみのデータと全取引のデータを区別するため
ALTER TABLE purchase_summary 
ADD COLUMN is_appraisal_only BOOLEAN DEFAULT FALSE COMMENT '査定物件のみフラグ' AFTER month;

-- UNIQUE KEYを更新（is_appraisal_onlyを含める）
ALTER TABLE purchase_summary 
DROP INDEX uk_purchase_summary;

ALTER TABLE purchase_summary 
ADD UNIQUE KEY uk_purchase_summary (aggregation_year, owner_id, month, is_appraisal_only);

-- 既存データは全取引として扱う（is_appraisal_only=FALSE）
-- デフォルト値がFALSEなので、既存データには自動的に適用される
