-- 査定物件テーブルに会社名カラムを追加
-- データベース: mirai_base

USE mirai_base;

-- 会社名カラムを追加
ALTER TABLE satei_properties 
ADD COLUMN company_name VARCHAR(255) NULL COMMENT '会社名' AFTER property_name;

-- インデックスを追加（検索用）
ALTER TABLE satei_properties 
ADD INDEX idx_company_name (company_name);
